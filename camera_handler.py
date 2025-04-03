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