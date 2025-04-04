# main.py
import time
import os
import argparse
import sys # For sys.exit()

# Import handlers
from gemini_handler import GeminiHandler
from serial_handler import SerialHandler # Use this by default
from mock_serial_handler import MockSerialHandler # Use if --simulate
from camera_handler import CameraHandler

# --- Configuration Constants ---
INITIAL_PROMPT_FILE_DEFAULT = "initial_prompt.txt"
SCORBOT_MANUAL_PATH_DEFAULT = "scorbot_acl_manual.pdf"
IMAGE_CAPTURE_DIR = "captures"
SERIAL_RESPONSE_TIMEOUT = 90.0 # Max seconds to wait for *any* response after sending cmd
SERIAL_INTER_MESSAGE_TIMEOUT = 1.5 # Max seconds to wait between lines of a multi-line response
# --- Adjust SERIAL_INTER_MESSAGE_TIMEOUT based on observed robot behavior ---
# If the robot sends multiple lines quickly, this can be shorter (e.g., 0.5s).
# If there are pauses between valid response lines, it needs to be longer.

# --- Helper Function ---
def is_slash_command(text):
    """Checks if the input is a local slash command."""
    return text.startswith('/')

def wait_for_serial_response(serial_comm, sent_command):
    """
    Waits for and collects serial response lines after a command is sent.
    Returns a string containing all response lines, or a system note on timeout/error.
    """
    responses = []
    start_time = time.time()
    last_rx_time = start_time
    timed_out = False
    inter_message_timed_out = False

    print(f"    (Waiting for response to '{sent_command}' - Max {SERIAL_RESPONSE_TIMEOUT}s total, {SERIAL_INTER_MESSAGE_TIMEOUT}s between lines)")

    while True:
        # Check overall timeout
        if time.time() - start_time > SERIAL_RESPONSE_TIMEOUT:
            print("    (Overall response timeout reached.)")
            timed_out = True
            break

        line = serial_comm.get_received_line() # Handler already prints RX line

        if line is not None: # Received something
            responses.append(line)
            last_rx_time = time.time() # Reset inter-message timer
            # --- Add logic here if a specific line signals command completion ---
            # Example: Check for Scorbot's typical prompt or completion message
            # if line.strip() == ">" or line.strip().upper() == "OK":
            #    print("    (Detected likely end-of-response marker)")
            #    break # Optional: Exit early if terminator found
            # Example: Check for specific completion message from prompt for HOME
            if sent_command.upper() == "HOME" and "Homing complete(robot)" in line:
                print("    (Detected 'Homing complete' message)")
                # Give a tiny bit more time in case 'OK' follows immediately
                time.sleep(0.2)
                # Check one last time for any immediate follow-up line
                final_line = serial_comm.get_received_line()
                if final_line is not None:
                     responses.append(final_line)
                break # Consider HOME complete after this specific message

        else: # No line received right now
            # Check inter-message timeout
            if time.time() - last_rx_time > SERIAL_INTER_MESSAGE_TIMEOUT:
                if responses: # Had previous lines, but now a pause
                    print("    (Timeout waiting for *further* response lines.)")
                    inter_message_timed_out = True
                # If no responses were ever received, the main timeout will handle it.
                break
            # No line, but not timed out yet, wait briefly
            time.sleep(0.05) # Avoid busy-waiting

    # --- Format the response for Gemini ---
    if responses:
        # Join collected lines into a single multi-line string
        full_response = "\n".join(responses)
        # Add context about the command that triggered this response
        result = f"[SERIAL_RX for '{sent_command}']: {full_response}"
        if timed_out:
            result += "\n[System Note: Overall response timeout reached during reception.]"
        elif inter_message_timed_out:
             result += "\n[System Note: Stopped waiting for further lines due to inter-message timeout.]"
        return result
    elif timed_out:
        print(f"    (Timeout: No response received for '{sent_command}' within {SERIAL_RESPONSE_TIMEOUT}s)")
        return f"[System Note: Sent '{sent_command}', but received no response within timeout.]"
    else:
         # This case should be rare if timeouts work correctly, but handle it.
         print(f"    (No response collected for '{sent_command}', but no explicit timeout state?)")
         return f"[System Note: Sent '{sent_command}', received no response.]"


