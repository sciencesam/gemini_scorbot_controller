Okay, here is the complete `main.py` file with the syntax error corrected in the async message draining section.

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
                 # Ensure self.ser is used for the actual serial object if not mock
                 if hasattr(serial_comm, 'ser') and serial_comm.ser:
                     serial_comm.ser.write(full_value_cmd.encode('ascii'))
                 else:
                     # This case shouldn't happen if connected, but is a safeguard
                      raise serial.SerialException("Serial object 'ser' not available in handler.")

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
    print(f"Loading initial prompt from: {args.prompt}")
    try:
        with open(args.prompt, 'r') as f: initial_prompt = f.read()
    except FileNotFoundError: print(f"FATAL ERROR: Initial prompt file '{args.prompt}' not found."); sys.exit(1)
    if args.manual and not os.path.exists(args.manual): print(f"Warning: Manual file '{args.manual}' not found.")
    print("Initializing Gemini Handler...")
    try:
        gemini = GeminiHandler(initial_prompt, manual_path=args.manual)
    except Exception as e: print(f"FATAL ERROR: Failed to initialize Gemini Handler: {e}"); sys.exit(1)

    # Camera setup
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

    # Serial setup
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
                gemini_response_text = gemini.send_message(**next_gemini_input)
                next_gemini_input = {}
            else:
                 # --- CORRECTED DRAIN LOGIC ---
                 stray_lines = [] # Initialize list to store stray lines
                 # print("--- Checking for async serial messages before prompt ---") # Optional: Add visibility
                 while True:
                     line = serial_comm.get_received_line() # Poll for a line
                     if line is None:
                         break # Exit the while loop if no more lines are waiting
                     # If line is not None, append it
                     stray_lines.append(line)
                     # time.sleep(0.01) # Optional: prevent overly fast spinning if needed

                 if stray_lines:
                     # Lines were already printed by handler's RX print
                     print(f"--- Handled {len(stray_lines)} async serial lines before user prompt ---")
                 # --- END CORRECTED DRAIN LOGIC ---

                 # Now, get user input
                 try:
                    user_input = input("\n> You: ").strip()
                 except EOFError:
                    print("\nEOF detected. Exiting...")
                    break

                 # Handle Local Commands
                 if is_slash_command(user_input):
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

                 # Regular user input to Gemini
                 print("\n... Asking Gemini (based on user input)...")
                 gemini_response_text = gemini.send_message(user_message_text=user_input)

            # --- Step 2: Parse Gemini's Response ---
            if gemini_response_text is None: print("Warning: Gemini gave no response."); continue
            text_to_show, serial_cmd_from_gemini, needs_image = gemini.parse_response(gemini_response_text)
            print(f"\n< Gemini: {text_to_show}")

            # --- Step 3: Handle Gemini's Actions ---
            if serial_cmd_from_gemini:
                gemini_triggered_action = True
                command_base = ""
                if serial_cmd_from_gemini.strip(): # Check if command is not empty
                     command_base = serial_cmd_from_gemini.split()[0].upper()

                # --- Check if it's SETPV (interactive) ---
                if command_base == "SETPV" and len(serial_cmd_from_gemini.split()) > 1:
                    # Call the specialized handler
                    response_summary_for_gemini = handle_setpv_interactive(serial_comm, serial_cmd_from_gemini, current_robot_state)
                elif serial_cmd_from_gemini.strip(): # Ensure it's not an empty command string
                    # --- Handle regular commands ---
                    if serial_comm.send_command(serial_cmd_from_gemini):
                        # Wait for and process the response
                        response_summary_for_gemini = wait_for_serial_response(serial_comm, serial_cmd_from_gemini)
                    else:
                        # Failed to send command
                        print(f"    ERROR: Failed to send command '{serial_cmd_from_gemini}' to serial port.")
                        response_summary_for_gemini = f"[System Note: Failed to send command '{serial_cmd_from_gemini}' due to serial error.]"
                else:
                     # Gemini generated an empty/invalid command tag
                     print("Warning: Gemini generated an empty serial command tag.")
                     response_summary_for_gemini = "[System Note: Received empty serial command from Gemini.]"


                # Prepare response for next Gemini call
                next_gemini_input = {'serial_response': response_summary_for_gemini}

            elif needs_image:
                 gemini_triggered_action = True
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
        # Check if handlers were initialized before trying to clean up
        if 'serial_comm' in locals() and serial_comm:
            print("Disconnecting serial..."); serial_comm.disconnect()
        if 'camera' in locals() and camera:
             print("Releasing camera..."); camera.release_camera()
        print("Goodbye!")

if __name__ == "__main__":
    main()
```