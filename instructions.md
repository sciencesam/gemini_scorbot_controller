
Okay, here is the complete file structure, the code for each file, and setup instructions for the refined version incorporating the manual upload, camera selection, and simulation mode.

**1. File Structure**

Create a directory for your project, for example, `gemini_scorbot_controller`. Inside this directory, create the following files and potentially add your manual PDF/TXT:

```
gemini_scorbot_controller/
├── main.py                 # Main application logic, CLI
├── gemini_handler.py       # Handles Gemini API interaction (incl. file upload)
├── serial_handler.py       # Manages REAL serial port communication
├── mock_serial_handler.py  # Manages SIMULATED serial communication
├── camera_handler.py       # Handles webcam capture and selection
├── initial_prompt.txt      # The starting prompt for Gemini
├── requirements.txt        # Lists Python dependencies
│
├── scorbot_acl_manual.pdf  # <-- PLACE YOUR SCORBOT MANUAL PDF/TXT HERE
│                           # (Make sure the filename matches the default or use --manual flag)
│
└── captures/               # Directory for captured images (will be created automatically)
```

**2. Code for Each File**

**`requirements.txt`:**
```txt
google-generativeai
pyserial
opencv-python
Pillow
```

**`initial_prompt.txt`:**
```text
You are an AI assistant controlling a Scorbot ER VII robotic arm connected via a serial interface. Your goal is to follow user instructions to manipulate the arm and report on its actions, using a webcam for visual feedback when necessary.

**Your Capabilities:**

1.  **Refer to Manual:** You have been provided with the 'Scorbot ACL Reference Manual'. **Please refer to this uploaded document as the primary and authoritative source for all Scorbot commands, syntax, parameters, and expected responses.** Use it diligently when formulating commands.
2.  **Send Serial Commands:** To send a command to the Scorbot, output the command *exactly* as specified in the manual, enclosed within `<SERIAL_CMD>` and `</SERIAL_CMD>` tags. For example: `<SERIAL_CMD>HOME</SERIAL_CMD>`. Only output one command tag per response. I will execute this command and provide the robot's response, if any, prefixed with `[SERIAL_RX]: `.
3.  **Receive Serial Data:** Any messages received from the robot over the serial port will be provided to you prefixed with `[SERIAL_RX]: `. Use this information to understand the robot's status or responses to your commands, cross-referencing with the manual if necessary.
4.  **Request Webcam Image:** To see the current state of the robot and its workspace, output the tag `<REQUEST_IMAGE/>`. I will capture an image from the webcam and provide it to you in the next turn. Use this for visual confirmation or assessment.
5.  **Chat:** You can converse normally with the user. Ask for clarification if a user request is ambiguous or requires information not readily available in the manual or current context.

**Robot Information Summary (Confirm with Manual):**

*   Robot Model: Scorbot ER VII
*   Communication: Serial (ASCII commands)
*   Command Termination: Typically Carriage Return (`\r`).
*   Key Task: Interpret user goals, translate them into correct ACL commands using the provided manual, manage interaction flow, and use visual feedback when needed.

**Task Context:**

*   You are connected to the robot via a serial port (real or simulated).
*   A webcam is pointed at the robot.
*   The user will give you tasks or ask questions.

**Your Goal:** Be a precise and helpful robot controller. Prioritize using the provided manual for command generation. Use `<SERIAL_CMD>COMMAND</SERIAL_CMD>` for actions and `<REQUEST_IMAGE/>` for visual checks. Acknowledge serial responses (`[SERIAL_RX]: ...`). Start by confirming you understand these instructions and have access to the manual.
```

