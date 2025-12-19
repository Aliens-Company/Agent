from text_input import UserTextInput
from screen_capture2 import ScreenCapture
from vision_analyzer2 import VisionAnalzer
from action_execution2 import ActionExecuter

class AutonomousLoop:
    def __init__(self):
        self.user_text = UserTextInput()
        self.screen_capture = ScreenCapture()
        self.vision_analizer = VisionAnalzer()
        self.action_execution = ActionExecuter()

    def run_autonomous_agent(self):
        command = self.user_text.get_user_command()
        if command is None:
            return

        img = self.screen_capture.capture_and_encode()
        if img is None:
            return 

        element_data = self.vision_analizer.analyze_screen(img, command)
        # if element_data is None:
        #     return
        
        self.action_execution.action_execution(element_data)
        