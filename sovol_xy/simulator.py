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


class SovolXYSimulator(object):
    def __init__(self):
        self.master, self.slave = pty.openpty()
        self.serial_name = os.ttyname(self.slave)
        self.serial = serial.Serial(self.serial_name, timeout=.001)

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
    def update(self, ctx):
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
                            os.write(self.master, b"error: invalid command\n\r")
                    elif line == "G21":
                        os.write(self.master, b"ok\n\r")
                    elif line == "G28":
                        # self.position = (0.0, 0.0)
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
                            self.command_position_stack.append(np.array([x, y]))
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
        speed_limit = (self.speed/ 60.0)/self.x_max
        # Note I think this only works for x and y being hte same dimensions
        if len(self.command_position_stack) > 0:
            self.command_position = self.command_position_stack[0]

            dp = self.command_position - self.position
            dp_norm = dp / (dp**2).sum()**0.5
            dp_dt = dp / dt
            speed = np.linalg.norm(dp_dt)
            print(f"speed: {self.speed}, command: {self.command_position}, pos: {self.position}, dp_dt: {dp_dt}, {speed_limit}")
            if abs(speed) < speed_limit:
                self.position = self.command_position
            else:
                self.position += dp_norm * speed_limit * dt

            if self.pen_height > 10.0:
                print(f"Moving to {self.position}")
                ctx.move_to(*self.position)
            else:
                print(f"Line to {self.position}")
                ctx.line_to(*self.position)
                ctx.set_source_rgba(*self.line_color)  # Solid color
                ctx.set_line_width(self.line_width)
                ctx.stroke()
                ctx.move_to(*self.position)

            if self.command_position[0] == self.position[0] and \
                self.command_position[1] == self.position[1]:
                self.command_position_stack.pop(0)
                os.write(self.master, b"ok\n\r")



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


robot = SovolXYSimulator()

width, height = 1000, 1000
pygame.init()

pygame.display.set_mode((width, height))
screen = pygame.display.get_surface()
pygame.display.set_caption('Simulator')
done = False

surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
ctx = cairo.Context(surface)
ctx.scale(width, width)  # Normalizing the canvas

# Clear to white background
ctx.rectangle(0, 0, 1, 1)  # Rectangle(x0, y0, x1, y1)
ctx.set_source_rgba(1.0, 1.0, 1.0)
ctx.fill()
ctx.move_to(*robot.position)

while not done:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            done = True

    ctx.set_line_cap(cairo.LineCap.ROUND)
    robot.update(ctx)

    # i += .0005
    # i = i % 1

    # ctx.translate(0, 0)  # Changing the current transformation matrix

    # ctx.move_to(0, 0)
    # # Arc(cx, cy, radius, start_angle, stop_angle)
    # ctx.arc(0.2, 0.1, 0.1, -math.pi / 2, 0)
    # ctx.line_to(0.5, 0.1)  # Line to (x,y)
    # # Curve(x1, y1, x2, y2, x3, y3)
    # ctx.curve_to(0.5, 0.2, 0.5, 0.4, 0.2, 0.8)
    # ctx.close_path()

    buf = bgra_surf_to_rgba_string(surface)
    image = pygame.image.frombuffer(buf, (width, height), "RGBA").convert()
    screen.blit(image, image.get_rect())
    pygame.display.flip()
