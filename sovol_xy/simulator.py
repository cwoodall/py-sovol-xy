#!/usr/bin/env python
# Using Cairo and python https://pypi.org/project/pycairo/
# https://pycairo.readthedocs.io/en/latest/reference/surfaces.html
# https://www.geeksforgeeks.org/python-os-readv-method/
# https://stackoverflow.com/questions/21429369/read-file-with-timeout-in-python
# https://stackoverflow.com/questions/2291772/virtual-serial-device-in-python
# vsketch
import math
import numpy as np
# from sovol_xy.sovol_xy import Point
import cairo
from numpy import positive
import pygame
import PIL.Image as Image
import os
import pty
import serial
import sys
import select
from parse import parse


def surface_to_pil(surface):
    return Image.frombuffer(
        mode='RGBA',
        size=(int(surface.get_width()), int(surface.get_height())),
        data=surface.get_data(),
    )


def pil_to_surface(image):
    return cairo.ImageSurface.create_for_data(
        bytearray(image.tobytes('raw', 'BGRa')),
        cairo.FORMAT_ARGB32,
        int(image.width),
        int(image.height),
    )


def add_surfaces(a, b):
    assert a.get_width() == b.get_width() and a.get_height() == b.get_height()
    result_pil = Image.new(
        mode='RGBA',
        size=sz,
        color=(0.0, 0.0, 0.0, 0.0),
    )
    for surface in (a, b):
        surface_pil = surface_to_pil(surface)
        result_pil.paste(im=surface_pil, mask=surface_pil)
    return pil_to_surface(result_pil)


