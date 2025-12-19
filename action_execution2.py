import pyautogui


class ActionExecuter:
    def __init__(self):
        pass 

    def action_execution(self, element):
        x = element.get("x", "")
        y = element.get("y", "")

        pyautogui.moveTo(x, y, duration=3)
        pyautogui.click()
