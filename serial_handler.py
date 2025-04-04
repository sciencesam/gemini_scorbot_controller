# serial_handler.py

import serial
import serial.tools.list_ports
import time
import threading

class SerialHandler:
    """Handles communication with a real serial port."""
    def __init__(self):
        self.ser = None
        self.receive_buffer = [] # Store lines received from serial
        self.stop_read_thread = threading.Event()
        self.read_thread = None
        self.lock = threading.Lock() # Lock for buffer access

    def list_ports(self):
        """Lists available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self, port, baudrate=9600, timeout=1):
        """Connects to the specified serial port."""
        if self.ser and self.ser.is_open:
            print("Already connected. Disconnecting first.")
            self.disconnect()
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            time.sleep(2)
            if self.ser.is_open:
                print(f"Successfully connected to {port} at {baudrate} baud.")
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.stop_read_thread.clear()
                self.read_thread = threading.Thread(target=self._read_serial_loop, daemon=True)
                self.read_thread.start()
                return True
            else:
                print(f"Failed to open serial port {port} (ser.is_open is false).")
                self.ser = None
                return False
        except serial.SerialException as e:
            print(f"ERROR connecting to {port}: {e}")
            self.ser = None
            return False
        except Exception as e:
            print(f"ERROR: Unexpected error connecting to serial port: {e}")
            self.ser = None
            return False

    def disconnect(self):
        """Disconnects from the serial port and stops the read thread."""
        if self.read_thread and self.read_thread.is_alive():
            self.stop_read_thread.set()
            self.read_thread.join(timeout=2)
            if self.read_thread.is_alive():
                print("Warning: Read thread did not terminate cleanly.")

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                print("Serial port disconnected.")
            except Exception as e:
                print(f"Error closing serial port: {e}")
        self.ser = None
        self.read_thread = None
        with self.lock:
            self.receive_buffer = []

    def send_command(self, command):
        """Sends a command over the serial port. Appends CR ('\r')."""
        if self.ser and self.ser.is_open:
            try:
                full_command = command + '\r'
                encoded_command = full_command.encode('ascii')
                self.ser.write(encoded_command)
                # --- CHANGED: Use a consistent prefix for TX ---
                print(f"--> [SERIAL_TX]: {command}") # Log sent command clearly
                return True
            except serial.SerialTimeoutException:
                print(f"ERROR: Timeout writing to serial port for command: {command}")
                return False
            except serial.SerialException as e:
                print(f"ERROR writing to serial port: {e}")
                return False
            except Exception as e:
                print(f"ERROR: Unexpected error sending command: {e}")
                return False
        else:
            print("ERROR: Cannot send command, serial port not connected.")
            return False

    def _read_serial_loop(self):
        """Continuously reads lines from serial port (run in background thread)."""
        print("Starting serial read thread...")
        while not self.stop_read_thread.is_set():
            if not self.ser or not self.ser.is_open:
                 print("Serial port is not open in read loop. Stopping thread.")
                 break
            try:
                if self.ser.in_waiting > 0:
                    line_bytes = self.ser.readline()
                    # --- CHANGED: Decode carefully and print immediately ---
                    try:
                        line = line_bytes.decode('ascii', errors='replace').strip() # Use replace on error
                        if line:
                            # --- Print immediately when received ---
                            print(f"<-- [SERIAL_RX]: {line}")
                            with self.lock:
                                self.receive_buffer.append(line)
                    except UnicodeDecodeError as ude:
                         # Log if decoding fails completely, even with replace (unlikely)
                         print(f"<-- [SERIAL_RX_ERROR]: Failed to decode bytes: {line_bytes} - Error: {ude}")

            except serial.SerialException as e:
                print(f"ERROR reading from serial port: {e}. Stopping read thread.")
                self.stop_read_thread.set()
                break
            except Exception as e:
                 print(f"ERROR: Unexpected error reading serial: {e}")
                 time.sleep(0.5)
            time.sleep(0.05) # Reduce CPU usage

        print("Stopping serial read thread.")

    def get_received_line(self):
        """Gets the oldest received line from the buffer (FIFO), non-blocking."""
        with self.lock:
            if self.receive_buffer:
                return self.receive_buffer.pop(0)
        return None

    def get_buffer_snapshot(self):
        """Returns a copy of the current buffer content without clearing it."""
        with self.lock:
            return list(self.receive_buffer) # Return a copy

    def is_connected(self):
        """Checks if the serial port is connected and open."""
        return self.ser is not None and self.ser.is_open