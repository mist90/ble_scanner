#!/usr/bin/env python3
import sys
import asyncio
import platform
import argparse
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QLabel, 
                            QMessageBox, QTabWidget, QSplitter, QLineEdit, QDialog,
                            QFormLayout, QSpinBox, QDialogButtonBox, QTextEdit, QHeaderView)
from PyQt5.QtCore import Qt, QTimer, QDateTime
from bleak_worker import BleakWorker
from device_tab import DeviceTab

# Global debug flag
DEBUG = False

def debug_print(*args, **kwargs):
    """Print only if DEBUG is enabled"""
    if DEBUG:
        print(*args, **kwargs)



class BLEScanner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLE Scanner")
        self.resize(1000, 700)
        
        # Initialize BLE worker
        self.ble_worker = BleakWorker()
        self.ble_worker.devices_updated.connect(self.update_device_list)
        self.ble_worker.advertisement_received.connect(self.process_advertisement)
        self.ble_worker.connection_updated.connect(self.update_connection_status)
        
        # Dictionary to store advertisement data
        self.device_advertisements = {}  # address -> advertisement_data
        self.ble_worker.services_updated.connect(self.update_services)
        self.ble_worker.characteristic_read.connect(self.update_characteristic_value)
        self.ble_worker.characteristic_written.connect(self.handle_write_response)
        self.ble_worker.notification_received.connect(self.handle_notification)
        self.ble_worker.error_occurred.connect(self.show_error)
        self.ble_worker.connection_status_checked.connect(self.handle_connection_check)
        self.ble_worker.start()
        
        # Dictionary to track connected devices
        self.connected_devices = {}  # address -> client
        
        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Splitter for device list and device tabs
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)
        
        # Device list and advertisement data in a vertical splitter
        device_widget = QWidget()
        device_layout = QVBoxLayout(device_widget)
        device_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scanning controls
        scan_layout = QHBoxLayout()
        self.scan_button = QPushButton("Start Scan")
        self.scan_button.clicked.connect(self.toggle_scan)
        scan_layout.addWidget(self.scan_button)
        
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.show_settings_dialog)
        scan_layout.addWidget(self.settings_button)
        
        device_layout.addLayout(scan_layout)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        
        self.mac_filter = QLineEdit()
        self.mac_filter.setPlaceholderText("MAC Address")
        self.mac_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.mac_filter)
        
        self.rssi_filter = QLineEdit()
        self.rssi_filter.setPlaceholderText("Min RSSI (e.g. -70)")
        self.rssi_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.rssi_filter)
        
        self.adv_filter = QLineEdit()
        self.adv_filter.setPlaceholderText("Adv Data (hex)")
        self.adv_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.adv_filter)
        
        device_layout.addLayout(filter_layout)
        
        # Create a vertical splitter for device list and advertisement data
        device_splitter = QSplitter(Qt.Vertical)
        
        # Device list panel
        device_list_widget = QWidget()
        device_list_layout = QVBoxLayout(device_list_widget)
        device_list_layout.setContentsMargins(0, 0, 0, 0)
        
        device_list_layout.addWidget(QLabel("Discovered Devices:"))
        
        # Create table widget for devices
        self.device_list = QTableWidget()
        self.device_list.setColumnCount(4)
        self.device_list.setHorizontalHeaderLabels(["MAC Address", "Name", "RSSI", "Adv Period"])
        self.device_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_list.setSelectionMode(QTableWidget.SingleSelection)
        self.device_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.device_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.device_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.device_list.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        device_list_layout.addWidget(self.device_list)
        
        device_splitter.addWidget(device_list_widget)
        
        # Advertisement data panel
        adv_data_widget = QWidget()
        adv_layout = QVBoxLayout(adv_data_widget)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        
        adv_layout.addWidget(QLabel("Raw Advertisement Data:"))
        self.adv_data_text = QTextEdit()
        self.adv_data_text.setReadOnly(True)
        self.adv_data_text.setPlaceholderText("Select a device to view raw advertisement data")
        adv_layout.addWidget(self.adv_data_text)
        
        device_splitter.addWidget(adv_data_widget)
        
        # Set initial sizes - make device list larger than advertisement data
        device_splitter.setSizes([700, 300])
        
        device_layout.addWidget(device_splitter)
        
        # Connect button
        connect_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_to_device)
        self.connect_button.setEnabled(False)
        connect_layout.addWidget(self.connect_button)
        device_layout.addLayout(connect_layout)
        
        # Device selection handler
        self.device_list.itemSelectionChanged.connect(self.device_selected)
        
        splitter.addWidget(device_widget)
        
        # Device tabs
        self.device_tabs = QTabWidget()
        self.device_tabs.setTabsClosable(True)
        self.device_tabs.tabCloseRequested.connect(self.close_device_tab)
        splitter.addWidget(self.device_tabs)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Settings
        self.scan_time = 30000  # 30 seconds by default
        self.connection_timeout = 10000  # 10 seconds by default
        
        # State variables
        self.scanning = False
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.stop_scan)
        self.current_device = None
        self.device_tabs_map = {}  # Maps address -> tab index
        self.adv_timestamps = {}   # Maps address -> list of timestamps
        self.adv_periods = {}      # Maps address -> calculated period in ms
        
    def toggle_scan(self):
        if not self.scanning:
            self.start_scan()
        else:
            self.stop_scan()
    
    def start_scan(self):
        self.scanning = True
        self.scan_button.setText("Stop Scan")
        self.device_list.clear()
        # Clear advertisement timestamps and periods for a fresh scan
        self.adv_timestamps = {}
        self.adv_periods = {}
        self.statusBar().showMessage("Scanning for devices...")
        self.ble_worker.scan_devices(self.scan_time)
        self.scan_timer.start(self.scan_time)  # Auto-stop after configured time
    
    def stop_scan(self):
        self.scanning = False
        self.scan_button.setText("Start Scan")
        self.scan_timer.stop()
        self.statusBar().showMessage("Scan stopped")
    
    def process_advertisement(self, device, advertisement_data):
        """Process each advertisement as it's received"""
        if not self.scanning:
            return
            
        # Update device list during scanning
        if not hasattr(self, 'all_devices'):
            self.all_devices = []
            
        # Check if device is already in the list
        device_found = False
        for existing_device in self.all_devices:
            if hasattr(existing_device, 'address') and hasattr(device, 'address') and existing_device.address == device.address:
                device_found = True
                break
        
        # Add device if not already in the list
        if not device_found:
            self.all_devices.append(device)
            self.apply_filters()
            
        address = device.address if hasattr(device, 'address') else str(device)
        current_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        
        # No need to store advertisement data on device object anymore
        
        # Store advertisement data
        self.device_advertisements[address] = advertisement_data
        
        # Update advertisement timestamps
        if address not in self.adv_timestamps:
            self.adv_timestamps[address] = []
        
        self.adv_timestamps[address].append(current_time)
        
        # Keep all timestamps (commented code previously limited to 10)
        
        # Calculate period if we have at least 2 timestamps
        if len(self.adv_timestamps[address]) >= 2:
            timestamps = self.adv_timestamps[address]
            periods = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
            min_period = min(periods)
            self.adv_periods[address] = min_period
        
        # Always update the device in the list for each advertisement
        self.update_device_in_list(address)
        # Apply filters to refresh the list
        self.apply_filters()
            
        # Update advertisement data display if this is the currently selected device
        if self.current_device and hasattr(self.current_device, 'address') and self.current_device.address == address:
            current_item = self.device_list.currentItem()
            if current_item is not None:
                self.device_selected(current_item)
    
    def update_device_in_list(self, address):
        """Update a specific device in the list with new advertisement period"""
        # Find the row with this device
        for row in range(self.device_list.rowCount()):
            item = self.device_list.item(row, 0)
            if item and item.data(Qt.UserRole) and hasattr(item.data(Qt.UserRole), 'address') and item.data(Qt.UserRole).address == address:
                device = item.data(Qt.UserRole)
                
                # Get the device properties
                name = device.name if hasattr(device, 'name') else "Unknown Device"
                
                # Get RSSI
                device_rssi = None
                if address in self.device_advertisements:
                    device_rssi = self.device_advertisements[address].rssi
                rssi_display = str(device_rssi) if device_rssi is not None else "N/A"
                
                # Get advertisement period
                adv_period = "N/A"
                if address in self.adv_periods:
                    adv_period = f"{self.adv_periods[address]:.0f} ms"
                
                # Update the cells
                self.device_list.item(row, 1).setText(name)
                self.device_list.item(row, 2).setText(rssi_display)
                self.device_list.item(row, 3).setText(adv_period)
                break
    
    def update_device_list(self, devices):
        """Update the device list with all discovered devices"""
        self.all_devices = devices
        self.apply_filters()
    
    def apply_filters(self):
        if not hasattr(self, 'all_devices'):
            return
            
        self.device_list.setRowCount(0)  # Clear the table
        # Ensure column headers are set correctly
        self.device_list.setHorizontalHeaderLabels(["MAC Address", "Name", "RSSI", "Adv Period"])
        mac_filter = self.mac_filter.text().lower()
        
        try:
            rssi_filter = int(self.rssi_filter.text()) if self.rssi_filter.text() else None
        except ValueError:
            rssi_filter = None
            
        adv_filter = self.adv_filter.text().strip().lower().replace(" ", "")
        
        row = 0
        for device in self.all_devices:
            # Get device properties
            name = device.name if hasattr(device, 'name') else "Unknown Device"
            address = device.address if hasattr(device, 'address') else str(device)
            
            # Get RSSI from advertisement data
            device_rssi = None
            if address in self.device_advertisements:
                device_rssi = self.device_advertisements[address].rssi
            
            # Apply MAC filter
            if mac_filter and mac_filter not in address.lower():
                continue
                
            # Apply RSSI filter
            if rssi_filter is not None and (device_rssi is None or device_rssi < rssi_filter):
                continue

            # Apply advertisement data filter
            if adv_filter:
                mfg_hex = ""
                
                # Get manufacturer data from advertisement_data
                if address in self.device_advertisements and hasattr(self.device_advertisements[address], 'manufacturer_data'):
                    for company_code, data in self.device_advertisements[address].manufacturer_data.items():
                        if isinstance(data, (bytes, bytearray)):
                            mfg_hex += ''.join(f'{b:02x}' for b in data)
                
                if adv_filter not in mfg_hex:
                    continue
            
            # Device passed all filters, add to table
            self.device_list.insertRow(row)
            
            # MAC Address
            mac_item = QTableWidgetItem(address)
            mac_item.setData(Qt.UserRole, device)
            self.device_list.setItem(row, 0, mac_item)
            
            # Name
            name_item = QTableWidgetItem(name)
            self.device_list.setItem(row, 1, name_item)
            
            # RSSI
            rssi_display = str(device_rssi) if device_rssi is not None else "N/A"
            rssi_item = QTableWidgetItem(rssi_display)
            self.device_list.setItem(row, 2, rssi_item)
            
            # Advertisement Period
            adv_period = "N/A"
            if address in self.adv_periods:
                adv_period = f"{self.adv_periods[address]:.0f} ms"
            period_item = QTableWidgetItem(adv_period)
            self.device_list.setItem(row, 3, period_item)
            
            # Add tooltip to all cells in the row
            tooltip = ""
            if address in self.device_advertisements and hasattr(self.device_advertisements[address], 'manufacturer_data'):
                for company_code, data in self.device_advertisements[address].manufacturer_data.items():
                    if isinstance(data, (bytes, bytearray)):
                        tooltip += f"Mfg: 0x{company_code:04x} Data: {' '.join([f'{b:02X}' for b in data])}\n"
            
            if tooltip:
                for col in range(4):
                    self.device_list.item(row, col).setToolTip(tooltip)
            
            row += 1
    
    def device_selected(self):
        selected_rows = self.device_list.selectedItems()
        if not selected_rows:
            return
            
        # Get the first selected row
        row = selected_rows[0].row()
        
        # Get the device from the first cell of the selected row
        item = self.device_list.item(row, 0)
        if not item:
            return
            
        self.current_device = item.data(Qt.UserRole)
        self.connect_button.setEnabled(True)
        
        # Update advertisement data display
        device = self.current_device
        if device:
            address = device.address if hasattr(device, 'address') else str(device)
            name = device.name if hasattr(device, 'name') else "Unknown Device"
            
            adv_text = f"Device: {name} ({address})\n\n"
            
            # Add advertisement period if available
            if address in self.adv_periods:
                adv_text += f"Advertisement Period: {self.adv_periods[address]:.0f} ms\n\n"
            
            # Display specific advertisement data fields
            if address in self.device_advertisements:
                adv_data = self.device_advertisements[address]
                
                # RSSI
                if hasattr(adv_data, 'rssi'):
                    adv_text += f"RSSI: {adv_data.rssi} dBm\n\n"
                
                # TX Power
                if hasattr(adv_data, 'tx_power'):
                    tx_power = adv_data.tx_power
                    if tx_power is not None:
                        adv_text += f"TX Power: {tx_power} dBm\n\n"
                
                # Manufacturer Data
                if hasattr(adv_data, 'manufacturer_data') and adv_data.manufacturer_data:
                    adv_text += "Manufacturer Data:\n"
                    for company_code, data in adv_data.manufacturer_data.items():
                        if isinstance(data, (bytes, bytearray)):
                            hex_data = ' '.join([f'{b:02X}' for b in data])
                            adv_text += f"  Company: 0x{company_code:04X}\n  Data: {hex_data}\n\n"
                
                # Service UUIDs
                if hasattr(adv_data, 'service_uuids') and adv_data.service_uuids:
                    adv_text += "Service UUIDs:\n"
                    for uuid in adv_data.service_uuids:
                        adv_text += f"  {uuid}\n"
                    adv_text += "\n"
                
                # Service Data
                if hasattr(adv_data, 'service_data') and adv_data.service_data:
                    adv_text += "Service Data:\n"
                    for uuid, data in adv_data.service_data.items():
                        if isinstance(data, (bytes, bytearray)):
                            hex_data = ' '.join([f'{b:02X}' for b in data])
                            adv_text += f"  {uuid}: {hex_data}\n"
                    adv_text += "\n"
                
                # Platform Data
                if hasattr(adv_data, 'platform_data') and adv_data.platform_data:
                    adv_text += "Platform Data:\n"
                    # Check if platform_data is a dictionary
                    if isinstance(adv_data.platform_data, dict):
                        for key, value in adv_data.platform_data.items():
                            adv_text += f"  {key}: {value}\n"
                    else:
                        # Handle case where platform_data is not a dictionary
                        adv_text += f"  {adv_data.platform_data}\n"
                    adv_text += "\n"
                
                # Display raw AdvertisementData content
                adv_text += "Raw AdvertisementData:\n"
                
                # Display all attributes of the AdvertisementData object
                for attr_name in dir(adv_data):
                    if not attr_name.startswith('_') and not callable(getattr(adv_data, attr_name)):
                        try:
                            attr_value = getattr(adv_data, attr_name)
                            
                            # Format the value based on its type
                            if isinstance(attr_value, (bytes, bytearray)):
                                formatted_value = ' '.join([f'{b:02X}' for b in attr_value])
                            elif isinstance(attr_value, dict):
                                # Format dictionaries (like manufacturer_data and service_data)
                                formatted_value = "{\n"
                                for k, v in attr_value.items():
                                    if isinstance(v, (bytes, bytearray)):
                                        v_str = ' '.join([f'{b:02X}' for b in v])
                                    else:
                                        v_str = str(v)
                                    formatted_value += f"    {k}: {v_str}\n"
                                formatted_value += "  }"
                            elif isinstance(attr_value, list):
                                # Format lists (like service_uuids)
                                formatted_value = "[\n"
                                for item in attr_value:
                                    formatted_value += f"    {item}\n"
                                formatted_value += "  ]"
                            else:
                                formatted_value = str(attr_value)
                                
                            adv_text += f"  {attr_name}: {formatted_value}\n\n"
                        except Exception as e:
                            adv_text += f"  {attr_name}: Error accessing value: {str(e)}\n\n"
            
            self.adv_data_text.setText(adv_text)
        else:
            self.adv_data_text.clear()
    
    def connect_to_device(self):
        if self.current_device:
            device = self.current_device
            address = device.address if hasattr(device, 'address') else str(device)
            
            # Check if device tab is already open
            if address in self.device_tabs_map:
                # Switch to the existing tab
                self.device_tabs.setCurrentIndex(self.device_tabs_map[address])
                
                # If not connected, reconnect
                if address not in self.connected_devices:
                    self.statusBar().showMessage(f"Reconnecting to {device.name if hasattr(device, 'name') else 'Unknown Device'}...")
                    self.ble_worker.connect_device(address, self.connection_timeout)
                return
            
            # Create a new tab for this device
            device_tab = DeviceTab(device)
            
            # Connect the tab's action signals to our methods
            # Create proper method references that capture the current address
            current_address = address  # Create a local variable to capture the current value
            
            # Create handlers with proper binding to the address
            def read_handler():
                if device_tab.current_characteristic:
                    char_uuid = str(device_tab.current_characteristic.uuid)
                    debug_print(f"Reading characteristic {char_uuid} on {current_address}")
                    self.statusBar().showMessage(f"Reading characteristic {char_uuid} on {current_address}...")
                    try:
                        self.ble_worker.read_characteristic(current_address, char_uuid)
                        # Set a timeout to clear the status if no response is received
                        QTimer.singleShot(5000, lambda: self.check_read_timeout(current_address, char_uuid))
                    except Exception as e:
                        self.statusBar().showMessage(f"Error reading characteristic: {str(e)}")
            
            def write_handler():
                self.write_characteristic(current_address)
                
            def notify_handler():
                self.toggle_notifications(current_address)
            
            # Connect the buttons directly to our handlers
            device_tab.read_button.clicked.connect(read_handler)
            device_tab.write_button.clicked.connect(write_handler)
            device_tab.notify_button.clicked.connect(notify_handler)
            
            # Add the tab
            device_name = device.name if hasattr(device, 'name') else "Unknown Device"
            tab_index = self.device_tabs.addTab(device_tab, f"{device_name} ({address})")
            self.device_tabs_map[address] = tab_index
            self.device_tabs.setCurrentIndex(tab_index)
            
            # Start connection
            self.statusBar().showMessage(f"Connecting to {device_name}...")
            self.ble_worker.connect_device(address, self.connection_timeout)
    
    def close_device_tab(self, index):
        # Get the tab widget
        tab_widget = self.device_tabs.widget(index)
        
        # Find the address for this tab
        address = None
        for addr, idx in self.device_tabs_map.items():
            if idx == index:
                address = addr
                break
        
        if address:
            # Disconnect the device if it's connected
            if address in self.connected_devices:
                self.ble_worker.disconnect_device(address)
            
            # Remove from our maps
            del self.device_tabs_map[address]
            
            # Update indices for tabs that come after this one
            for addr, idx in self.device_tabs_map.items():
                if idx > index:
                    self.device_tabs_map[addr] = idx - 1
            
            # Remove the tab
            self.device_tabs.removeTab(index)
    
    def update_connection_status(self, connected, address, client):
        if address in self.device_tabs_map:
            tab_index = self.device_tabs_map[address]
            device_tab = self.device_tabs.widget(tab_index)
            
            if connected:
                self.statusBar().showMessage(f"Connected to {address}")
                self.connected_devices[address] = client
                device_tab.set_connected_state(True)
                # Start checking connection status for this device
                self.check_connection_status(address)
            else:
                self.statusBar().showMessage(f"Disconnected from {address}")
                if address in self.connected_devices:
                    del self.connected_devices[address]
                device_tab.set_connected_state(False)
    
    def update_services(self, address, services):
        if address in self.device_tabs_map:
            tab_index = self.device_tabs_map[address]
            device_tab = self.device_tabs.widget(tab_index)
            device_tab.update_services(services)
    
    def read_characteristic(self, address):
        """Read the selected characteristic on the specified device - used for direct calls from main window"""
        if address in self.device_tabs_map:
            tab_index = self.device_tabs_map[address]
            device_tab = self.device_tabs.widget(tab_index)
            
            if device_tab.current_characteristic:
                char_uuid = str(device_tab.current_characteristic.uuid)
                self.statusBar().showMessage(f"Reading characteristic {char_uuid} on {address}...")
                debug_print(f"Main window reading characteristic {char_uuid}")  # Debug output
                try:
                    self.ble_worker.read_characteristic(address, char_uuid)
                    # Set a timeout to clear the status if no response is received
                    QTimer.singleShot(5000, lambda: self.check_read_timeout(address, char_uuid))
                except Exception as e:
                    self.statusBar().showMessage(f"Error reading characteristic: {str(e)}")
    
    def check_read_timeout(self, address, char_uuid):
        """Check if a read operation has timed out"""
        current_status = self.statusBar().currentMessage()
        if current_status == f"Reading characteristic {char_uuid} on {address}...":
            self.statusBar().showMessage(f"Read operation timed out for {char_uuid} on {address}")
    
    def update_characteristic_value(self, address, char_uuid, value):
        """Update the displayed value for a characteristic"""
        debug_print(f"Received value for {char_uuid} on {address}: {value}")  # Debug output
        if address in self.device_tabs_map:
            tab_index = self.device_tabs_map[address]
            device_tab = self.device_tabs.widget(tab_index)
            debug_print(f"Updating tab {tab_index} for device {address}")  # Debug output
            device_tab.update_characteristic_value(char_uuid, value)
            
            # Update status bar
            hex_value = " ".join([f"{b:02X}" for b in value])
            self.statusBar().showMessage(f"Read complete for {char_uuid} on {address}: {hex_value}")
    
    def write_characteristic(self, address):
        """Write to the selected characteristic on the specified device"""
        if address in self.device_tabs_map:
            tab_index = self.device_tabs_map[address]
            device_tab = self.device_tabs.widget(tab_index)
            
            if not device_tab.current_characteristic:
                return
                
            try:
                # Parse hex input
                hex_text = device_tab.write_input.text().strip()
                if not hex_text:
                    QMessageBox.warning(self, "Input Error", "Please enter a hex value")
                    return
                    
                # Convert hex string to bytes
                hex_values = hex_text.split()
                data = bytearray([int(h, 16) for h in hex_values])
                
                char_uuid = str(device_tab.current_characteristic.uuid)
                properties = device_tab.current_characteristic.properties if hasattr(device_tab.current_characteristic, 'properties') else []
                with_response = "write" in properties
                
                self.statusBar().showMessage(f"Writing to characteristic {char_uuid} on {address}...")
                self.ble_worker.write_characteristic(address, char_uuid, data, with_response)
                
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Invalid hex format. Use space-separated hex values (e.g., 01 02 03)")
    
    def handle_write_response(self, address, char_uuid, success):
        """Handle the response from a write operation"""
        if success:
            self.statusBar().showMessage(f"Write to {char_uuid} on {address} successful")
        else:
            self.statusBar().showMessage(f"Write to {char_uuid} on {address} failed")
    
    def toggle_notifications(self, address):
        """Toggle notifications for the selected characteristic on the specified device"""
        if address in self.device_tabs_map:
            tab_index = self.device_tabs_map[address]
            device_tab = self.device_tabs.widget(tab_index)
            
            if not device_tab.current_characteristic:
                return
                
            char_uuid = str(device_tab.current_characteristic.uuid)
            
            if char_uuid in device_tab.notification_active:
                # Unsubscribe
                self.ble_worker.stop_notify(address, char_uuid)
                device_tab.notification_active.pop(char_uuid, None)
                device_tab.notify_button.setText("Subscribe")
                self.statusBar().showMessage(f"Unsubscribed from {char_uuid} on {address}")
            else:
                # Subscribe
                self.ble_worker.start_notify(address, char_uuid)
                device_tab.notification_active[char_uuid] = True
                device_tab.notify_button.setText("Unsubscribe")
                self.statusBar().showMessage(f"Subscribed to {char_uuid} on {address}")
    
    def handle_notification(self, address, char_uuid, data):
        """Handle a notification from a characteristic"""
        if address in self.device_tabs_map:
            tab_index = self.device_tabs_map[address]
            device_tab = self.device_tabs.widget(tab_index)
            device_tab.handle_notification(char_uuid, data)
    
    def try_decode_ascii(self, data):
        """Try to decode binary data as ASCII or UTF-8"""
        try:
            return data.decode('ascii')
        except:
            try:
                return data.decode('utf-8')
            except:
                return "(not text)"
    
    def show_error(self, message):
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "Error", message)
    
    def check_connection_status(self, address=None):
        """Check the connection status of a device or all devices"""
        if address:
            # Check a specific device
            if address in self.connected_devices:
                self.ble_worker.check_connection_status(address)
        else:
            # Check all connected devices
            for addr in list(self.connected_devices.keys()):
                self.ble_worker.check_connection_status(addr)
                
        # Schedule the next check for all devices
        QTimer.singleShot(2000, lambda: self.check_connection_status())
    
    def handle_connection_check(self, address, is_connected):
        """Handle the result of a connection status check"""
        if address in self.device_tabs_map:
            tab_index = self.device_tabs_map[address]
            device_tab = self.device_tabs.widget(tab_index)
            
            # If we think we're connected but we're actually not
            if not is_connected and device_tab.connected:
                self.statusBar().showMessage(f"Device {address} disconnected unexpectedly")
                if address in self.connected_devices:
                    del self.connected_devices[address]
                device_tab.set_connected_state(False)
    
    def show_settings_dialog(self):
        """Show the settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setMinimumWidth(300)
        
        layout = QFormLayout(dialog)
        
        # Scan time setting
        scan_time_spin = QSpinBox(dialog)
        scan_time_spin.setRange(1, 60)
        scan_time_spin.setValue(self.scan_time // 1000)  # Convert ms to seconds
        scan_time_spin.setSuffix(" seconds")
        layout.addRow("Scan Time:", scan_time_spin)
        
        # Connection timeout setting
        conn_timeout_spin = QSpinBox(dialog)
        conn_timeout_spin.setRange(1, 60)
        conn_timeout_spin.setValue(self.connection_timeout // 1000)  # Convert ms to seconds
        conn_timeout_spin.setSuffix(" seconds")
        layout.addRow("Connection Timeout:", conn_timeout_spin)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addRow(button_box)
        
        # Show dialog and process result
        if dialog.exec_() == QDialog.Accepted:
            self.scan_time = scan_time_spin.value() * 1000  # Convert seconds to ms
            self.connection_timeout = conn_timeout_spin.value() * 1000  # Convert seconds to ms
            self.statusBar().showMessage(f"Settings updated: Scan time: {self.scan_time//1000}s, Connection timeout: {self.connection_timeout//1000}s")
    
    def closeEvent(self, event):
        # Disconnect all devices
        for address in list(self.connected_devices.keys()):
            try:
                self.ble_worker.disconnect_device(address)
            except:
                pass
            
        # Clean up BLE worker
        try:
            self.ble_worker.quit()
            self.ble_worker.wait(1000)  # Wait with timeout
        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            # Force quit if needed
            if self.ble_worker.isRunning():
                self.ble_worker.terminate()
            event.accept()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='BLE Scanner')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args, remaining = parser.parse_known_args()
    
    # Update the global DEBUG flag
    DEBUG = args.debug
    
    # Update sys.argv to remove our custom arguments
    sys.argv = [sys.argv[0]] + remaining
    
    # Fix for macOS event loop
    if platform.system() == 'Darwin':
        # Set the event loop policy to use the asyncio event loop
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    
    app = QApplication(sys.argv)
    window = BLEScanner()
    window.show()
    sys.exit(app.exec_())