**`gemini_handler.py`:**
```python
import google.generativeai as genai
from PIL import Image
import os
import time

# --- Configuration ---
# Best practice: Load API key from environment variable
# Ensure GOOGLE_API_KEY is set in your environment
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    print("ERROR: GOOGLE_API_KEY environment variable not set.")
    print("Please set the GOOGLE_API_KEY environment variable.")
    exit() # Exit if key is not set

MODEL_NAME = 'gemini-1.5-pro-latest'

class GeminiHandler:
    def __init__(self, initial_prompt_text, manual_path=None):
        """Initializes the Gemini Handler with the model and initial context."""
        self.model = genai.GenerativeModel(MODEL_NAME)
        self.uploaded_manual = None # Store reference to uploaded file object

        # --- Upload Manual if provided ---
        if manual_path and os.path.exists(manual_path):
            print(f"Uploading manual: {manual_path}...")
            try:
                # Give it a display name Gemini can potentially reference
                manual_file = genai.upload_file(path=manual_path,
                                                display_name="Scorbot ACL Reference Manual")
                print(f"Manual uploaded successfully. File Name: {manual_file.name}") # Use .name
                self.uploaded_manual = manual_file
                # Optional: Add check for file state if needed, but usually okay
                # time.sleep(2) # Small delay if issues occur
            except Exception as e:
                print(f"Error uploading manual {manual_path}: {e}")
                print("Proceeding without uploaded manual reference in initial context.")
                self.uploaded_manual = None
        elif manual_path:
            print(f"Warning: Manual file not found at {manual_path}. Proceeding without it.")

        # --- Prepare Initial Chat History ---
        initial_history = []
        initial_user_parts = [initial_prompt_text] # Start with the prompt text

        # If manual was uploaded successfully, add the file object to the parts list
        # The API expects the file object itself, not just the name/URI here.
        if self.uploaded_manual:
            initial_user_parts.append(self.uploaded_manual)
            print("Reference to uploaded manual added to initial user message.")

        # Add the complete initial user message (prompt + maybe file)
        initial_history.append({'role': 'user', 'parts': initial_user_parts})

        # Add the initial model response confirming understanding
        initial_history.append({'role': 'model', 'parts': ["Understood. I have received the initial instructions and the 'Scorbot ACL Reference Manual' if it was uploaded successfully. I will refer to it for command details. I am ready to assist with controlling the Scorbot ER VII using `<SERIAL_CMD>COMMAND</SERIAL_CMD>` and `<REQUEST_IMAGE/>` tags. Please provide serial responses prefixed with '[SERIAL_RX]: ' and images when requested."]})

        # Start the chat with the prepared history
        self.chat = self.model.start_chat(history=initial_history)
        print("Gemini chat initialized.")

    def send_message(self, user_message_text=None, image_path=None, serial_response=None):
        """Sends a message (text, image, or serial response) to Gemini."""
        parts = []

        # Note: Including the manual reference on *every* turn is generally not needed
        # if it was included correctly in the initial history for Gemini 1.5 Pro.
        # The model should maintain context. Test this behavior.

        if user_message_text:
            parts.append(user_message_text)
        if image_path:
            try:
                img = Image.open(image_path)
                parts.append(img)
                print(f"Attaching image: {image_path}")
            except Exception as e:
                print(f"Error loading image {image_path}: {e}")
                parts.append(f"[System Note: Failed to load image: {image_path}]") # Inform Gemini
        if serial_response:
             # Prefix serial responses clearly
            parts.append(f"[SERIAL_RX]: {serial_response}")

        if not parts:
            print("Warning: Attempted to send an empty message to Gemini.")
            return None

        try:
            print("Sending message to Gemini...")
            # Set safety settings if needed, though defaults are usually reasonable
            # safety_settings={'HARASSMENT':'block_none', 'HATE_SPEECH': 'block_none', ...}
            response = self.chat.send_message(parts, stream=False) # Use stream=True for typing effect
            print("Received response from Gemini.")
            # Basic check if response was blocked
            if not response.parts:
                 print("Warning: Gemini response was empty or blocked.")
                 return "[System Note: Gemini response was empty or blocked by safety filters.]"
            return response.text
        except Exception as e:
            print(f"Error communicating with Gemini: {e}")
            # Consider more specific error handling (e.g., google.api_core.exceptions...)
            return f"[System Error: Could not get response from Gemini: {e}]"

    def parse_response(self, gemini_response):
        """
        Parses Gemini's response to find commands or image requests.
        Returns: (text_for_user, serial_command, request_image_flag)
        """
        if not gemini_response:
            return "Gemini did not respond.", None, False

        text_for_user = gemini_response
        serial_command = None
        request_image_flag = False

        # Simple parsing for specific tags (can be made more robust with regex)
        cmd_start_tag = "<SERIAL_CMD>"
        cmd_end_tag = "</SERIAL_CMD>"
        img_req_tag = "<REQUEST_IMAGE/>"

        # Check for image request first
        if img_req_tag in text_for_user:
            request_image_flag = True
            # Remove the tag from the user-facing text for clarity
            text_for_user = text_for_user.replace(img_req_tag, "[Requesting Image]").strip()
            print("Gemini requested an image.")

        # Check for serial command
        cmd_start_index = text_for_user.find(cmd_start_tag)
        if cmd_start_index != -1:
            cmd_end_index = text_for_user.find(cmd_end_tag, cmd_start_index)
            if cmd_end_index != -1:
                serial_command = text_for_user[cmd_start_index + len(cmd_start_tag):cmd_end_index].strip()
                # Remove the command part from the user-facing text for better readability
                text_for_user = (text_for_user[:cmd_start_index].strip() + " " + \
                                 f"[Sending Command: {serial_command}]" + " " + \
                                 text_for_user[cmd_end_index + len(cmd_end_tag):].strip()).strip()
                # Ensure we don't have double spacing if tags were at start/end
                text_for_user = ' '.join(text_for_user.split())
                print(f"Gemini requested serial command: {serial_command}")
            else:
                 print(f"Warning: Found '{cmd_start_tag}' but no matching '{cmd_end_tag}'.")

        return text_for_user, serial_command, request_image_flag

```

