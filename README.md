# ble_scanner
Crossplatform BLE scanner

<img width="1916" height="1002" alt="image" src="https://github.com/user-attachments/assets/2ca039b2-1f7a-4aa2-a90a-eb44a613228e" />

## Features

- **Device Discovery** — scan for nearby BLE devices with configurable scan duration (up to 30 minutes)
- **Real-time Filtering** — filter devices by name, MAC address, RSSI level, or advertisement data (hex)
- **Advertisement Data** — view raw advertisement data including manufacturer data, service UUIDs, TX power, and advertisement period
- **Device Connection** — connect to multiple BLE devices simultaneously in separate tabs
- **Service Browser** — explore GATT services and characteristics with properties display
- **Read/Write** — read and write characteristic values (hex format)
- **Notifications** — subscribe to characteristic notifications with timestamped logging
- **Cross-platform** — works on Windows, macOS, and Linux

## Requirements
python3
pip install bleak PyQt5

# Run
./ble_scanner.py

#    MIT License
  Author: Mikhail Tegin, 2025
  ropewalker@yandex-team.ru

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
