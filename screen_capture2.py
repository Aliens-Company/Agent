import mss 
import io
from PIL import Image
import base64
import time

class ScreenCapture:
    def __init__(self):
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]

    def screen_capture(self):
        try:
            screenshot = self.sct.grab(self.monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            filename = f"screenshots/screenshot_{time.time()}.png"
            img.save(filename)
            return img
        except Exception as e:
            print(f"An error when screen capture {e}")    
            return None

    def capture_and_encode(self):
        img = self.screen_capture()

        if img is None:
            return None

        bufferd = io.BytesIO()
        img.save(bufferd, format="PNG")

        img_str = base64.b64encode(bufferd.getvalue()).decode()

        return img_str

