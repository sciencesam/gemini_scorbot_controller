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
        self.lock = threading.Lock() # Lock for buffer access if needed, good practice

    def list_ports(self):
        """Lists available serial ports."""
        ports = serial.tools.list_ports.comports()
        # Filter for common USB serial patterns if desired, but list all for now
        return [port.device for port in ports]

    def connect(self, port, baudrate=9600, timeout=1):
        """Connects to the specified serial port."""
        if self.ser and self.ser.is_open:
            print("Already connected. Disconnecting first.")
            self.disconnect()
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            # Some devices need a brief pause after opening the port
            time.sleep(2) # Allow time for connection to establish & device init
            if self.ser.is_open:
                print(f"Successfully connected to {port} at {baudrate} baud.")
                # Clear any old data in buffer
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                # Start background reader thread
                self.stop_read_thread.clear()
                self.read_thread = threading.Thread(target=self._read_serial_loop, daemon=True)
                self.read_thread.start()
                return True
            else:
                # This case might not be reachable if Serial() throws exception on failure
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
            # Wait for the thread to finish
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
            self.receive_buffer = [] # Clear buffer on disconnect

    def send_command(self, command):
        """Sends a command over the serial port. Appends CR ('\r')."""
        if self.ser and self.ser.is_open:
            try:
                # Scorbot typically uses Carriage Return (CR) termination
                # Verify this in your manual! Could be '\n' or '\r\n'
                full_command = command + '\r'
                encoded_command = full_command.encode('ascii')
                self.ser.write(encoded_command)
                # Optional: Flush output buffer to ensure data is sent immediately
                # self.ser.flush()
                print(f"[SERIAL_TX]: {command}") # Log sent command
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
        """Continuously reads lines from serial port (run in a background thread)."""
        print("Starting serial read thread...")
        while not self.stop_read_thread.is_set():
            if not self.ser or not self.ser.is_open:
                 # Port closed unexpectedly
                 print("Serial port is not open in read loop. Stopping thread.")
                 break
            try:
                if self.ser.in_waiting > 0:
                    # Read one line, expecting bytes, decode assuming ASCII
                    # Use errors='ignore' for robustness against potential noise
                    line_bytes = self.ser.readline()
                    line = line_bytes.decode('ascii', errors='ignore').strip()
                    if line: # Only add non-empty lines
                        # print(f"[SERIAL_RX_RAW]: {line}") # Log raw received line (optional)
                        with self.lock:
                            self.receive_buffer.append(line)
            except serial.SerialException as e:
                # Handle specific serial errors if the port disconnects etc.
                print(f"ERROR reading from serial port: {e}. Stopping read thread.")
                self.stop_read_thread.set() # Signal stop
                break
            except Exception as e:
                 print(f"ERROR: Unexpected error reading serial: {e}")
                 # Depending on error, might want to stop or continue
                 time.sleep(0.5) # Pause briefly after unexpected error
            # Small sleep even if no data, prevents busy-waiting spinning CPU
            time.sleep(0.05) # 50ms poll interval

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
