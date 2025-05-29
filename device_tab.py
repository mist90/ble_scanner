#!/usr/bin/env python3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QTextEdit, QTreeWidget, QTreeWidgetItem,
                            QTabWidget, QSplitter, QLineEdit)
from PyQt5.QtCore import Qt, QTimer, QDateTime

class DeviceTab(QWidget):
    """Widget representing a connected device tab"""
    
    def __init__(self, device, parent=None):
        super().__init__(parent)
        self.device = device
        self.address = device.address if hasattr(device, 'address') else str(device)
        self.name = device.name if hasattr(device, 'name') else "Unknown Device"
        self.connected = False
        self.current_characteristic = None
        self.notification_active = {}
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Create splitter for services and details
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)
        
        # Services and characteristics tree
        self.service_tree = QTreeWidget()
        self.service_tree.setHeaderLabels(["Services & Characteristics", "UUID", "Properties"])
        self.service_tree.setColumnWidth(0, 300)
        self.service_tree.setColumnWidth(1, 300)
        self.service_tree.itemClicked.connect(self.characteristic_selected)
        splitter.addWidget(self.service_tree)
        
        # Characteristic details
        details_widget = QTabWidget()
        
        # Read/Write tab
        rw_tab = QWidget()
        rw_layout = QVBoxLayout(rw_tab)
        
        self.value_display = QTextEdit()
        self.value_display.setReadOnly(True)
        self.value_display.setPlaceholderText("Characteristic value will be displayed here")
        
        rw_layout.addWidget(QLabel("Value:"))
        rw_layout.addWidget(self.value_display)
        
        write_layout = QHBoxLayout()
        self.write_input = QLineEdit()
        self.write_input.setPlaceholderText("Enter hex value (e.g., 01 02 03)")
        write_layout.addWidget(self.write_input)
        
        self.read_button = QPushButton("Read")
        self.read_button.setEnabled(False)
        write_layout.addWidget(self.read_button)
        
        self.write_button = QPushButton("Write")
        self.write_button.setEnabled(False)
        write_layout.addWidget(self.write_button)
        
        self.notify_button = QPushButton("Subscribe")
        self.notify_button.setEnabled(False)
        write_layout.addWidget(self.notify_button)
        
        rw_layout.addLayout(write_layout)
        
        # Notifications tab
        notify_tab = QWidget()
        notify_layout = QVBoxLayout(notify_tab)
        
        self.notification_log = QTextEdit()
        self.notification_log.setReadOnly(True)
        notify_layout.addWidget(self.notification_log)
        
        clear_button = QPushButton("Clear Log")
        clear_button.clicked.connect(self.notification_log.clear)
        notify_layout.addWidget(clear_button)
        
        # Add tabs
        details_widget.addTab(rw_tab, "Read/Write")
        details_widget.addTab(notify_tab, "Notifications")
        
        splitter.addWidget(details_widget)
        
        # Set initial state
        self.set_connected_state(False)
    
    def set_connected_state(self, connected):
        """Update UI elements based on connection state"""
        self.connected = connected
        self.service_tree.setEnabled(connected)
        self.write_input.setEnabled(connected)
        self.read_button.setEnabled(connected and self.current_characteristic is not None)
        self.write_button.setEnabled(connected and self.current_characteristic is not None)
        self.notify_button.setEnabled(connected and self.current_characteristic is not None)
    
    def update_services(self, services):
        """Update the services tree with the device's services"""
        self.service_tree.clear()
        
        for uuid, service in services.items():
            service_item = QTreeWidgetItem(self.service_tree)
            service_item.setText(0, f"Service: {service.description if hasattr(service, 'description') else ''}")
            service_item.setText(1, str(service.uuid))
            service_item.setExpanded(True)
            
            for char in service.characteristics:
                char_item = QTreeWidgetItem(service_item)
                char_item.setText(0, f"Characteristic: {char.description if hasattr(char, 'description') else ''}")
                char_item.setText(1, str(char.uuid))
                
                props = []
                # Handle properties as a list
                if hasattr(char, 'properties'):
                    properties = char.properties
                    if "read" in properties:
                        props.append("Read")
                    if "write" in properties:
                        props.append("Write")
                    if "write-without-response" in properties:
                        props.append("Write No Response")
                    if "notify" in properties:
                        props.append("Notify")
                    if "indicate" in properties:
                        props.append("Indicate")
                
                char_item.setText(2, ", ".join(props))
                char_item.setData(0, Qt.UserRole, char)
    
    def characteristic_selected(self, item, column=0):
        """Handle characteristic selection in the tree"""
        # Check if this is a characteristic (not a service)
        char_data = item.data(0, Qt.UserRole)
        if char_data:
            self.current_characteristic = char_data
            
            # Enable/disable buttons based on properties
            properties = char_data.properties if hasattr(char_data, 'properties') else []
            self.read_button.setEnabled(self.connected and "read" in properties)
            self.write_button.setEnabled(
                self.connected and (
                    "write" in properties or 
                    "write-without-response" in properties
                )
            )
            
            can_notify = (
                "notify" in properties or 
                "indicate" in properties
            )
            self.notify_button.setEnabled(self.connected and can_notify)
            
            # Update notify button text
            char_uuid = str(char_data.uuid)
            if char_uuid in self.notification_active:
                self.notify_button.setText("Unsubscribe")
            else:
                self.notify_button.setText("Subscribe")
    
    def read_characteristic(self):
        """Request to read the selected characteristic"""
        if self.current_characteristic:
            # This is a placeholder that will be overridden by the main window
            # Debug output will be handled by the main window
            pass
            # This method will be replaced at runtime
    
    def write_characteristic(self):
        """Request to write to the selected characteristic"""
        # This will be implemented by the main window
        pass
    
    def toggle_notifications(self):
        """Toggle notifications for the selected characteristic"""
        # This will be implemented by the main window
        pass
    
    def update_characteristic_value(self, char_uuid, value):
        """Update the displayed value for a characteristic"""
        # Debug output handled by main window
        if self.current_characteristic and str(self.current_characteristic.uuid) == char_uuid:
            # Display as hex
            hex_value = " ".join([f"{b:02X}" for b in value])
            text_value = f"Hex: {hex_value}\n\nASCII: {self.try_decode_ascii(value)}\n\nInt: {int.from_bytes(value, byteorder='little') if len(value) <= 8 else 'Too long'}"
            # Debug output handled by main window
            self.value_display.setText(text_value)
        else:
            # Debug output handled by main window
            pass
    
    def handle_notification(self, char_uuid, data):
        """Handle a notification from a characteristic"""
        hex_value = " ".join([f"{b:02X}" for b in data])
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss.zzz")
        
        self.notification_log.append(f"[{timestamp}] {char_uuid}:\nHex: {hex_value}\nASCII: {self.try_decode_ascii(data)}\n")
        
        # If this is the currently selected characteristic, update the value display too
        if self.current_characteristic and str(self.current_characteristic.uuid) == char_uuid:
            self.update_characteristic_value(char_uuid, data)
    
    def try_decode_ascii(self, data):
        """Try to decode binary data as ASCII or UTF-8"""
        try:
            return data.decode('ascii')
        except:
            try:
                return data.decode('utf-8')
            except:
                return "(not text)"
