# Gemini Scorbot Controller

**Control a Scorbot ER VII robotic arm using natural language commands powered by Google Gemini, with integrated webcam vision and serial communication.**

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

This project provides a command-line interface (CLI) to interact with a Scorbot ER VII robot arm connected via a serial port. It leverages the Google Gemini AI model to interpret user requests, translate them into appropriate Scorbot ACL (Arm Control Language) commands based on a provided manual, and manage the interaction flow. The system can use a webcam for visual feedback, requesting images when necessary and confirming with the user before capturing, making it suitable for cameras requiring manual positioning (like iPhones via Continuity Camera). It also features a simulation mode for testing without hardware and automates specific command sequences like reading joint positions (`LISTPV POSITION`) and setting them (`SETPV <name>`) interactively.

## Features

*   **Natural Language Control:** Instruct the robot using plain English (e.g., "Send the robot home", "Define a point named 'pickup' at the current location").
*   **Gemini AI Integration:** Uses Google's `gemini-1.5-pro-latest` model for command understanding and generation.
*   **Manual-Based Commands:** Gemini refers to an uploaded Scorbot ACL manual (PDF/TXT) to ensure command accuracy.
*   **Serial Communication:** Interfaces with the Scorbot controller via a standard USB-to-Serial adapter (Real mode).
*   **Simulation Mode:** Run the application without connecting to the actual robot hardware using a mock serial handler.
*   **Webcam Vision:**
    *   Gemini can request images (`<REQUEST_IMAGE/>`) for visual assessment.
    *   User confirmation prompt before any image capture (manual or Gemini-requested).
    *   Manual image capture command (`/capture`).
*   **Interactive Setup:** Automatically detects and prompts for serial port and camera selection if multiple are found (can be overridden by flags).
*   **State Management:** Remembers joint values read via `LISTPV POSITION` to automatically populate prompts during interactive `SETPV <name>` commands.
*   **Real-time Feedback:** Displays serial commands sent (`--> [SERIAL_TX]:`), responses received (`<-- [SERIAL_RX]:`), Gemini messages (`< Gemini:`), and system notes.
*   **Manual Override:** Send raw serial commands directly using `/serial <command>`.

## File Structure

```
gemini_scorbot_controller/
├── main.py                 # Main application logic, CLI, interaction loop
├── gemini_handler.py       # Handles Gemini API interaction (incl. file upload)
├── serial_handler.py       # Manages REAL serial port communication
├── mock_serial_handler.py  # Manages SIMULATED serial communication
├── camera_handler.py       # Handles webcam capture, selection, confirmation
├── initial_prompt.txt      # The starting system prompt for Gemini
├── requirements.txt        # Lists Python dependencies
├── README.md               # This file
│
├── scorbot_acl_manual.pdf  # <-- PLACE YOUR SCORBOT MANUAL PDF/TXT HERE
│                           # (Crucial for Gemini's command generation!)
│
└── captures/               # Directory for captured images (created automatically)
```

## Prerequisites

*   **Hardware:**
    *   Scorbot ER VII Robot Arm with Controller-A
    *   USB-to-Serial Adapter compatible with your Scorbot controller and OS
    *   Webcam (built-in or external) OR iPhone with Continuity Camera enabled (macOS)
    *   Computer running Python
*   **Software:**
    *   Python 3.7 or newer
    *   `pip` (Python package installer)
    *   Git (optional, for cloning)
    *   Serial port drivers for your USB adapter
