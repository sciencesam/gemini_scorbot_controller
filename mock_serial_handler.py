# mock_serial_handler.py
import time

class MockSerialHandler:
    """A mock version of SerialHandler for testing without hardware."""
    def __init__(self):
        self._is_connected = False
        self.receive_buffer = [] # Simulate received lines
        self.last_sent_command = None
        print("[MockSerial] Initialized Mock Handler.")

    def list_ports(self):
        print("[MockSerial] Listing dummy ports.")
        return ["SIM_PORT_A", "/dev/tty.mockusb"]

    def connect(self, port, baudrate=9600, timeout=1):
        print(f"[MockSerial] Simulating connection to {port} at {baudrate} baud.")
        self._is_connected = True
        # Simulate initial messages, add them to buffer but don't print RX yet
        self.receive_buffer.append("Scorbot Mock Interface Ready.")
        self.receive_buffer.append("OK")
        return True

    def disconnect(self):
        print("[MockSerial] Simulating disconnection.")
        self._is_connected = False
        self.receive_buffer = []

    def send_command(self, command):
        if not self._is_connected:
            print("[MockSerial] ERROR: Cannot send command, not connected.")
            return False
        # --- CHANGED: Use consistent TX prefix ---
        print(f"--> [SERIAL_TX]: {command}")
        self.last_sent_command = command.upper()

        # --- Add basic mock responses ---
        time.sleep(0.1) # Simulate processing delay
        if "HOME" in self.last_sent_command:
             # Check the explicit instruction: wait for "Homing complete(robot)"
             if self.last_sent_command == "HOME":
                self.receive_buffer.append("Executing HOME...")
                time.sleep(1.5) # Simulate homing time
                self.receive_buffer.append("Axis 1 homed.")
                self.receive_buffer.append("Axis 2 homed.")
                self.receive_buffer.append("Axis 3 homed.")
                self.receive_buffer.append("Axis 4 homed.")
                self.receive_buffer.append("Axis 5 homed.")
                self.receive_buffer.append("Homing complete(robot)") # Specific message from prompt
             else: # Other commands containing "HOME" (unlikely?)
                 self.receive_buffer.append("OK")
        elif "LISTPV POSITION" in self.last_sent_command:
            self.receive_buffer.append("Position POSITION :")
            self.receive_buffer.append("Axis 1 = 12345 counts")
            self.receive_buffer.append("Axis 2 = -5678 counts")
            self.receive_buffer.append("Axis 3 = 9012 counts")
            self.receive_buffer.append("Axis 4 = 3456 counts")
            self.receive_buffer.append("Axis 5 = -7890 counts")
            self.receive_buffer.append("OK")
        elif "DEFP" in self.last_sent_command:
             self.receive_buffer.append("OK")
        elif "SETPV" in self.last_sent_command: # Assume prompting mode for simulation
             self.receive_buffer.append("Enter Axis 1 value:") # Simulate prompt
             # In simulation, we can't wait for user input here, so just OK it
             self.receive_buffer.append("OK")
        elif "LISTPV" in self.last_sent_command: # Simulate listing a variable
            pos_name = self.last_sent_command.split()[-1]
            self.receive_buffer.append(f"Position {pos_name} :")
            # Use different values than POSITION
            self.receive_buffer.append("Axis 1 = 1000 counts")
            self.receive_buffer.append("Axis 2 = 2000 counts")
            self.receive_buffer.append("Axis 3 = 3000 counts")
            self.receive_buffer.append("Axis 4 = 4000 counts")
            self.receive_buffer.append("Axis 5 = 5000 counts")
            self.receive_buffer.append("OK")
        elif "EDIT" in self.last_sent_command:
             self.receive_buffer.append("Entering EDIT mode.")
             self.receive_buffer.append("OK") # Simple OK for simulation
        elif "EXIT" in self.last_sent_command:
             self.receive_buffer.append("Exiting EDIT mode.")
             self.receive_buffer.append("OK")
        elif "RUN" in self.last_sent_command:
            self.receive_buffer.append("Running program...")
            time.sleep(1.0) # Simulate program execution
            self.receive_buffer.append("Program complete.")
            self.receive_buffer.append("OK")
        elif "SPEED" in self.last_sent_command:
            self.receive_buffer.append("OK")
        elif "MOVED" in self.last_sent_command or "MOVELD" in self.last_sent_command:
             self.receive_buffer.append("Executing move...")
             time.sleep(0.8)
             self.receive_buffer.append("Move complete.") # More specific message
             self.receive_buffer.append("OK")
        elif "STATUS" in self.last_sent_command or "WHERE" in self.last_sent_command:
             self.receive_buffer.append("STATUS: Ready, Speed=50, Pos=(Simulated)")
             self.receive_buffer.append("OK")
        elif "OPEN" in self.last_sent_command or "CLOSE" in self.last_sent_command:
            self.receive_buffer.append("OK")
        else:
            self.receive_buffer.append("ERROR: Unknown command in mock")

        return True

    def get_received_line(self):
        """Gets a simulated received line, printing it with RX prefix."""
        if self.receive_buffer:
            line = self.receive_buffer.pop(0)
            # --- CHANGED: Print using the standard prefix when retrieved ---
            print(f"<-- [SERIAL_RX]: {line}")
            return line
        return None

    def get_buffer_snapshot(self):
         """Returns a copy of the current buffer content without clearing it."""
         return list(self.receive_buffer)

    def is_connected(self):
        """Checks if mock connection is active."""
        return self._is_connected