**`serial_handler.py`:**
```python
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

```

**`mock_serial_handler.py`:**
```python
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

```

**`camera_handler.py`:**
```python
import cv2
import time
import os

class CameraHandler:
    def __init__(self, camera_index=0):
        """Initializes the camera handler with a specific index."""
        self.camera_index = camera_index
        self.cap = None
        print(f"Camera Handler configured for camera index: {self.camera_index}")

    def initialize_camera(self):
        """Opens the camera feed specified by camera_index."""
        if self.cap is not None and self.cap.isOpened():
            print(f"Camera {self.camera_index} already initialized.")
            return True
        try:
            print(f"Attempting to initialize camera index: {self.camera_index}...")
            # Try different APIs if default fails, sometimes needed on specific OS/hardware
            # self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_ANY) # Try auto-detect
            self.cap = cv2.VideoCapture(self.camera_index)

            if not self.cap.isOpened():
                print(f"ERROR: Could not open camera stream for index {self.camera_index}.")
                print("Check if camera is connected, not used by another app, and permissions are granted.")
                self.cap = None
                return False

            # Set properties *after* opening
            # Optional: Set resolution (check supported resolutions for your camera)
            # width = 640
            # height = 480
            # self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            # self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # Read one frame to ensure connection is working and buffer populated
            ret, _ = self.cap.read()
            if not ret:
                 print(f"Warning: Camera {self.camera_index} opened but failed to read initial frame.")
                 # Keep trying, might stabilise
            else:
                 print(f"Successfully read initial frame from camera {self.camera_index}.")


            print(f"Camera {self.camera_index} initialized.")
            # Allow camera to stabilize/auto-adjust
            time.sleep(1.0) # Increased delay can help
            return True
        except Exception as e:
            print(f"ERROR: Exception initializing camera {self.camera_index}: {e}")
            if self.cap: # Ensure cap is released if partially opened
                 self.cap.release()
            self.cap = None
            return False

    def capture_image(self, output_dir="captures", filename_prefix="capture"):
        """Captures a single frame and saves it to a file."""
        if self.cap is None or not self.cap.isOpened():
            print("Camera not initialized or already released. Trying to re-initialize...")
            if not self.initialize_camera():
                print("ERROR: Failed to initialize camera for capture.")
                return None
            # Add a small delay after re-initialization
            time.sleep(0.5)

        # Try reading a few frames to discard stale ones
        for _ in range(3):
             ret, frame = self.cap.read()
             if not ret:
                 time.sleep(0.1) # Wait briefly if read fails

        # Read the final frame
        ret, frame = self.cap.read()
        if not ret or frame is None:
            print("ERROR: Failed to capture frame from camera.")
            # Consider releasing and trying re-init next time?
            # self.release_camera()
            return None

        # Ensure output directory exists
        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
        except OSError as e:
             print(f"ERROR: Could not create capture directory '{output_dir}': {e}")
             return None # Cannot save image

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(output_dir, f"{filename_prefix}_{timestamp}.jpg")

        try:
            # Save the captured frame as a JPG image
            success = cv2.imwrite(filepath, frame)
            if success:
                print(f"Image captured and saved to {filepath}")
                return filepath
            else:
                # imwrite can fail if path is invalid, disk full, permissions etc.
                print(f"ERROR: Failed to save image to {filepath} (cv2.imwrite returned false).")
                return None
        except Exception as e:
            # Catch potential errors during file writing
            print(f"ERROR: Exception occurred while saving image: {e}")
            return None

    def release_camera(self):
        """Releases the camera resource."""
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            print(f"Camera {self.camera_index} released.")
        self.cap = None
        # cv2.destroyAllWindows() # Avoid if not managing windows directly here

    @staticmethod
    def list_available_cameras(max_to_test=5):
        """Tries to open camera indices to see which are available. Returns a list of valid indices."""
        available_indices = []
        print(f"Detecting available cameras (checking indices 0 to {max_to_test-1})...")
        for i in range(max_to_test):
            cap = cv2.VideoCapture(i)
            if cap is not None and cap.isOpened():
                # Try reading a frame to be more certain it's usable
                ret, _ = cap.read()
                if ret:
                    print(f"  Camera found and readable at index {i}")
                    available_indices.append(i)
                else:
                    print(f"  Camera opened at index {i}, but failed to read frame (might be busy or unusable).")
                cap.release()
            # else:
                # print(f"  No camera detected at index {i}.") # Can be verbose
        if not available_indices:
             print("No readily usable cameras detected by OpenCV.")
        else:
             print(f"Detected usable camera indices: {available_indices}")
        return available_indices

```

