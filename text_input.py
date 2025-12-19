import pyautogui

class UserTextInput:
    def get_user_command(self):
        print("\n", "="*50)
        print("AI Autonomouse Agent - Command Input")
        print( "="*50)
        print("Exemple:")
        print("- Chrome open karo")
        print("- To Do open karo")

        command = input("Enter your command:")

        pyautogui.hotkey("win", "d")
        if not command:
            return None

        return command 


# obj = UserTextInput()
# obj.get_user_command()