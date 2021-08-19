"""Console script for sovol_xy."""

import fire

from . import SovolSO1


def help():
    print("sovol_xy")
    print("=" * len("sovol_xy"))
    print("Library for controlling the Sovol-SO1 xy plotter using the Marlin Firmware")


def main():
    fire.Fire({"help": help})


if __name__ == "__main__":
    main()  # pragma: no cover
