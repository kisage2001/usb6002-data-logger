# USB-6002 Data Acquisition System

High-performance data acquisition and control system for NI USB-6002.

A real-time multi-channel logger that also works as a function generator,
digital I/O controller, and frequency-response (Bode) analyzer.

<img src="https://github.com/kisage2001/usb6002-data-logger/blob/main/Image.png" width="600" alt="ロゴ">
<img src="https://github.com/kisage2001/usb6002-data-logger/blob/main/Image2.png" width="600" alt="ロゴ">

## Features

- ✅ 8-channel simultaneous real-time monitoring
- ✅ Physical quantity conversion (per-channel coefficients) and zero/offset
- ✅ Data recording and Hold snapshot (Excel output with graph)
- ✅ Graph screenshot / clipboard export in academic-paper format
- ✅ Configuration save/load and bulk coefficient change
- ✅ Function generator on AO0/AO1 (Sine/Square/Triangle/Sawtooth/DC) with live preview
- ✅ Frequency response (Bode) measurement with Excel output and adjustable graph format
- ✅ Digital I/O on P0.0–P0.7 (per-line Input/Output, color-coded state)

> USB-6002 limits: AO update rate is 5 kS/s (practical upper frequency ~500 Hz);
> digital I/O is software-timed TTL (0/3.3 V).

## Requirements

- Python 3.8+
- NI USB-6002
- NI-DAQmx Driver

## Installation

1. Install the NI-DAQmx Driver
   https://www.ni.com/en-us/support/downloads/drivers/download.ni-daqmx.html

2. Install the Python packages

   ```
   pip install nidaqmx matplotlib pandas numpy pillow pywin32 openpyxl
   ```

## Usage

```
python usb6002_configurable.py
```

## Configuration

A `config.json` file is generated on first launch. Channel names, conversion
factors, units, and Y-axis ranges can be set through the configuration editor.

## License

MIT License

## Author

Tsutsumi Hirotaka