**`main.py`:**
```python
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
```

**3. Setup and Running Instructions**

1.  **Prerequisites:**
    *   Python 3.7 or newer installed.
    *   `pip` (Python package installer).
    *   Git (optional, for cloning if you host this).

2.  **Download/Create Files:**
    *   Create the project directory: `mkdir gemini_scorbot_controller`
    *   `cd gemini_scorbot_controller`
    *   Save each code block above into its corresponding filename (e.g., `main.py`, `gemini_handler.py`, etc.) within this directory.
    *   Save the `requirements.txt` file.
    *   Save the `initial_prompt.txt` file.
    *   **Crucially:** Obtain a copy of your Scorbot ER VII's ACL command reference manual (preferably as a PDF or TXT file) and place it in this directory. Rename it to `scorbot_acl_manual.pdf` (or `.txt`) or be prepared to use the `--manual` command-line flag later with the correct path/filename.

3.  **Set up Virtual Environment (Recommended):**
    *   `python3 -m venv venv` (or `python -m venv venv`)
    *   Activate it:
        *   macOS/Linux: `source venv/bin/activate`
        *   Windows (cmd): `venv\Scripts\activate.bat`
        *   Windows (PowerShell): `venv\Scripts\Activate.ps1` (You might need to set execution policy: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`)

4.  **Install Dependencies:**
    *   `pip install -r requirements.txt`

5.  **Get Google AI API Key:**
    *   Go to [Google AI Studio](https://aistudio.google.com/).
    *   Create an API key.
    *   **Set Environment Variable:** You *must* set the `GOOGLE_API_KEY` environment variable for the script to authenticate.
        *   macOS/Linux (temporary for current session):
            ```bash
            export GOOGLE_API_KEY='YOUR_API_KEY_HERE'
            ```
        *   Windows (cmd - temporary for current session):
            ```cmd
            set GOOGLE_API_KEY=YOUR_API_KEY_HERE
            ```
        *   Windows (PowerShell - temporary for current session):
            ```powershell
            $env:GOOGLE_API_KEY='YOUR_API_KEY_HERE'
            ```
        *   (For permanent setting, add it to your `.bashrc`, `.zshrc`, `.profile`, or System Environment Variables on Windows). **Do not hardcode the key in the script.**

6.  **Connect Hardware (for non-simulation mode):**
    *   Connect your Scorbot's USB-to-Serial adapter to your Mac.
    *   Connect your desired webcam (or ensure your iPhone is ready for Continuity Camera if you plan to select it).

7.  **Run the Application:**
    *   **Simulation Mode:** Test without connecting to the real robot. It will use the `MockSerialHandler`.
        ```bash
        python main.py --simulate
        ```
        (You can also add `--manual /path/to/different_manual.pdf` if needed).
    *   **Real Robot Mode (Interactive Selection):** The script will list detected serial ports and cameras (if multiple) and ask you to choose.
        ```bash
        python main.py --baud 9600 # Or your robot's baud rate
        ```
    *   **Real Robot Mode (Specify Port/Camera):** If you know the exact port and camera index:
        ```bash
        # Example for macOS:
        python main.py --port /dev/tty.usbserial-A12B3CD4 --baud 9600 --camera 1

        # Example for Linux:
        # python main.py --port /dev/ttyUSB0 --baud 9600 --camera 0

        # Example for Windows:
        # python main.py --port COM3 --baud 9600 --camera 0
        ```
        (Use the actual port name found on your system. Find it using `ls /dev/tty.*` on macOS/Linux or Device Manager on Windows. Find camera index via trial/error or the detection list).

8.  **Interact:**
    *   Follow the prompts to select the serial port and/or camera if needed.
    *   Once "System Ready" appears, type messages for Gemini (e.g., "Send the robot home", "What is the robot's status?", "Move joint 1 to 90 degrees").
    *   Use the special commands like `/view`, `/capture`, `/serial` (only in real mode), and `/quit`.
    *   Observe the output for messages sent (`[SERIAL_TX]`), messages received (`[SERIAL_RX]`), Gemini responses (`< Gemini:`), and system actions/errors.

Remember to consult your Scorbot manual for the correct commands and baud rate. Good luck!