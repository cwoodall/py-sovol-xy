# Sovol XY Plotter


<p align="center">
<a href="https://pypi.python.org/pypi/sovol_xy">
    <img src="https://img.shields.io/pypi/v/sovol_xy.svg"
        alt = "Release Status">
</a>

<a href="https://github.com/cwoodall/sovol_xy/actions">
    <img src="https://github.com/cwoodall/sovol_xy/actions/workflows/main.yml/badge.svg?branch=release" alt="CI Status">
</a>

<a href="https://sovol-xy.readthedocs.io/en/latest/?badge=latest">
    <img src="https://readthedocs.org/projects/sovol-xy/badge/?version=latest" alt="Documentation Status">
</a>

<a href="https://pyup.io/repos/github/cwoodall/sovol_xy/">
<img src="https://pyup.io/repos/github/cwoodall/sovol_xy/shield.svg" alt="Updates">
</a>

</p>


Library for controlling the Sovol-SO1 xy plotter using the Marlin Firmware


* Free software: MIT
* Documentation: <https://sovol-xy.readthedocs.io>


## Features

* TODO

## Architecture

```mermaid
graph LR
    ParseSVG --> ShapesToPathSegments
    SortAndCombinePathSegments --> WriteToDevice
```

Devices:
- Simulation
- File (produce G-Code)
- Sovol-XY

## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [zillionare/cookiecutter-pypackage](https://github.com/zillionare/cookiecutter-pypackage) project template.