class SovolXYSimulator(object):
    def __init__(self, width, height):
        self.master, self.slave = pty.openpty()
        self.serial_name = os.ttyname(self.slave)
        self.serial = serial.Serial(self.serial_name, timeout=.001)

        self.width = width
        self.height = height
        print(f"Virtual Serial Port to attach to: {self.serial_name}")
        self.x_max = 300
        self.y_max = 300
        self.buffer1 = bytearray(100)
        self.line_width = 0.005
        self.pen_height = 30.0
        self.position = np.array([0.0, 0.0])
        self.speed = 10000  # mm / min
        self.command_position = None
        self.line_color = (0.0, 0, 0, 1)
        self.command_position_stack = []

        self.toolhead_surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, width, height)
        self.toolhead_ctx = cairo.Context(self.toolhead_surface)
        self.toolhead_ctx.scale(width, height)  # Normalizing the canvas
        self.toolhead_ctx.arc(0, 0, .01, 0, 360)
        self.toolhead_ctx.set_line_cap(cairo.LineCap.ROUND)
        self.toolhead_ctx.set_source_rgba(1.0, 0, 0, 1)
        self.toolhead_ctx.set_line_width(.005)
        self.toolhead_ctx.stroke()

        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self.ctx = cairo.Context(self.surface)
        self.ctx.scale(width, height)  # Normalizing the canvas

        # Clear to white background
        self.ctx.rectangle(0, 0, 1, 1)  # Rectangle(x0, y0, x1, y1)
        self.ctx.set_source_rgba(1.0, 1.0, 1.0)
        self.ctx.fill()
        self.ctx.move_to(*self.position)
        self.ctx.set_line_cap(cairo.LineCap.ROUND)

    def update(self):
        # To read from the device
        read_buffer = self.serial.read_all()
        if read_buffer:
            print(read_buffer)

        # Select to see if we have a valid connection
        r, w, e = select.select([self.master], [], [], 0)
        if self.master in r:
            # print(r,w,e)
            bytes_read = os.readv(self.master, [self.buffer1])
            if bytes_read > 0:
                lines = self.buffer1.splitlines()
                if len(lines) > 1:
                    line: bytearray = lines[0].decode("ascii")
                    print(line)
                    if line == "G90":
                        # Absolute positioning, relative positioning
                        # is not supported
                        os.write(self.master, b"ok\n\r")
                    elif line == "G91":
                        # Relative positioning is not supported
                        os.write(self.master, b"error: not supported\n\r")
                    elif "M18" in line:
                        os.write(self.master, b"ok\n\r")
                    elif line == "G92":
                        # Set the current position
                        args = line.split(" ")[1:]
                        x = None
                        y = None
                        for arg in args:
                            print(arg)
                            code, value = parse("{:l}{:g}", arg)
                            if code is "X":
                                x = value / self.x_max
                            elif code is "Y":
                                y = value / self.y_max

                        # Need to change this to deal with drawing speeds more reliably
                        if x and y:
                            self.position = np.array([x, y])
                            os.write(self.master, b"ok\n\r")
                        else:
                            os.write(
                                self.master, b"error: invalid command\n\r")
                    elif line == "G21":
                        os.write(self.master, b"ok\n\r")
                    elif line == "G28":
                        # Auto Home clears and then brings the pen position back home.
                        self.position = (0.0, 0.0)
                        # Rectangle(x0, y0, x1, y1)
                        self.ctx.rectangle(0, 0, 1, 1)
                        self.ctx.set_source_rgba(1.0, 1.0, 1.0)
                        self.ctx.fill()
                        self.ctx.move_to(*self.position)
                        os.write(self.master, b"ok\n\r")
                    elif "G1" in line or "G0" in line:
                        # https://marlinfw.org/docs/gcode/G000-G001.html
                        # E, Z and S are ignored
                        args = line.split(" ")[1:]
                        x = None
                        y = None
                        speed = None
                        for arg in args:
                            print(arg)
                            code, value = parse("{:l}{:g}", arg)
                            if code is "X":
                                x = value / self.x_max
                            if code is "Y":
                                y = value / self.y_max
                            if code is "F":
                                print(f"SPEED SET TO {value}")
                                speed = value

                        # Need to change this to deal with drawing speeds more reliably
                        if x and y:
                            self.command_position_stack.append(
                                np.array([x, y]))
                            print(self.command_position_stack)
                        else:
                            os.write(self.master, b"ok\n\r")

                        if speed:
                            self.speed = speed
                    elif "M280" in line:
                        pen_height = parse("M280P0S{:d}", line)[0]
                        self.pen_height = pen_height
                        print(f"Pen Height: {pen_height}")
                        os.write(self.master, b"ok\n\r")
                    elif "G4" in line:
                        # Pauses are not handled just passed along
                        os.write(self.master, b"ok\n\r")
                    elif "G3" in line or "G2" in line:
                        # Arcs are not supported
                        os.write(self.master, b"error: not supported\n\r")

        # Move the pen
        dt = .01
        # convert mm/min to %/second
        speed_limit = (self.speed / 60.0)/self.x_max
        # Note I think this only works for x and y being hte same dimensions
        if len(self.command_position_stack) > 0:
            self.command_position = self.command_position_stack[0]

            dp = self.command_position - self.position
            dp_norm = dp / (dp**2).sum()**0.5
            dp_dt = dp / dt
            speed = np.linalg.norm(dp_dt)
            print(
                f"speed: {self.speed}, command: {self.command_position}, pos: {self.position}, dp_dt: {dp_dt}, {speed_limit}")
            if abs(speed) < speed_limit:
                self.position = self.command_position
            else:
                self.position += dp_norm * speed_limit * dt

            if self.pen_height > 10.0:
                print(f"Moving to {self.position}")
                self.ctx.move_to(*self.position)
            else:
                print(f"Line to {self.position}")
                self.ctx.line_to(*self.position)
                self.ctx.set_source_rgba(*self.line_color)  # Solid color
                self.ctx.set_line_width(self.line_width)
                self.ctx.stroke()
                self.ctx.move_to(*self.position)

            if self.command_position[0] == self.position[0] and \
                    self.command_position[1] == self.position[1]:
                self.command_position_stack.pop(0)
                os.write(self.master, b"ok\n\r")

        self.toolhead_surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, self.width, self.height)
        self.toolhead_ctx = cairo.Context(self.toolhead_surface)
        self.toolhead_ctx.scale(self.width, self.height)  # Normalizing the canvas
        self.toolhead_ctx.arc(*self.position, .01, 0, 360)
        self.toolhead_ctx.set_line_cap(cairo.LineCap.ROUND)
        self.toolhead_ctx.set_source_rgba(1.0, 0, 0, 1)
        self.toolhead_ctx.set_line_width(.005)
        if self.pen_height < 10:
            self.toolhead_ctx.fill()
        self.toolhead_ctx.stroke()


def bgra_surf_to_rgba_string(cairo_surface):
    """
    On little-endian machines (and perhaps big-endian, who knows?),
    Cairo's ARGB format becomes a BGRA format. PyGame does not accept
    BGRA, but it does accept RGBA, which is why we have to convert the
    surface data. You can check what endian-type you have by printing
    out sys.byteorder
    """
    # We use PIL to do this
    img = Image.frombuffer(
        'RGBA', (cairo_surface.get_width(),
                 cairo_surface.get_height()),
        cairo_surface.get_data().tobytes(), 'raw', 'BGRA', 0, 1)

    return img.tobytes('raw', 'RGBA', 0, 1)


def main():
    width, height = 1000, 1000
    pygame.init()

    pygame.display.set_mode((width, height))
    screen = pygame.display.get_surface()
    pygame.display.set_caption('Simulator')
    robot = SovolXYSimulator(width, height)
    done = False
    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
        screen.fill(pygame.color.Color('white'))
        robot.update()

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)
        ctx.scale(width, height)
        ctx.identity_matrix()

        ctx.set_source_surface(robot.surface, 0, 0)
        ctx.paint()
        ctx.set_source_surface(robot.toolhead_surface, 0, 0)
        ctx.identity_matrix()
        ctx.paint()

        buf = bgra_surf_to_rgba_string(surface)
        image = pygame.image.frombuffer(buf, (width, height), "RGBA").convert()
        screen.blit(image, image.get_rect())
        pygame.display.flip()

if __name__ == "__main__":
    main()