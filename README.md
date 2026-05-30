USB-6002 Data Acquisition System
High-performance data acquisition and control system for NI USB-6002.
A real-time multi-channel logger that also turns the USB-6002 into a function
generator, a digital I/O controller, and a frequency-response (Bode) analyzer —
suitable for benchtop experiments and engineering education.
Features
Acquisition & Monitoring

✅ 8-channel simultaneous real-time monitoring
✅ Physical quantity conversion (per-channel coefficient settings)
✅ Per-channel zero/offset (tare) function
✅ Data recording with Excel output
✅ Hold snapshot — pressing Hold saves the on-screen data to Excel, including a worksheet with a graph rendered in the same style as the live plot
✅ Graph screenshot / clipboard export in academic-paper format
✅ Configuration save/load (config.json)
✅ Bulk coefficient/unit/range change feature

Analog Output — Function Generator (AO0 / AO1)

✅ Two independent function-generator channels
✅ Waveforms: Sine, Square, Triangle, Sawtooth, DC
✅ Adjustable frequency, amplitude, offset, and phase per channel
✅ Live waveform preview with auto-scaling and ±10 V clip warning
✅ One-click output toggle (button changes color while active)
✅ Runs concurrently with input monitoring

Frequency Response (Bode) Measurement

✅ AO0 step-sweep excitation (log or linear sweep)
✅ Selectable input reference (AO0 command or any AI channel, e.g. a motor-driver command signal) and response (any AI channel)
✅ Per-frequency single-sine least-squares fit → gain (dB) and phase (deg)
✅ Configurable start/stop frequency, points, amplitude, settle time, and measurement cycles
✅ Results saved to Excel (data + Bode diagram image)
✅ Separate Bode window with adjustable graph format (title, font family, font sizes, line width, marker size, grid) and PNG/PDF/SVG export

Digital I/O (P0.0–P0.7)

✅ Per-line mode selection: Input (cyan) or Output (orange)
✅ Output lines: click to toggle, yellow (OFF) → green (ON)
✅ Input lines: continuously monitored, yellow (LOW) / green (HIGH)
✅ DO/DI tasks rebuilt automatically so a line is never used as input and output at the same time


Note on USB-6002 limits: the AO update rate is 5 kS/s, so the practical
function-generator / Bode upper frequency is roughly 500 Hz. Digital I/O is
software-timed TTL (0/3.3 V); use a relay or transistor stage to drive loads.

Requirements

Python 3.8+
NI USB-6002
NI-DAQmx Driver

Installation

Install the NI-DAQmx Driver
https://www.ni.com/en-us/support/downloads/drivers/download.ni-daqmx.html
Install the Python packages

   pip install nidaqmx matplotlib pandas numpy pillow pywin32 openpyxl
Usage
python usb6002_configurable.py
Configuration
A config.json file is automatically generated on first launch. You can
configure channel names, conversion factors, units, and Y-axis ranges through
the configuration editor. Active-channel selections are preserved between
sessions.
License
MIT License
Author
Tsutsumi Hirotaka
