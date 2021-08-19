"""Main module."""

import enum
import logging
from typing import List, Optional, Tuple
import time
from serial import Serial

logger = logging.getLogger(__name__)

Point = Tuple[float, float]


class PenState(enum.Enum):
    DOWN = 0
    UP = 30
    HIGH_UP = 90


class Rotation(enum.Enum):
    CLOCKWISE = 2
    COUNTER_CLOCKWISE = 3


class CommandException(Exception):
    pass


class SovolSO1(object):
    """
    Object for controlling the Sovol SO1 pen plotter given the G-Code here:

    https://marlinfw.org/docs/gcode/G005.html
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB1",
        baud: int = 115200,
        max_dimensions: Point = (300.0, 300.0),
        startup_timeout: float = 10.0,
        timeout: float = 0.0,
        travel_speed: int = 10000,
        drawing_speed: int = 3000,
    ):
        self.serial = Serial(port, baud, dsrdtr=True, timeout=timeout)
        self.end_of_line = b"\n"
        self.max_dimensions = max_dimensions
        self.travel_speed = travel_speed
        self.drawing_speed = drawing_speed

        # Wait until the machine has started up, after some amount of time
        # establishing a new connection will cause the machine to reboot.
        # It would be good to figure out how to make this a little more robust
        time.sleep(startup_timeout)
        startup_text = self.serial.read_all()
        logger.debug(startup_text.decode("ascii"))
        self.write("G90")  # Set to absolute mode
        self.write("G21")  # Set to mm

    def close(self):
        self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.disableSteppers()
        self.close()

    def disableSteppers(
        self,
        timeout: Optional[float] = None,
        send_x_flag: bool = False,
        send_y_flag: bool = False,
        send_z_flag: bool = False,
    ):
        command = "M18"
        if timeout:
            command += " S{timeout:0.0f}"
        if send_x_flag:
            command += " X"
        if send_y_flag:
            command += " Y"
        if send_z_flag:
            command += " Z"
        self.write(command)

    def enableSteppers(
        self,
        send_x_flag: bool = False,
        send_y_flag: bool = False,
        send_z_flag: bool = False,
    ):
        command = "M17"
        if send_x_flag:
            command += " X"
        if send_y_flag:
            command += " Y"
        if send_z_flag:
            command += " Z"
        self.write(command)

    def write(self, cmd: str, timeout: float = 100.0):
        success = False

        # self.serial.flush() # Make sure we don't have any garbage left over.

        logger.debug(cmd)
        # Write the command
        self.serial.write(cmd.encode("utf-8") + self.end_of_line)

        # Wait until we get an ok returned
        start_time = time.time()
        read_buffer = ""
        while (not success) and ((time.time() - start_time) < timeout):
            # To do this properly we really should have a buffer incase we wrap over.
            read_buffer += self.serial.read().decode("ascii")
            if "ok" in read_buffer:
                logger.debug(read_buffer)
                logger.info("Success!!!")
                success = True
        if not success:
            logger.critical(read_buffer)
            raise CommandException("Failed to get a successful command")

    def setPen(self, state: PenState):
        self.write(f"M280P0S{state.value}")

    def pause(self, pause_time_ms: int):
        self.write(f"G4 P{pause_time_ms}")

    def moveTo(self, point: Point):
        self.write(f"G1 X{point[0]:0.3f} Y{point[1]:0.3f}")

    def arcTo(
        self,
        point: Optional[Point] = None,
        center: Optional[Point] = None,
        rot: Rotation = Rotation.CLOCKWISE,
        radius: Optional[float] = None,
    ):
        if center:
            if point:
                self.write(
                    f"G{rot.value} "
                    f"X{point[0]:0.3f} Y{point[1]:0.3f} "
                    f"I{center[0]:0.3f} J{center[1]:0.3f}"
                )
            else:
                self.write(f"G{rot.value} " f"I{center[0]:0.3f} J{center[1]:0.3f}")

        elif radius:
            self.write(
                f"G{rot.value} " f"X{point[0]:0.3f} Y{point[1]:0.3f} " f"R{radius:0.3f}"
            )
        else:
            raise CommandException("Must provide either a center point or a radius")

    def autoHome(self):
        self.write("G28", timeout=100.0)

    def setSpeed(self, speed: int):
        self.write(f"G1 F{speed}")

    def setTravelSpeed(self):
        self.setSpeed(self.travel_speed)

    def setDrawingSpeed(self):
        self.setSpeed(self.drawing_speed)