# --- Main Application Logic ---
def main():
    # --- Argument Parser Setup ---
    parser = argparse.ArgumentParser(
        description="Control Scorbot ER VII with Gemini AI, using serial and webcam.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # ... (keep all existing arguments: --simulate, --manual, --prompt, --baud, --port, --camera) ...
    parser.add_argument(
        '--simulate',
        action='store_true',
        help="Run in simulation mode using MockSerialHandler instead of real serial port."
    )
    parser.add_argument(
        '--manual',
        type=str,
        default=SCORBOT_MANUAL_PATH_DEFAULT,
        help="Path to the Scorbot manual file (PDF, TXT, etc.) for Gemini."
    )
    parser.add_argument(
        '--prompt',
        type=str,
        default=INITIAL_PROMPT_FILE_DEFAULT,
        help="Path to the initial prompt instructions file for Gemini."
    )
    parser.add_argument(
        '--baud',
        type=int,
        default=9600,
        help="Baud rate for the serial connection (if not simulating)."
    )
    parser.add_argument(
        '--port',
        type=str,
        default=None,
        help="Specify the serial port directly (e.g., /dev/tty.usbserial-XXXX or COM3). Skips interactive selection if provided."
    )
    parser.add_argument(
        '--camera',
        type=int,
        default=None,
        help="Specify the camera index directly. Skips interactive selection if provided."
    )
    args = parser.parse_args()

    print("--- Gemini Scorbot Controller ---")
    if args.simulate:
        print("*** RUNNING IN SIMULATION MODE (Using Mock Serial Handler) ***")
        # In simulation, use the mock handler
        SerialOrMockHandler = MockSerialHandler
    else:
        print("*** RUNNING IN LIVE MODE (Using Real Serial Handler) ***")
        # In live mode, use the real handler
        SerialOrMockHandler = SerialHandler


    # --- Initialize Handlers ---
    print(f"Loading initial prompt from: {args.prompt}")
    try:
        with open(args.prompt, 'r') as f:
            initial_prompt = f.read()
    except FileNotFoundError:
        print(f"FATAL ERROR: Initial prompt file '{args.prompt}' not found.")
        sys.exit(1)

    if args.manual and not os.path.exists(args.manual):
         print(f"Warning: Specified manual file '{args.manual}' not found. Gemini will proceed without it.")

    print("Initializing Gemini Handler...")
    # Make sure GOOGLE_API_KEY is set in environment! GeminiHandler checks this.
    try:
        gemini = GeminiHandler(initial_prompt, manual_path=args.manual)
    except Exception as e:
        print(f"FATAL ERROR: Failed to initialize Gemini Handler: {e}")
        # Specific check for missing API key (although handler tries to print this)
        if "GOOGLE_API_KEY" in str(e) or "API key" in str(e):
             print("Ensure the GOOGLE_API_KEY environment variable is set correctly.")
        sys.exit(1)

    # --- Camera Setup ---
    # ... (Camera setup logic remains the same as before) ...
    camera = None
    selected_camera_index = args.camera
    if selected_camera_index is None:
        available_cameras = CameraHandler.list_available_cameras()
        if not available_cameras:
            print("Warning: No cameras detected. Image capture and requests will not work.")
        elif len(available_cameras) == 1:
            selected_camera_index = available_cameras[0]
            print(f"Automatically selecting the only detected camera at index {selected_camera_index}.")
        else:
            print("Available camera indices:")
            for idx in available_cameras:
                 label = "(likely built-in)" if idx == 0 else ""
                 print(f"  {idx} {label}")
            while True:
                try:
                    choice = input(f"Select the camera index to use (default {available_cameras[0]}): ")
                    if not choice.strip():
                         selected_camera_index = available_cameras[0]
                         print(f"Using default camera index {selected_camera_index}")
                         break
                    choice_int = int(choice)
                    if choice_int in available_cameras:
                        selected_camera_index = choice_int
                        break
                    else:
                        print("Invalid choice. Please select from the available indices.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

    if selected_camera_index is not None:
        print(f"Initializing Camera Handler for index {selected_camera_index}...")
        camera = CameraHandler(camera_index=selected_camera_index)
        if not camera.initialize_camera():
            print(f"Warning: Failed to initialize camera {selected_camera_index}. Image features disabled.")
            camera = None

    # --- Serial Port Setup ---
    print("Initializing Serial Handler...")
    serial_comm = SerialOrMockHandler() # Use the class selected based on --simulate
    selected_port = args.port

    if args.simulate:
        # 'Connect' the mock handler
        if not serial_comm.connect("SIMULATED_PORT", args.baud):
             print("FATAL ERROR: Failed to initialize mock serial handler.")
             if camera: camera.release_camera()
             sys.exit(1)
    else: # Real serial connection setup (only if not simulating)
        if selected_port is None:
            available_ports = serial_comm.list_ports()
            if not available_ports:
                print("FATAL ERROR: No serial ports found. Connect the Scorbot USB-Serial adapter and ensure drivers are installed.")
                if camera: camera.release_camera()
                sys.exit(1)

            print("Available serial ports:")
            for i, p in enumerate(available_ports):
                print(f"  {i}: {p}")

            while True:
                try:
                    choice = input(f"Select the serial port number for the Scorbot (0-{len(available_ports)-1}): ")
                    choice_int = int(choice)
                    if 0 <= choice_int < len(available_ports):
                        selected_port = available_ports[choice_int]
                        break
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Please enter a number.")

        print(f"Attempting to connect to {selected_port} at {args.baud} baud...")
        if not serial_comm.connect(selected_port, args.baud):
            print(f"FATAL ERROR: Failed to connect to serial port {selected_port}.")
            print("Check device connection, port name, baud rate, permissions.")
            if camera: camera.release_camera()
            sys.exit(1)


    # --- Ready message ---
    print("\n--- System Ready ---")
    print("Type your message/command for the robot, or a local command.")
    print("Local Commands:")
    if not args.simulate:
        print("  /serial <raw_cmd>  - Send a raw command directly (bypasses Gemini).")
    print("  /view              - Show recent raw lines from serial buffer (debug).") # Keep for debug
    if camera:
        print("  /capture           - Manually capture an image from the webcam.")
    print("  /quit              - Exit the application.")
    print("-" * 25)

    # --- Main Interaction Loop (Revised Structure) ---
    # This loop now prioritizes processing Gemini's actions (commands, image requests)
    # and their results before asking for new user input.
    next_gemini_input = {} # Dictionary to hold parts for the *next* call to gemini.send_message

    try:
        while True:
            gemini_triggered_action = False # Flag to see if Gemini's response needs immediate processing

            # --- Step 1: Prepare and Send to Gemini (if there's input) ---
            if next_gemini_input:
                print("\n... Asking Gemini (based on previous action/response)...")
                # Clear buffer snapshot just before sending response to avoid re-sending old async messages
                serial_comm.get_buffer_snapshot() # Read and discard anything in buffer now
                gemini_response_text = gemini.send_message(**next_gemini_input)
                next_gemini_input = {} # Clear the input queue
            else:
                # No pending action, get user input
                # Drain any stray async messages received before asking user
                stray_lines = []
                while True:
                     line = serial_comm.get_received_line()
                     if line is None: break
                     stray_lines.append(line)
                if stray_lines:
                     print(f"--- Note: Received {len(stray_lines)} async serial lines before user prompt ---")
                     # Optionally, decide if these should be sent to Gemini later or ignored
                     # For now, they were printed by the handler, we just drain the buffer.

                try:
                    user_input = input("\n> You: ").strip()
                except EOFError:
                    print("\nEOF detected. Exiting...")
                    break

                # Handle local commands first
                if is_slash_command(user_input):
                    if user_input.lower() == '/quit':
                        break
                    elif user_input.lower().startswith('/serial ') and not args.simulate:
                        manual_cmd = user_input[len('/serial '):].strip()
                        if manual_cmd:
                            print(f"--> [Manual Serial Send]: {manual_cmd}")
                            serial_comm.send_command(manual_cmd)
                            # Manually sent commands bypass Gemini loop for now
                            # User will see raw response via RX prints.
                            # We could optionally add a wait/collect here too if needed.
                            time.sleep(0.5) # Brief pause
                        else:
                             print("Usage: /serial <command_to_send>")
                        continue # Ask for user input again
                    elif user_input.lower() == '/view':
                        print("--- Received Serial Buffer (Snapshot) ---")
                        buffered_lines = serial_comm.get_buffer_snapshot()
                        if buffered_lines:
                            for line in buffered_lines[-15:]: # Show last 15
                                print(f"  {line}")
                        else:
                            print("  (Buffer is empty or lines were handled)")
                        print("-" * 20)
                        continue # Ask for user input again
                    elif user_input.lower() == '/capture' and camera:
                         print("--> [Manual Image Capture]")
                         filepath = camera.capture_image(IMAGE_CAPTURE_DIR, "manual_capture")
                         if filepath:
                             print(f"Image saved to {filepath}.")
                             send_to_gemini = input("Send this captured image to Gemini? (y/n): ").lower().strip()
                             if send_to_gemini == 'y':
                                 # Prepare to send this image in the next loop iteration
                                 next_gemini_input = {
                                     'user_message_text': "[User manually captured this image. Please observe.]",
                                     'image_path': filepath
                                 }
                                 # Continue will loop back and send this to Gemini
                                 continue
                         else:
                             print("Failed to capture image.")
                         continue # Ask for user input again (if not sending)
                    elif user_input.lower() == '/capture' and not camera:
                         print("Camera is not available or failed to initialize.")
                         continue
                    else: # Unknown slash command
                        print(f"Unknown local command: {user_input}")
                        continue # Ask for user input again

                # Regular user input, send to Gemini
                print("\n... Asking Gemini (based on user input)...")
                gemini_response_text = gemini.send_message(user_message_text=user_input)

            # --- Step 2: Parse Gemini's Response ---
            if gemini_response_text is None:
                print("Warning: Gemini did not provide a response or an error occurred.")
                # Loop will ask for user input again as next_gemini_input is empty
                continue

            text_to_show, serial_cmd_from_gemini, needs_image = gemini.parse_response(gemini_response_text)
            print(f"\n< Gemini: {text_to_show}") # Show Gemini's textual response

            # --- Step 3: Handle Actions Requested by Gemini ---
            if serial_cmd_from_gemini:
                gemini_triggered_action = True # Mark that we need to loop back
                # Send the command
                if serial_comm.send_command(serial_cmd_from_gemini):
                    # Wait for and collect the response
                    response_data = wait_for_serial_response(serial_comm, serial_cmd_from_gemini)
                    # Prepare the collected response for the *next* Gemini call
                    next_gemini_input = {'serial_response': response_data}
                else:
                    # Command failed to send (e.g., serial error)
                    print("    ERROR: Failed to send the command to the serial port.")
                    # Inform Gemini about the failure in the next turn
                    next_gemini_input = {
                        'user_message_text': f"[System Note: Failed to send the previous serial command ('{serial_cmd_from_gemini}') due to a serial communication error.]"
                    }

            elif needs_image: # Gemini requested an image (and didn't send a command)
                 gemini_triggered_action = True # Mark that we need to loop back
                 if camera:
                     print("--> [Capturing Image for Gemini as Requested]")
                     filepath = camera.capture_image(IMAGE_CAPTURE_DIR, "gemini_request")
                     if filepath:
                         print("... Image captured, will send to Gemini next.")
                         # Prepare the image path for the *next* Gemini call
                         next_gemini_input = {
                              'user_message_text': "[System Note: Here is the image you requested.]",
                              'image_path': filepath
                         }
                     else:
                         print("ERROR: Failed to capture the requested image.")
                         # Inform Gemini about the failure in the next turn
                         next_gemini_input = {
                             'user_message_text': "[System Note: Failed to capture the requested image due to a camera error.]"
                         }
                 else:
                     print("Cannot fulfill image request: Camera is not available.")
                     # Inform Gemini about the failure in the next turn
                     next_gemini_input = {
                          'user_message_text': "[System Note: Cannot capture image because the camera is not available or failed to initialize.]"
                     }

            # --- Step 4: Loop Control ---
            # If Gemini triggered an action (command or image request),
            # we 'continue' to loop immediately and process the result (send response/image to Gemini).
            # Otherwise (Gemini just chatted or finished an action sequence),
            # the loop will naturally proceed to ask for user input again in the next iteration
            # because next_gemini_input will be empty.
            if gemini_triggered_action:
                continue

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting...")
    finally:
        # --- Cleanup ---
        print("\nShutting down and cleaning up resources...")
        if serial_comm:
            print("Disconnecting serial port...")
            serial_comm.disconnect()
        if camera:
             print("Releasing camera...")
             camera.release_camera()
        print("Goodbye!")

if __name__ == "__main__":
    main()