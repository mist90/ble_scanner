#!/usr/bin/env python3
import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

class BleakWorker(QThread):
    """Worker thread for handling BLE operations"""
    devices_updated = pyqtSignal(list)
    advertisement_received = pyqtSignal(object, object)  # device, advertisement_data
    connection_updated = pyqtSignal(bool, str, object)  # connected, address, client
    services_updated = pyqtSignal(str, dict)  # address, services
    characteristic_read = pyqtSignal(str, str, bytearray)  # address, char_uuid, value
    characteristic_written = pyqtSignal(str, str, bool)  # address, char_uuid, success
    notification_received = pyqtSignal(str, str, bytearray)  # address, char_uuid, data
    error_occurred = pyqtSignal(str)
    connection_status_checked = pyqtSignal(str, bool)  # address, is_connected
    
    def __init__(self):
        super().__init__()
        self.command_queue = asyncio.Queue()
        self.clients = {}  # Dictionary of address -> BleakClient
        self.notification_handlers = {}  # Dictionary of address -> {char_uuid -> handler}
        self.loop = None
        self.connection_check_timer = None
        
    async def notification_handler(self, address, characteristic, data):
        self.notification_received.emit(address, str(characteristic), data)
        
    async def run_ble_loop(self):
        while True:
            command, args = await self.command_queue.get()
            
            try:
                if command == "scan":
                    # Use scanner with callback to get all advertisements
                    scan_time = args[0] if args else 5.0  # Default to 5 seconds if not specified
                    scan_time_seconds = scan_time / 1000.0 if scan_time > 100 else scan_time  # Convert from ms if needed
                    
                    devices_dict = {}
                    
                    def detection_callback(device, advertisement_data):
                        # Store device in dictionary
                        if device.address not in devices_dict:
                            devices_dict[device.address] = device
                        # Emit signal for each advertisement
                        self.advertisement_received.emit(device, advertisement_data)
                    
                    scanner = BleakScanner(detection_callback=detection_callback)
                    await scanner.start()
                    await asyncio.sleep(scan_time_seconds)
                    await scanner.stop()
                    
                    # We don't need to emit devices_updated here since we're updating 
                    # the list with each advertisement via advertisement_received
                    # devices = list(devices_dict.values())
                    # self.devices_updated.emit(devices)
                
                elif command == "connect":
                    address = args[0]
                    timeout = args[1] if len(args) > 1 else None
                    
                    if address in self.clients:
                        await self.clients[address].disconnect()
                    
                    # Use timeout if provided
                    if timeout:
                        timeout_seconds = timeout / 1000.0  # Convert ms to seconds
                        client = BleakClient(address, timeout=timeout_seconds)
                    else:
                        client = BleakClient(address)
                        
                    connected = await client.connect()
                    
                    if connected:
                        self.clients[address] = client
                        self.notification_handlers[address] = {}
                        
                        services = client.services
                        # Convert services to a dictionary - handle different Bleak versions
                        services_dict = {}
                        if hasattr(services, 'values'):
                            # For older Bleak versions
                            services_dict = {str(service.uuid): service for service in services.values()}
                        else:
                            # For newer Bleak versions where services is already iterable
                            services_dict = {str(service.uuid): service for service in services}
                        
                        self.connection_updated.emit(connected, address, client)
                        self.services_updated.emit(address, services_dict)
                    else:
                        self.connection_updated.emit(False, address, None)
                
                elif command == "disconnect":
                    address = args[0]
                    if address in self.clients and self.clients[address].is_connected:
                        # Disable all active notifications first
                        if address in self.notification_handlers:
                            for char_uuid in list(self.notification_handlers[address].keys()):
                                await self.clients[address].stop_notify(char_uuid)
                            self.notification_handlers[address].clear()
                        
                        await self.clients[address].disconnect()
                        self.connection_updated.emit(False, address, None)
                        del self.clients[address]
                        if address in self.notification_handlers:
                            del self.notification_handlers[address]
                
                elif command == "check_connection":
                    address = args[0]
                    is_connected = False
                    if address in self.clients:
                        try:
                            # Convert to bool explicitly to handle _DeprecatedIsConnectedReturn type
                            is_connected = bool(self.clients[address].is_connected)
                        except:
                            is_connected = False
                    self.connection_status_checked.emit(address, is_connected)
                
                elif command == "read":
                    address, char_uuid = args
                    if address in self.clients and self.clients[address].is_connected:
                        try:
                            # Debug output handled by main window
                            value = await self.clients[address].read_gatt_char(char_uuid)
                            # Debug output handled by main window
                            # Ensure we're emitting the signal with the correct parameters
                            self.characteristic_read.emit(address, char_uuid, value)
                            # Debug output handled by main window
                        except Exception as e:
                            # Debug output handled by main window
                            self.error_occurred.emit(f"Failed to read characteristic {char_uuid} on device {address}: {str(e)}")
                
                elif command == "write":
                    address, char_uuid, value, response = args
                    if address in self.clients and self.clients[address].is_connected:
                        try:
                            await self.clients[address].write_gatt_char(char_uuid, value, response)
                            self.characteristic_written.emit(address, char_uuid, True)
                        except Exception as e:
                            self.error_occurred.emit(f"Failed to write to characteristic {char_uuid} on device {address}: {str(e)}")
                            self.characteristic_written.emit(address, char_uuid, False)
                
                elif command == "start_notify":
                    address, char_uuid = args
                    if address in self.clients and self.clients[address].is_connected:
                        # Create a notification handler for this specific device/characteristic
                        handler = lambda sender, data: asyncio.create_task(
                            self.notification_handler(address, sender, data)
                        )
                        
                        await self.clients[address].start_notify(char_uuid, handler)
                        
                        if address not in self.notification_handlers:
                            self.notification_handlers[address] = {}
                        self.notification_handlers[address][char_uuid] = True
                
                elif command == "stop_notify":
                    address, char_uuid = args
                    if (address in self.clients and 
                        self.clients[address].is_connected and 
                        address in self.notification_handlers and 
                        char_uuid in self.notification_handlers[address]):
                        
                        await self.clients[address].stop_notify(char_uuid)
                        del self.notification_handlers[address][char_uuid]
                        
            except BleakError as e:
                self.error_occurred.emit(f"BLE Error: {str(e)}")
                # If this was a connection error, update the connection status
                if command == "connect":
                    self.connection_updated.emit(False, args[0], None)
            except Exception as e:
                self.error_occurred.emit(f"Error: {str(e)}")
                # If this was a connection error, update the connection status
                if command == "connect":
                    self.connection_updated.emit(False, args[0], None)
                
            self.command_queue.task_done()
    
    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run_ble_loop())
    
    def scan_devices(self, scan_time=None):
        asyncio.run_coroutine_threadsafe(self.command_queue.put(("scan", [scan_time])), self.loop)
    
    def connect_device(self, address, timeout=None):
        asyncio.run_coroutine_threadsafe(self.command_queue.put(("connect", [address, timeout])), self.loop)
    
    def disconnect_device(self, address):
        asyncio.run_coroutine_threadsafe(self.command_queue.put(("disconnect", [address])), self.loop)
    
    def read_characteristic(self, address, char_uuid):
        # Debug output handled by main window
        asyncio.run_coroutine_threadsafe(self.command_queue.put(("read", [address, char_uuid])), self.loop)
    
    def write_characteristic(self, address, char_uuid, value, response=True):
        asyncio.run_coroutine_threadsafe(self.command_queue.put(("write", [address, char_uuid, value, response])), self.loop)
    
    def start_notify(self, address, char_uuid):
        asyncio.run_coroutine_threadsafe(self.command_queue.put(("start_notify", [address, char_uuid])), self.loop)
    
    def stop_notify(self, address, char_uuid):
        asyncio.run_coroutine_threadsafe(self.command_queue.put(("stop_notify", [address, char_uuid])), self.loop)
        
    def check_connection_status(self, address):
        asyncio.run_coroutine_threadsafe(self.command_queue.put(("check_connection", [address])), self.loop)
