Okay, this is a great refinement goal. We want the program to act more like an intelligent agent, handling the back-and-forth of specific command sequences (like `LISTPV` followed by `SETPV`) and ensuring Gemini gets a complete picture of the interaction for better decision-making.

We'll implement **Option D** discussed in the thought process: The program will store the results from `LISTPV POSITION` and automatically use those values when Gemini asks to run `SETPV <name>` in prompting mode.

Here's the plan:

1.  **Introduce State:** Add a dictionary in `main.py` to hold the last known joint values.
2.  **Parse `LISTPV`:** Enhance `wait_for_serial_response` to specifically parse the output of `LISTPV POSITION` and store the values in our state dictionary.
3.  **Intercept and Handle `SETPV`:** Create a new function `handle_setpv_interactive` that manages the prompt-response sequence for `SETPV`, using the stored joint values.
4.  **Modify Main Loop:** Call the appropriate handler (`handle_setpv_interactive` or the standard `wait_for_serial_response`) based on the command Gemini sends.
5.  **Ensure Full Feedback:** Make sure the summary of the `SETPV` interaction (including values sent) is returned to Gemini.
6.  **Update Mock Handler:** Improve the mock handler to simulate these interactions more accurately.

Let's modify the code:

**1. Update `mock_serial_handler.py`**

Make the mock handler simulate the `LISTPV POSITION` output format and the `SETPV` prompting sequence realistically.

```python
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

```

**2. Modify `main.py`**

