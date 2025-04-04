# mock_serial_handler.py
import time
import re # Import regex

class MockSerialHandler:
    """A mock version of SerialHandler for testing without hardware."""
    def __init__(self):
        self._is_connected = False
        self.receive_buffer = [] # Simulate received lines
        self.last_sent_command = None
        # Simulate some initial state for LISTPV
        self.mock_joint_values = [1111, -2222, 3333, -4444, 5555]
        print("[MockSerial] Initialized Mock Handler.")

    def list_ports(self):
        print("[MockSerial] Listing dummy ports.")
        return ["SIM_PORT_A", "/dev/tty.mockusb"]

    def connect(self, port, baudrate=9600, timeout=1):
        print(f"[MockSerial] Simulating connection to {port} at {baudrate} baud.")
        self._is_connected = True
        self.receive_buffer.append("Scorbot Mock Interface Ready.")
        self.receive_buffer.append("OK") # Simulate prompt/OK
        return True

    def disconnect(self):
        print("[MockSerial] Simulating disconnection.")
        self._is_connected = False
        self.receive_buffer = []

    def send_command(self, command):
        if not self._is_connected:
            print("[MockSerial] ERROR: Cannot send command, not connected.")
            return False

        print(f"--> [SERIAL_TX]: {command}")
        self.last_sent_command = command.upper()
        command_parts = command.split() # Split command for parsing
        base_command = command_parts[0].upper()

        # --- Simulate Responses ---
        time.sleep(0.1)

        if base_command == "HOME":
             self.receive_buffer.append("Executing HOME...")
             time.sleep(1.0) # Shorten simulation time
             self.receive_buffer.append("Axis 1 homed.")
             self.receive_buffer.append("Axis 2 homed.")
             self.receive_buffer.append("Axis 3 homed.")
             self.receive_buffer.append("Axis 4 homed.")
             self.receive_buffer.append("Axis 5 homed.")
             self.receive_buffer.append("Homing complete(robot)")
             self.receive_buffer.append("OK") # Add OK after homing complete

        elif base_command == "LISTPV" and len(command_parts) > 1 and command_parts[1].upper() == "POSITION":
            # Simulate LISTPV POSITION output
            self.receive_buffer.append("Position POSITION :")
            for i, val in enumerate(self.mock_joint_values):
                 self.receive_buffer.append(f"Axis {i+1} = {val} counts")
            self.receive_buffer.append("OK")

        elif base_command == "LISTPV" and len(command_parts) > 1:
             pos_name = command_parts[1] # Keep original case
             # Simulate listing a variable with slightly different values
             self.receive_buffer.append(f"Position {pos_name} :")
             self.receive_buffer.append("Axis 1 = 1000 counts")
             self.receive_buffer.append("Axis 2 = 2000 counts")
             self.receive_buffer.append("Axis 3 = 3000 counts")
             self.receive_buffer.append("Axis 4 = 4000 counts")
             self.receive_buffer.append("Axis 5 = 5000 counts")
             self.receive_buffer.append("OK")

        elif base_command == "DEFP":
             # DEFP itself is usually just OK
             self.receive_buffer.append("OK")

        elif base_command == "SETPV" and len(command_parts) > 1:
            # SETPV <name> enters prompting mode
            pos_name = command_parts[1]
            print(f"[MockSerial] Simulating SETPV prompting for '{pos_name}'")
            # Add the prompts to the buffer - the main loop will handle reading them
            for i in range(5):
                self.receive_buffer.append(f"Enter Axis {i+1} value:")
            # Add the final confirmation after all prompts *would* have been answered
            self.receive_buffer.append("OK")

        elif base_command == "EDIT":
             self.receive_buffer.append("Entering EDIT mode.")
             self.receive_buffer.append("OK")
        elif base_command == "EXIT":
             self.receive_buffer.append("Exiting EDIT mode.")
             self.receive_buffer.append("OK")
        elif base_command == "RUN":
            self.receive_buffer.append("Running program...")
            time.sleep(0.5)
            self.receive_buffer.append("Program complete.")
            self.receive_buffer.append("OK")
        elif base_command == "SPEED":
            self.receive_buffer.append("OK")
        elif base_command == "MOVED" or base_command == "MOVELD":
             self.receive_buffer.append("Executing move...")
             time.sleep(0.5)
             # Simulate changing the internal position for subsequent LISTPV
             self.mock_joint_values = [v + 100 for v in self.mock_joint_values]
             self.receive_buffer.append("Move complete.")
             self.receive_buffer.append("OK")
        elif base_command == "STATUS" or base_command == "WHERE":
             self.receive_buffer.append("STATUS: Ready, Speed=50, Pos=(Simulated)")
             self.receive_buffer.append("OK")
        elif base_command == "OPEN" or base_command == "CLOSE":
            self.receive_buffer.append("OK")
        else:
            self.receive_buffer.append("ERROR: Unknown command in mock")

        return True

    # --- send_value (New method for interactive SETPV simulation) ---
    def send_value(self, value_str):
        """ Simulates the program sending a value during SETPV """
        if not self._is_connected: return False
        # The robot wouldn't echo the value, just proceed.
        # We just need to print it for clarity in the simulation log.
        print(f"--> [SIMULATED_VALUE_TX]: {value_str}")
        # Update mock position state if desired, but primary purpose
        # is just to acknowledge the value was "sent"
        return True


    def get_received_line(self):
        """Gets a simulated received line, printing it with RX prefix."""
        if self.receive_buffer:
            line = self.receive_buffer.pop(0)
            print(f"<-- [SERIAL_RX]: {line}")
            return line
        return None

    def get_buffer_snapshot(self):
         return list(self.receive_buffer)

    def is_connected(self):
        return self._is_connected