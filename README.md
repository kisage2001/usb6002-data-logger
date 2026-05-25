# USB-6002 Data Logger

High-performance data acquisition system for NI USB-6002


## Features
✅ 8-channel simultaneous real-time monitoring  
✅ Physical quantity conversion (coefficient settings)  
✅ Data recording (Excel output)  
✅ Graph screenshot functionality  
✅ Configuration save/load  
✅ Bulk coefficient change feature  

## Requirements
- Python 3.8+
- NI USB-6002
- NI-DAQmx Driver

## Installation

### 1. Install NI-DAQmx Driver
https://www.ni.com/en-us/support/downloads/drivers/download.ni-daqmx.html

### 2. Install Python Packages
```bash
pip install nidaqmx matplotlib pandas numpy pillow pywin32 openpyxl
```

## Usage
```bash
python usb6002_configurable.py
```

## Configuration
A `config.json` file is automatically generated on first launch.
You can configure channel names, conversion factors, units, and Y-axis ranges through the configuration editor.

## License
MIT License

## Author
Tsutsumi Hirotaka

https://github.com/kisage2001/usb6002-data-logger/blob/main/Image.png