```python
# main.py
import time
import os
import argparse
import sys
import re # Import regex

# Import handlers
from gemini_handler import GeminiHandler
from serial_handler import SerialHandler # Use this by default
from mock_serial_handler import MockSerialHandler # Use if --simulate
from camera_handler import CameraHandler

# --- Configuration Constants ---
INITIAL_PROMPT_FILE_DEFAULT = "initial_prompt.txt"
SCORBOT_MANUAL_PATH_DEFAULT = "scorbot_acl_manual.pdf"
IMAGE_CAPTURE_DIR = "captures"
SERIAL_RESPONSE_TIMEOUT = 90.0 # Max seconds overall
SERIAL_INTER_MESSAGE_TIMEOUT = 1.5 # Max seconds between lines
SERIAL_PROMPT_TIMEOUT = 5.0 # Max seconds to wait specifically for a known prompt (like SETPV)

# --- State Dictionary ---
# Stores information gleaned from robot responses
# We initialize 'last_joint_values' to None to indicate we don't know them yet.
current_robot_state = {
    "last_joint_values": None # Will store list of 5 floats/ints, or None
}

# --- Helper Functions ---
def is_slash_command(text):
    """Checks if the input is a local slash command."""
    return text.startswith('/')

# --- Regex for parsing LISTPV POSITION output ---
# Matches "Axis N = VALUE units" and captures N and VALUE
listpv_axis_regex = re.compile(r"Axis\s+(\d+)\s*=\s*(-?\d+(\.\d+)?)\s+counts", re.IGNORECASE)

def parse_listpv_response(response_lines):
    """
    Parses the lines from a LISTPV POSITION response to extract joint values.
    Updates the global current_robot_state.
    Returns True if successful (5 values found), False otherwise.
    """
    global current_robot_state
    joint_values = [None] * 5 # Initialize list for 5 axes
    found_count = 0

    for line in response_lines:
        match = listpv_axis_regex.search(line)
        if match:
            axis_num = int(match.group(1))
            axis_val_str = match.group(2)
            try:
                # Store as float for potential future use, though counts are ints
                axis_val = float(axis_val_str)
                if 1 <= axis_num <= 5:
                    if joint_values[axis_num - 1] is None: # Only store first match per axis
                        joint_values[axis_num - 1] = axis_val
                        found_count += 1
            except ValueError:
                print(f"Warning: Could not parse axis value '{axis_val_str}' as float.")
                continue # Skip this line if value is invalid

    if found_count == 5 and all(v is not None for v in joint_values):
        print(f"    (Successfully parsed joint values: {joint_values})")
        current_robot_state["last_joint_values"] = joint_values
        return True
    else:
        print(f"Warning: Did not find all 5 axis values in LISTPV response. Found: {found_count}")
        # Optionally clear state if parsing fails:
        # current_robot_state["last_joint_values"] = None
        return False


def wait_for_serial_response(serial_comm, sent_command):
    """
    Waits for and collects serial response lines.
    Specifically parses LISTPV POSITION if that was the command sent.
    Returns a string containing all response lines/summary.
    """
    global current_robot_state # Allow modification of state
    responses = []
    start_time = time.time()
    last_rx_time = start_time
    timed_out = False
    inter_message_timed_out = False

    print(f"    (Waiting for response to '{sent_command}' - Max {SERIAL_RESPONSE_TIMEOUT}s total, {SERIAL_INTER_MESSAGE_TIMEOUT}s between lines)")

    while True:
        if time.time() - start_time > SERIAL_RESPONSE_TIMEOUT:
            print("    (Overall response timeout reached.)")
            timed_out = True
            break

        line = serial_comm.get_received_line()

        if line is not None:
            responses.append(line)
            last_rx_time = time.time()

            # --- Specific command completion checks ---
            # Check for generic OK or prompt which often signals end
            # Be careful: SETPV also sends prompts we need to handle differently
            # if sent_command.upper().split()[0] != "SETPV" and (line.strip() == ">" or line.strip().upper() == "OK"):
            #     print("    (Detected likely end-of-response marker)")
            #     # Give a tiny bit more time?
            #     time.sleep(0.1)
            #     final_line = serial_comm.get_received_line()
            #     if final_line is not None: responses.append(final_line)
            #     break # Exit if terminator found for non-SETPV commands

            if sent_command.upper() == "HOME" and "Homing complete(robot)" in line:
                print("    (Detected 'Homing complete' message)")
                time.sleep(0.2)
                final_line = serial_comm.get_received_line()
                if final_line is not None: responses.append(final_line)
                break # Consider HOME complete

        else: # No line received
            if time.time() - last_rx_time > SERIAL_INTER_MESSAGE_TIMEOUT:
                if responses:
                    # print("    (Timeout waiting for *further* response lines.)") # Can be noisy
                    inter_message_timed_out = True
                break
            time.sleep(0.05)

    # --- Process collected response ---
    full_response_text = "\n".join(responses)
    result_summary = f"[RX for '{sent_command}']: {full_response_text}" # Start with raw response

    # --- Parse if LISTPV POSITION ---
    if sent_command.upper() == "LISTPV POSITION":
        if parse_listpv_response(responses):
            # Add confirmation to the summary sent to Gemini
             result_summary += "\n[System Note: Successfully parsed and stored joint values from LISTPV.]"
        else:
             result_summary += "\n[System Note: Failed to parse joint values from LISTPV response.]"

    # --- Add timeout notes ---
    if timed_out:
        result_summary += "\n[System Note: Overall response timeout reached during reception.]"
    elif inter_message_timed_out and responses: # Only note inter-message timeout if we got *some* response
         result_summary += "\n[System Note: Stopped waiting for further lines due to inter-message timeout.]"
    elif not responses and timed_out: # No response at all
        result_summary = f"[System Note: Sent '{sent_command}', but received no response within timeout.]"
    elif not responses: # No response, no timeout (should be rare)
         result_summary = f"[System Note: Sent '{sent_command}', received no response.]"


    return result_summary


# --- NEW FUNCTION to handle SETPV interactive mode ---
def handle_setpv_interactive(serial_comm, command, state):
    """
    Handles the interactive prompting for SETPV <name>.
    Uses values from state['last_joint_values'].
    Sends values automatically.
    Returns a summary string for Gemini.
    """
    global current_robot_state # Needed if we modify state (e.g., on error)
    command_parts = command.split()
    if len(command_parts) < 2:
         return "[System Error: Invalid SETPV command format received.]"
    position_name = command_parts[1]

    print(f"--- Handling Interactive SETPV for '{position_name}' ---")
    interaction_log = [f"Initiating SETPV for '{position_name}'."] # Log for Gemini summary

    # 1. Check if we have stored joint values
    if state.get("last_joint_values") is None or len(state["last_joint_values"]) != 5:
        error_msg = f"[System Error: Cannot execute SETPV '{position_name}'. No valid joint values stored from a previous LISTPV POSITION.]"
        print(error_msg)
        interaction_log.append(error_msg)
        return "\n".join(interaction_log)

    stored_values = state["last_joint_values"]
    print(f"    (Using stored values: {stored_values})")
    interaction_log.append(f"Using stored values: {stored_values}")

    # 2. Send the initial SETPV command
    if not serial_comm.send_command(command):
        error_msg = f"[System Error: Failed to send initial command '{command}' to serial port.]"
        print(error_msg)
        interaction_log.append(error_msg)
        return "\n".join(interaction_log)

    # 3. Loop through expected prompts (Axis 1 to 5)
    axis_prompt_regex = re.compile(r"Enter Axis\s+(\d+)\s+value:", re.IGNORECASE)
    for i in range(1, 6): # Expect prompts for Axis 1 through 5
        expected_axis = i
        prompt_received = False
        start_prompt_wait = time.time()

        # Wait for the specific axis prompt
        print(f"    (Waiting for Axis {expected_axis} prompt...)")
        prompt_line = None
        while time.time() - start_prompt_wait < SERIAL_PROMPT_TIMEOUT:
            line = serial_comm.get_received_line()
            if line is not None:
                 interaction_log.append(f"Received: '{line}'") # Log raw receipt
                 match = axis_prompt_regex.search(line)
                 if match:
                     received_axis = int(match.group(1))
                     if received_axis == expected_axis:
                         prompt_line = line
                         prompt_received = True
                         print(f"    (Received prompt for Axis {expected_axis})")
                         break # Got the expected prompt
                     else:
                         # Received prompt for wrong axis? Error.
                         error_msg = f"[System Error: SETPV Interaction Failed. Expected prompt for Axis {expected_axis}, but received prompt for Axis {received_axis}.]"
                         print(error_msg)
                         interaction_log.append(error_msg)
                         return "\n".join(interaction_log)
                 # else: It's some other line, just log it and continue waiting for the prompt
            else:
                time.sleep(0.05) # Wait briefly

        # Check if we received the expected prompt
        if not prompt_received:
            error_msg = f"[System Error: SETPV Interaction Failed. Timed out waiting for Axis {expected_axis} prompt.]"
            print(error_msg)
            interaction_log.append(error_msg)
            return "\n".join(interaction_log)

        # Send the corresponding value
        value_to_send = str(stored_values[expected_axis - 1])
        print(f"    (Sending value for Axis {expected_axis}: {value_to_send})")
        # Use a dedicated method for mock, or regular send for real serial
        if isinstance(serial_comm, MockSerialHandler):
             if not serial_comm.send_value(value_to_send): # Mock handler prints TX
                  error_msg = f"[System Error: SETPV Interaction Failed. Mock send_value failed for Axis {expected_axis}.]"
                  print(error_msg)
                  interaction_log.append(error_msg)
                  return "\n".join(interaction_log)
        else:
             # Real serial: send value followed by CR
             full_value_cmd = value_to_send + '\r'
             print(f"--> [SERIAL_TX_VALUE]: {value_to_send}") # Explicitly log value sent
             try:
                 serial_comm.ser.write(full_value_cmd.encode('ascii'))
             except Exception as e:
                  error_msg = f"[System Error: SETPV Interaction Failed. Serial write error sending value for Axis {expected_axis}: {e}]"
                  print(error_msg)
                  interaction_log.append(error_msg)
                  return "\n".join(interaction_log)

        interaction_log.append(f"Sent value for Axis {expected_axis}: {value_to_send}")
        time.sleep(0.1) # Small pause after sending value

    # 4. Wait for final confirmation (e.g., "OK")
    print("    (Waiting for final confirmation 'OK'...)")
    confirmation_received = False
    start_confirm_wait = time.time()
    while time.time() - start_confirm_wait < SERIAL_PROMPT_TIMEOUT:
         line = serial_comm.get_received_line()
         if line is not None:
             interaction_log.append(f"Received: '{line}'")
             # Convert to upper for case-insensitive check
             if line.strip().upper() == "OK":
                 print("    (Received final 'OK')")
                 confirmation_received = True
                 break
             # Optional: Check for error messages explicitly here
             # elif "ERROR" in line.upper(): ... handle error ...

         else:
             time.sleep(0.05)

    # 5. Final Summary
    if confirmation_received:
        success_msg = f"[SETPV Interaction Summary for '{position_name}']: Successfully prompted for and sent values for all 5 axes using stored data. Received final 'OK'."
        print("--- SETPV Interaction Complete ---")
        interaction_log.append(success_msg)
    else:
        error_msg = f"[System Error: SETPV Interaction Failed. Did not receive final 'OK' confirmation after sending all values.]"
        print(error_msg)
        print("--- SETPV Interaction Failed ---")
        interaction_log.append(error_msg)

    # Return the detailed log for Gemini
    return "\n".join(interaction_log)


# --- Main Application Logic ---
def main():
    global current_robot_state # Make state accessible
    # --- Argument Parser Setup ---
    # ... (parser setup remains the same) ...
    parser = argparse.ArgumentParser(
        description="Control Scorbot ER VII with Gemini AI, using serial and webcam.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--simulate', action='store_true', help="Run in simulation mode.")
    parser.add_argument('--manual', type=str, default=SCORBOT_MANUAL_PATH_DEFAULT, help="Path to the Scorbot manual file.")
    parser.add_argument('--prompt', type=str, default=INITIAL_PROMPT_FILE_DEFAULT, help="Path to the initial prompt file.")
    parser.add_argument('--baud', type=int, default=9600, help="Baud rate for serial connection.")
    parser.add_argument('--port', type=str, default=None, help="Specify serial port directly.")
    parser.add_argument('--camera', type=int, default=None, help="Specify camera index directly.")
    args = parser.parse_args()


    print("--- Gemini Scorbot Controller ---")
    if args.simulate:
        print("*** RUNNING IN SIMULATION MODE (Using Mock Serial Handler) ***")
        SerialOrMockHandler = MockSerialHandler
    else:
        print("*** RUNNING IN LIVE MODE (Using Real Serial Handler) ***")
        SerialOrMockHandler = SerialHandler

    # --- Initialize Handlers (Gemini, Camera, Serial) ---
    # ... (Gemini init - same as before) ...
    print(f"Loading initial prompt from: {args.prompt}")
    try:
        with open(args.prompt, 'r') as f: initial_prompt = f.read()
    except FileNotFoundError: print(f"FATAL ERROR: Initial prompt file '{args.prompt}' not found."); sys.exit(1)
    if args.manual and not os.path.exists(args.manual): print(f"Warning: Manual file '{args.manual}' not found.")
    print("Initializing Gemini Handler...")
    try:
        gemini = GeminiHandler(initial_prompt, manual_path=args.manual)
    except Exception as e: print(f"FATAL ERROR: Failed to initialize Gemini Handler: {e}"); sys.exit(1)

    # ... (Camera setup - same as before) ...
    camera = None
    selected_camera_index = args.camera
    if selected_camera_index is None:
        available_cameras = CameraHandler.list_available_cameras()
        if not available_cameras: print("Warning: No cameras detected.")
        elif len(available_cameras) == 1: selected_camera_index = available_cameras[0]; print(f"Auto-selecting camera index {selected_camera_index}.")
        else:
            print("Available camera indices:"); [print(f"  {idx} {'(likely built-in)' if idx == 0 else ''}") for idx in available_cameras]
            while True:
                try:
                    choice = input(f"Select camera index (default {available_cameras[0]}): ")
                    if not choice.strip(): selected_camera_index = available_cameras[0]; print(f"Using default index {selected_camera_index}"); break
                    choice_int = int(choice);
                    if choice_int in available_cameras: selected_camera_index = choice_int; break
                    else: print("Invalid choice.")
                except ValueError: print("Invalid input.")
    if selected_camera_index is not None:
        print(f"Initializing Camera Handler index {selected_camera_index}...")
        camera = CameraHandler(camera_index=selected_camera_index)
        if not camera.initialize_camera(): print(f"Warning: Failed to initialize camera {selected_camera_index}."); camera = None

    # ... (Serial setup - same as before, uses SerialOrMockHandler) ...
    print("Initializing Serial Handler...")
    serial_comm = SerialOrMockHandler()
    selected_port = args.port
    if args.simulate:
        if not serial_comm.connect("SIMULATED_PORT", args.baud): print("FATAL ERROR: Failed mock connect."); sys.exit(1)
    else:
        if selected_port is None:
            available_ports = serial_comm.list_ports()
            if not available_ports: print("FATAL ERROR: No serial ports found."); sys.exit(1)
            print("Available serial ports:"); [print(f"  {i}: {p}") for i, p in enumerate(available_ports)]
            while True:
                try:
                    choice = input(f"Select serial port number (0-{len(available_ports)-1}): ")
                    choice_int = int(choice)
                    if 0 <= choice_int < len(available_ports): selected_port = available_ports[choice_int]; break
                    else: print("Invalid choice.")
                except ValueError: print("Please enter a number.")
        print(f"Connecting to {selected_port} at {args.baud} baud...")
        if not serial_comm.connect(selected_port, args.baud): print(f"FATAL ERROR: Failed to connect to {selected_port}."); sys.exit(1)


    # --- Ready message ---
    # ... (Ready message - same as before) ...
    print("\n--- System Ready ---")
    print("Type message/command, or local command (/quit, /view, /capture, /serial).")
    print("-" * 25)


    # --- Main Interaction Loop (Revised Structure) ---
    next_gemini_input = {}

    try:
        while True:
            gemini_triggered_action = False
            response_summary_for_gemini = None # Store result here

            # --- Step 1: Send to Gemini if needed, else get User Input ---
            if next_gemini_input:
                print("\n... Asking Gemini (based on previous action/response)...")
                # Clear buffer before sending response to Gemini? Risky if async msgs matter.
                # For now, rely on the handlers printing RX in real time.
                gemini_response_text = gemini.send_message(**next_gemini_input)
                next_gemini_input = {}
            else:
                 # Drain async messages before user prompt
                 # ... (drain logic same as before) ...
                stray_lines = []; # Drain async messages
                while True: line = serial_comm.get_received_line(); \
                     if line is None: break; stray_lines.append(line)
                if stray_lines: print(f"--- Note: Received {len(stray_lines)} async serial lines ---")

                try:
                    user_input = input("\n> You: ").strip()
                except EOFError: print("\nEOF detected."); break

                if is_slash_command(user_input):
                    # ... (Handle /quit, /view, /capture, /serial - same as before) ...
                    if user_input.lower() == '/quit': break
                    elif user_input.lower().startswith('/serial ') and not args.simulate:
                        manual_cmd = user_input[len('/serial '):].strip();
                        if manual_cmd: print(f"--> [Manual Serial Send]: {manual_cmd}"); serial_comm.send_command(manual_cmd); time.sleep(0.5)
                        else: print("Usage: /serial <cmd>")
                        continue
                    elif user_input.lower() == '/view':
                        print("--- Serial Buffer Snapshot ---"); buffered = serial_comm.get_buffer_snapshot();
                        if buffered: [print(f"  {line}") for line in buffered[-15:]]
                        else: print("  (Buffer empty or handled)"); print("-" * 20)
                        continue
                    elif user_input.lower() == '/capture' and camera:
                        print("--> [Manual Capture]"); filepath = camera.capture_image(IMAGE_CAPTURE_DIR, "manual_capture")
                        if filepath:
                            print(f"Saved to {filepath}.")
                            if input("Send to Gemini? (y/n): ").lower().strip() == 'y':
                                next_gemini_input = {'user_message_text': "[User manually captured image.]", 'image_path': filepath}; continue
                        else: print("Capture failed.")
                        continue
                    elif user_input.lower() == '/capture' and not camera: print("Camera unavailable."); continue
                    else: print(f"Unknown command: {user_input}"); continue

                # Regular user input
                print("\n... Asking Gemini (based on user input)...")
                gemini_response_text = gemini.send_message(user_message_text=user_input)

            # --- Step 2: Parse Gemini's Response ---
            if gemini_response_text is None: print("Warning: Gemini gave no response."); continue
            text_to_show, serial_cmd_from_gemini, needs_image = gemini.parse_response(gemini_response_text)
            print(f"\n< Gemini: {text_to_show}")

            # --- Step 3: Handle Gemini's Actions ---
            if serial_cmd_from_gemini:
                gemini_triggered_action = True
                command_base = serial_cmd_from_gemini.split()[0].upper()

                # --- Check if it's SETPV (interactive) ---
                if command_base == "SETPV" and len(serial_cmd_from_gemini.split()) > 1:
                    # Call the specialized handler
                    response_summary_for_gemini = handle_setpv_interactive(serial_comm, serial_cmd_from_gemini, current_robot_state)
                else:
                    # --- Handle regular commands ---
                    if serial_comm.send_command(serial_cmd_from_gemini):
                        # Wait for and process the response
                        response_summary_for_gemini = wait_for_serial_response(serial_comm, serial_cmd_from_gemini)
                    else:
                        # Failed to send command
                        print(f"    ERROR: Failed to send command '{serial_cmd_from_gemini}' to serial port.")
                        response_summary_for_gemini = f"[System Note: Failed to send command '{serial_cmd_from_gemini}' due to serial error.]"

                # Prepare response for next Gemini call
                next_gemini_input = {'serial_response': response_summary_for_gemini}

            elif needs_image:
                 gemini_triggered_action = True
                 # ... (Image capture logic - same as before) ...
                 if camera:
                     print("--> [Capturing Image for Gemini]"); filepath = camera.capture_image(IMAGE_CAPTURE_DIR, "gemini_request")
                     if filepath: print("... Image captured, will send next."); next_gemini_input = {'user_message_text': "[System Note: Here is requested image.]", 'image_path': filepath}
                     else: print("ERROR: Failed capture."); next_gemini_input = {'user_message_text': "[System Note: Failed capture due to camera error.]"}
                 else: print("Camera unavailable."); next_gemini_input = {'user_message_text': "[System Note: Cannot capture, camera unavailable.]"}


            # --- Step 4: Loop Control ---
            if gemini_triggered_action:
                continue # Immediately process the result/request

    except KeyboardInterrupt: print("\nCtrl+C detected.")
    finally:
        # --- Cleanup ---
        print("\nShutting down...");
        if serial_comm: print("Disconnecting serial..."); serial_comm.disconnect()
        if camera: print("Releasing camera..."); camera.release_camera()
        print("Goodbye!")

if __name__ == "__main__":
    main()
```

