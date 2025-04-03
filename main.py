import time
import os
import argparse
import sys # For sys.exit()

# Import handlers from other files
from gemini_handler import GeminiHandler
from serial_handler import SerialHandler
from mock_serial_handler import MockSerialHandler
from camera_handler import CameraHandler

# --- Configuration Constants ---
INITIAL_PROMPT_FILE_DEFAULT = "initial_prompt.txt"
SCORBOT_MANUAL_PATH_DEFAULT = "scorbot_acl_manual.pdf" # Default name for the manual
IMAGE_CAPTURE_DIR = "captures"

# --- Main Application Logic ---
def main():
    # --- Argument Parser Setup ---
    parser = argparse.ArgumentParser(
        description="Control Scorbot ER VII with Gemini AI, using serial and webcam.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Shows defaults in help
    )
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
        print("*** RUNNING IN SIMULATION MODE (No real serial connection) ***")

    # --- Initialize Handlers ---
    print(f"Loading initial prompt from: {args.prompt}")
    try:
        with open(args.prompt, 'r') as f:
            initial_prompt = f.read()
    except FileNotFoundError:
        print(f"FATAL ERROR: Initial prompt file '{args.prompt}' not found.")
        sys.exit(1) # Exit if prompt is missing

    # Check if manual exists if provided, but GeminiHandler also checks
    if args.manual and not os.path.exists(args.manual):
         print(f"Warning: Specified manual file '{args.manual}' not found. Gemini will proceed without it.")

    print("Initializing Gemini Handler...")
    gemini = GeminiHandler(initial_prompt, manual_path=args.manual) # Pass manual path

    # --- Camera Setup ---
    camera = None # Initialize camera variable
    selected_camera_index = args.camera # Use command line arg if provided

    if selected_camera_index is None: # If not specified via command line, detect and ask
        available_cameras = CameraHandler.list_available_cameras()
        if not available_cameras:
            print("Warning: No cameras detected. Image capture and requests will not work.")
        elif len(available_cameras) == 1:
            selected_camera_index = available_cameras[0]
            print(f"Automatically selecting the only detected camera at index {selected_camera_index}.")
        else: # Multiple cameras found, ask user
            print("Available camera indices:")
            for idx in available_cameras:
                 # Provide some context if possible (often 0 is built-in)
                 label = "(likely built-in)" if idx == 0 else ""
                 print(f"  {idx} {label}")
            while True:
                try:
                    choice = input(f"Select the camera index to use (default {available_cameras[0]}): ")
                    if not choice.strip(): # User hit Enter for default
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
    # else: camera index was provided via --camera arg

    # Initialize CameraHandler if an index was determined
    if selected_camera_index is not None:
        print(f"Initializing Camera Handler for index {selected_camera_index}...")
        camera = CameraHandler(camera_index=selected_camera_index)
        if not camera.initialize_camera():
            print(f"Warning: Failed to initialize camera {selected_camera_index}. Image features disabled.")
            camera = None # Disable camera features if init fails

    # --- Serial Port Setup ---
    serial_comm = None # Initialize serial handler variable

    if args.simulate:
        print("Initializing Mock Serial Handler for simulation.")
        serial_comm = MockSerialHandler()
        # 'Connect' the mock handler (doesn't require real port/baud)
        if not serial_comm.connect("SIMULATED_PORT", args.baud):
             print("FATAL ERROR: Failed to initialize mock serial handler.")
             sys.exit(1)
    else: # Real serial connection
        print("Initializing Real Serial Handler.")
        serial_comm = SerialHandler()
        selected_port = args.port # Use command line arg if provided

        if selected_port is None: # If not specified via command line, detect and ask
            available_ports = serial_comm.list_ports()
            if not available_ports:
                print("FATAL ERROR: No serial ports found. Connect the Scorbot USB-Serial adapter and ensure drivers are installed.")
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
        # else: port was provided via --port arg

        # Attempt to connect to the selected real port
        print(f"Attempting to connect to {selected_port} at {args.baud} baud...")
        if not serial_comm.connect(selected_port, args.baud):
            print(f"FATAL ERROR: Failed to connect to serial port {selected_port}.")
            print("Check device connection, port name, baud rate, and permissions (e.g., user might need to be in 'dialout' or 'serial' group on Linux).")
            if camera: camera.release_camera() # Cleanup camera if opened
            sys.exit(1)

    # --- Ready message ---
    print("\n--- System Ready ---")
    print("Type your message/command for the robot.")
    print("Special Commands:")
    if not args.simulate:
        print("  /serial <raw_cmd>  - Send a raw command directly over serial.")
    print("  /view              - Show the last few messages received from serial.")
    if camera: # Only show capture command if camera is working
        print("  /capture           - Manually capture an image from the webcam.")
    print("  /quit              - Exit the application.")
    print("-" * 25)

    # --- Main Interaction Loop ---
    last_serial_response_sent_to_gemini = None # Track what we last told Gemini

    try:
        while True:
            # 1. Check for incoming serial data (non-blocking)
            received_line = serial_comm.get_received_line()
            if received_line:
                print(f"\n<-- [Serial Received]: {received_line}")
                # Store it to potentially send to Gemini on the *next* turn
                # Avoid immediately sending back to Gemini here to prevent potential loops,
                # unless a specific strategy for that is implemented.
                last_serial_response_sent_to_gemini = received_line # Store the latest to send next time

            # 2. Get user input
            try:
                 user_input = input("\n> You: ").strip()
            except EOFError: # Handle Ctrl+D
                 print("\nEOF detected. Exiting...")
                 break

            # 3. Handle local commands (prefixed with /)
            if user_input.lower() == '/quit':
                print("Exiting on user command.")
                break
            elif user_input.lower().startswith('/serial ') and not args.simulate:
                manual_cmd = user_input[len('/serial '):].strip()
                if manual_cmd:
                    print(f"--> [Manual Serial Send]: {manual_cmd}")
                    serial_comm.send_command(manual_cmd)
                    # Wait briefly for a potential immediate response after manual send
                    time.sleep(0.5)
                    # Check buffer again right away
                    response = serial_comm.get_received_line()
                    while response:
                         print(f"<-- [Serial Response]: {response}")
                         response = serial_comm.get_received_line()
                else:
                     print("Usage: /serial <command_to_send>")
                continue # Go back to prompt user without involving Gemini
            elif user_input.lower() == '/view':
                print("--- Received Serial Buffer (Snapshot) ---")
                buffered_lines = serial_comm.get_buffer_snapshot() # Get a copy
                if buffered_lines:
                    for line in buffered_lines[-10:]: # Show last 10 lines
                        print(f"  {line}")
                else:
                    print("  (Buffer is empty)")
                print("-" * 20)
                continue # Go back to prompt user
            elif user_input.lower() == '/capture' and camera:
                 print("--> [Manual Image Capture]")
                 filepath = camera.capture_image(IMAGE_CAPTURE_DIR, "manual_capture")
                 if filepath:
                     print(f"Image saved to {filepath}.")
                     # Ask user if they want to send this to Gemini
                     send_to_gemini = input("Send this captured image to Gemini? (y/n): ").lower().strip()
                     if send_to_gemini == 'y':
                         print("... Sending manual capture to Gemini ...")
                         # Include context that user captured this
                         gemini_response_text = gemini.send_message(
                             user_message_text="[User manually captured this image. Please observe.]",
                             image_path=filepath
                         )
                         # Display Gemini's reaction to the manual capture
                         parsed_text, _, _ = gemini.parse_response(gemini_response_text) # Ignore actions from this
                         print(f"\n< Gemini (reaction): {parsed_text}")
                 else:
                     print("Failed to capture image.")
                 continue # Go back to prompt user
            elif user_input.lower() == '/capture' and not camera:
                 print("Camera is not available or failed to initialize.")
                 continue

            # 4. Process regular user message with Gemini
            # Send user input AND the last serial message received (if any, and if not already sent)
            print("\n... Asking Gemini ...")
            gemini_response_text = gemini.send_message(
                user_message_text=user_input,
                serial_response=last_serial_response_sent_to_gemini # Send the last line received
            )
            # Reset the flag after sending it, so we don't send the same line twice
            last_serial_response_sent_to_gemini = None

            if gemini_response_text is None:
                print("Gemini did not provide a response or an error occurred.")
                continue # Ask user for input again

            # 5. Parse Gemini's response for actions
            text_to_show, serial_cmd_from_gemini, needs_image = gemini.parse_response(gemini_response_text)

            print(f"\n< Gemini: {text_to_show}") # Show Gemini's textual response first

            # 6. Execute Gemini's requested actions (in order: command, then image if needed)
            if serial_cmd_from_gemini:
                print(f"--> [Executing Gemini's Serial Command]: {serial_cmd_from_gemini}")
                if serial_comm.send_command(serial_cmd_from_gemini):
                     # Command sent successfully, wait a bit for robot to process/respond
                     # Adjust delay based on typical robot response time
                     print("    (Waiting briefly for robot response...)")
                     time.sleep(1.0) # Example: 1 second delay
                     # The read thread will pick up any response asynchronously.
                     # It will be printed when detected and sent to Gemini on the *next* user turn.
                else:
                    # Command failed to send (e.g., serial error)
                    print("    ERROR: Failed to send the command to the serial port.")
                    # Optionally inform Gemini about the failure? Be careful of loops.
                    # gemini.send_message(user_message_text="[System Note: Failed to send the previous serial command due to a serial communication error.]")

            if needs_image:
                if camera:
                    print("--> [Capturing Image for Gemini as Requested]")
                    filepath = camera.capture_image(IMAGE_CAPTURE_DIR, "gemini_request")
                    if filepath:
                        print("... Sending requested image to Gemini ...")
                        # Send the image back to Gemini immediately for analysis
                        gemini_follow_up_response = gemini.send_message(
                            user_message_text="[System Note: Here is the image you requested.]",
                            image_path=filepath
                        )
                        # Parse and display Gemini's response *after seeing the image*
                        follow_up_text, follow_up_cmd, follow_up_needs_img = gemini.parse_response(gemini_follow_up_response)
                        print(f"\n< Gemini (after image): {follow_up_text}")

                        # Handle potential *immediate* action based on the image
                        if follow_up_cmd:
                             print(f"--> [Executing Gemini's Serial Command after image]: {follow_up_cmd}")
                             if serial_comm.send_command(follow_up_cmd):
                                 time.sleep(1.0) # Wait after command
                             else:
                                 print("    ERROR: Failed to send the follow-up command.")
                        if follow_up_needs_img:
                            # Avoid immediate loop if Gemini asks for another image right away
                            print("Warning: Gemini requested another image immediately after receiving one. Ignoring second request for now.")
                    else:
                        print("ERROR: Failed to capture the requested image.")
                        # Inform Gemini about the failure
                        gemini.send_message(user_message_text="[System Note: Failed to capture the requested image due to a camera error.]")
                else:
                    print("Cannot fulfill image request: Camera is not available.")
                    # Inform Gemini
                    gemini.send_message(user_message_text="[System Note: Cannot capture image because the camera is not available or failed to initialize.]")

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting...")
    finally:
        # --- Cleanup ---
        print("\nShutting down and cleaning up resources...")
        if serial_comm: # Check if it was initialized
            print("Disconnecting serial port...")
            serial_comm.disconnect()
        if camera: # Check if it was initialized
             print("Releasing camera...")
             camera.release_camera()
        print("Goodbye!")

if __name__ == "__main__":
    main()