*   **API Key:**
    *   A Google AI API Key (obtainable from [Google AI Studio](https://aistudio.google.com/))

## Setup Instructions

1.  **Clone or Download:**
    ```bash
    git clone git@github.com:sciencesam/gemini_scorbot_controller.git
    cd gemini_scorbot_controller
    ```
    Or download the files into a `gemini_scorbot_controller` directory.

2.  **Create Virtual Environment (Recommended):**
    ```bash
    python3 -m venv venv
    # Activate it:
    # macOS/Linux:
    source venv/bin/activate
    # Windows (cmd):
    # venv\Scripts\activate.bat
    # Windows (PowerShell):
    # venv\Scripts\Activate.ps1
    # (You might need: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser)
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Place Scorbot Manual:**
    *   Obtain your Scorbot ER VII ACL reference manual (PDF or TXT format).
    *   Place it inside the `gemini_scorbot_controller` directory.
    *   **Rename it to `scorbot_acl_manual.pdf` (or `.txt`)** OR be prepared to use the `--manual` flag when running the script (e.g., `--manual /path/to/your_manual.pdf`). This file is critical for Gemini.

5.  **Set Google AI API Key:**
    *   You **MUST** set the `GOOGLE_API_KEY` environment variable. **Do NOT hardcode it in the script.**
    *   **macOS/Linux (Temporary):**
        ```bash
        export GOOGLE_API_KEY='YOUR_API_KEY_HERE'
        ```
    *   **Windows CMD (Temporary):**
        ```cmd
        set GOOGLE_API_KEY=YOUR_API_KEY_HERE
        ```
    *   **Windows PowerShell (Temporary):**
        ```powershell
        $env:GOOGLE_API_KEY='YOUR_API_KEY_HERE'
        ```
    *   For permanent setting, add it to your shell profile (`.bashrc`, `.zshrc`, etc.) or System Environment Variables.

6.  **Connect Hardware (for Real Mode):**
    *   Connect the Scorbot controller to the PC via the USB-to-Serial adapter.
    *   Connect your webcam or prepare your iPhone for Continuity Camera.
    *   Power on the Scorbot controller and robot arm.

## Running the Application

*   **Simulation Mode:** (No hardware needed, uses mock responses)
    ```bash
    python main.py --simulate
    ```

*   **Real Mode (Interactive Setup):** (Connect hardware first)
    *   The script will list detected serial ports and cameras (if multiple).
    *   Follow the prompts to select the correct ones.
    ```bash
    # Use the correct baud rate for your Scorbot (e.g., 9600)
    python main.py --baud 9600
    ```

*   **Real Mode (Specify Port/Camera):**
    *   Find your serial port name (e.g., `ls /dev/tty.*` on macOS/Linux, Device Manager on Windows).
    *   Find your camera index (often 0 for built-in, 1+ for external; the script lists them if run interactively).
    ```bash
    # Example macOS:
    python main.py --port /dev/tty.usbserial-A1B2C3D4 --camera 1 --baud 9600

    # Example Linux:
    # python main.py --port /dev/ttyUSB0 --camera 0 --baud 9600

    # Example Windows:
    # python main.py --port COM3 --camera 0 --baud 9600
    ```

*   **Optional Flags:**
    *   `--manual /path/to/other_manual.pdf`: Specify a different path/name for the manual file.
    *   `--prompt /path/to/other_prompt.txt`: Specify a different initial prompt file.

## Usage

1.  **Launch** the script using one of the methods above.
2.  **Select** port/camera if prompted.
3.  Wait for the **"--- System Ready ---"** message.
4.  **Interact with Gemini:** Type natural language commands for the robot (e.g., "Home the robot", "List the current position", "Move axis 1 by 1000 counts"). Press Enter.
5.  **Observe Output:**
    *   `> You:` Your input.
    *   `... Asking Gemini ...` Processing request.
    *   `< Gemini:` Gemini's textual response (may include placeholder like `[Sending Command: CMD]`).
    *   `--> [SERIAL_TX]: CMD` Command being sent to the robot.
    *   `(Waiting for response...)` Script waiting for robot reply.
    *   `<-- [SERIAL_RX]: ...` Lines received from the robot.
    *   `[System Note:]` Information from the script about actions or errors.
    *   `--- Handling Interactive SETPV... ---` Indicates automated sequence.
6.  **Image Capture Confirmation:** If Gemini requests an image or you use `/capture`, you will be prompted: `Position the camera and press Enter to capture...`. Position your camera and press Enter, or type `skip` to cancel.
7.  **Local Commands:**
    *   `/quit`: Exit the application cleanly.
    *   `/serial <raw_command>`: (Real Mode Only) Send `<raw_command>` directly over serial, bypassing Gemini (e.g., `/serial STATUS`).
    *   `/view`: Display the last few raw lines received from the serial port buffer (for debugging).
    *   `/capture`: Manually initiate an image capture (will ask for confirmation). You'll be asked if you want to send the captured image to Gemini.

## Configuration

*   **API Key:** Set via the `GOOGLE_API_KEY` environment variable (see Setup).
*   **Timeouts:** Serial communication timeouts (`SERIAL_RESPONSE_TIMEOUT`, `SERIAL_INTER_MESSAGE_TIMEOUT`, `SERIAL_PROMPT_TIMEOUT`) can be adjusted near the top of `main.py`.
*   **Initial Prompt:** Modify `initial_prompt.txt` to change Gemini's core instructions and constraints.

## How it Works

1.  **User Input:** `main.py` takes user input or prepares input based on previous actions.
2.  **Gemini Interaction:** `main.py` sends the input (text, optional image, optional serial response context) to `gemini_handler.py`.
3.  **API Call:** `gemini_handler.py` interacts with the Google Gemini API, including the uploaded manual context.
4.  **Response Parsing:** `main.py` receives Gemini's response via `gemini_handler.py` and parses it for text, `<SERIAL_CMD>` tags, or `<REQUEST_IMAGE/>` tags.
5.  **Action Execution:**
    *   **Serial Command:** If a command is found:
        *   For `SETPV <name>`, `main.py` calls `handle_setpv_interactive` which uses stored state and manages the prompt/response sequence with `serial_handler.py`.
        *   For other commands, `main.py` calls `serial_handler.py` (or `mock_serial_handler.py`) to send the command. It then calls `wait_for_serial_response` to collect the robot's reply. `LISTPV POSITION` results are parsed and stored.
    *   **Image Request:** If an image is needed, `main.py` prompts the user for confirmation, then calls `camera_handler.py` to capture the image.
6.  **Feedback Loop:** The result of the action (serial response summary, captured image path, or system error/note) is prepared and sent back to Gemini in the next interaction cycle via `main.py` and `gemini_handler.py`.

## Troubleshooting & Notes

*   **Serial Permissions (Linux):** Your user may need to be part of the `dialout` or `serial` group. Use `sudo usermod -a -G dialout $USER` (log out/in after).
*   **No Serial Ports Found:** Ensure the USB-to-Serial adapter is plugged in securely and drivers are installed correctly.
*   **Cannot Connect/Send:** Verify the correct serial port, baud rate, and that no other application is using the port. Check physical connections.
*   **Camera Not Opening:** Ensure the camera is connected, not used by another app, and the script has permission (especially on macOS). Try different camera indices.
*   **Incorrect Robot Behavior:** Double-check that the provided `scorbot_acl_manual.pdf/txt` *exactly* matches your robot controller's expected commands and syntax. The quality of Gemini's output depends heavily on this manual. Ensure the `initial_prompt.txt` accurately reflects the desired workflow.
*   **Homing Issues:** If `HOME` doesn't work, try sending it manually via `/serial HOME`. Check robot power and status lights. Ensure the `SERIAL_RESPONSE_TIMEOUT` in `main.py` is long enough.

## License

This project is licensed under the MIT License - see the LICENSE file (if created) or the header in the source files for details.