**Key Changes Recap:**

1.  **`current_robot_state` Dictionary:** Added globally in `main.py` to hold `'last_joint_values'`.
2.  **`listpv_axis_regex` & `parse_listpv_response()`:** Added to specifically find and extract the 5 axis values from `LISTPV POSITION` output and update `current_robot_state`.
3.  **`wait_for_serial_response()` Updated:** Now calls `parse_listpv_response()` if the command was `LISTPV POSITION` and includes parsing success/failure notes in the summary sent to Gemini.
4.  **`handle_setpv_interactive()` Function:** This new function manages the `SETPV <name>` interaction:
    *   Checks `current_robot_state` for valid joint values.
    *   Sends the `SETPV` command.
    *   Loops, waiting for each `Enter Axis X value:` prompt.
    *   Sends the corresponding stored value.
    *   Waits for the final `OK`.
    *   Constructs a detailed log/summary of the entire interaction (success or failure steps) to be sent back to Gemini.
5.  **Main Loop Logic:** Checks if `serial_cmd_from_gemini` is `SETPV`. If yes, it calls `handle_setpv_interactive`; otherwise, it calls the original `send_command` + `wait_for_serial_response`. The result from *either* handler populates `next_gemini_input['serial_response']`.
6.  **Mock Handler:** Updated to produce realistic `LISTPV POSITION` output and the sequence of `SETPV` prompts, plus a `send_value` method for logging during simulation.

Now, when Gemini follows the "reliable workflow":

1.  Gemini asks to run `LISTPV POSITION`.
2.  `main.py` runs it, `wait_for_serial_response` collects the output and `parse_listpv_response` stores the values (e.g., `[123, 456, 789, ...]`) in `current_robot_state`. The summary sent back to Gemini includes the raw output *and* a note confirming the values were stored.
3.  Gemini asks to run `DEFP MYPOS`.
4.  `main.py` runs it, gets "OK", sends that back.
5.  Gemini asks to run `SETPV MYPOS`.
6.  `main.py` detects `SETPV`, calls `handle_setpv_interactive`.
7.  `handle_setpv_interactive` checks `current_robot_state`, finds the values `[123, 456, ...]`.
8.  It sends `SETPV MYPOS`. Waits for "Enter Axis 1 value:", sends "123". Waits for "Enter Axis 2 value:", sends "456", etc. Waits for "OK".
9.  It packages a summary like "[SETPV Interaction... Sent value 123 for Axis 1... Sent value 456 for Axis 2... Received final 'OK']" into `next_gemini_input`.
10. Gemini receives this summary, confirming the operation succeeded using the intended data.