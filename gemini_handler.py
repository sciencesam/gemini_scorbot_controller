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