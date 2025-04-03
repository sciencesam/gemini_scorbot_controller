import time

class MockSerialHandler:
    """A mock version of SerialHandler for testing without hardware."""
    def __init__(self):
        self._is_connected = False
        self.receive_buffer = [] # Simulate received lines
        self.last_sent_command = None
        print("[MockSerial] Initialized Mock Handler.")

    def list_ports(self):
        """Returns dummy ports for simulation."""
        print("[MockSerial] Listing dummy ports.")
        return ["SIM_PORT_A", "/dev/tty.mockusb"]

    def connect(self, port, baudrate=9600, timeout=1):
        """Simulates connecting."""
        print(f"[MockSerial] Simulating connection to {port} at {baudrate} baud.")
        self._is_connected = True
        # Simulate a potential welcome message or status from the robot on connect
        self.receive_buffer.append("Scorbot Mock Interface Ready.")
        self.receive_buffer.append("OK")
        return True

    def disconnect(self):
        """Simulates disconnecting."""
        print("[MockSerial] Simulating disconnection.")
        self._is_connected = False
        self.receive_buffer = [] # Clear buffer on disconnect

    def send_command(self, command):
        """Simulates sending a command; prints it and adds a mock response."""
        if not self._is_connected:
            print("[MockSerial] ERROR: Cannot send command, not connected.")
            return False

        print(f"[SIMULATED_SERIAL_TX]: {command}")
        self.last_sent_command = command.upper() # Store uppercase for easier matching

        # --- Add basic mock responses based on command ---
        # Make this more sophisticated as needed for your tests
        time.sleep(0.1) # Simulate processing delay
        if "HOME" in self.last_sent_command:
            self.receive_buffer.append("Executing HOME...") # Simulate intermediate msg
            time.sleep(0.5) # Simulate movement time
            self.receive_buffer.append("OK") # Simulate simple acknowledgement
        elif "STATUS" in self.last_sent_command or "WHERE" in self.last_sent_command:
             # Simulate position response (adjust format if needed)
             self.receive_buffer.append("POSITION: 100.0 50.5 -20.0 90.0 0.0")
             self.receive_buffer.append("OK")
        elif "SPEED" in self.last_sent_command:
            self.receive_buffer.append("OK")
        elif "MOVE" in self.last_sent_command or "GOTO" in self.last_sent_command:
             self.receive_buffer.append("Executing move...")
             time.sleep(0.4)
             self.receive_buffer.append("OK")
        elif "OPEN" in self.last_sent_command or "CLOSE" in self.last_sent_command:
            self.receive_buffer.append("OK")
        else:
            # Default response for unrecognized mock commands
            self.receive_buffer.append("ERROR: Unknown command in mock")
            # self.receive_buffer.append("OK") # Or just OK everything

        return True

    def get_received_line(self):
        """Gets a simulated received line from the buffer (FIFO)."""
        if self.receive_buffer:
            line = self.receive_buffer.pop(0)
            # Simulate receiving by printing it here when polled by main loop
            # print(f"[SIMULATED_SERIAL_RX]: {line}") # Optional: print when retrieved
            return line
        return None

    def get_buffer_snapshot(self):
         """Returns a copy of the current buffer content without clearing it."""
         return list(self.receive_buffer)

    def is_connected(self):
        """Checks if mock connection is active."""
        return self._is_connected