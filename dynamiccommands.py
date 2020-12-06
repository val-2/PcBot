import PcBotCore as Core


class Destiny(Core.DynamicCommand):
    def name(self):
        return 'destiny'

    def description(self):
        return 'Open Destiny 2'

    def can_showup(self):
        import sys
        return sys.platform == 'win32'

    def execute(self, update, context):
        import pywinauto
        import time
        import pyautogui
        import subprocess

        pyautogui.FAILSAFE = False

        subprocess.Popen("start steam://rungameid/1085660", shell=True)
        Core.send_message(update, "Starting Destiny 2")
        for _ in range(100):
            if not (wind := pywinauto.Desktop(backend="win32").windows(title_re="Destiny 2", visible_only=True)):
                time.sleep(1)
            else:
                break
        time.sleep(10)
        wind[0].set_focus()
        time.sleep(0.5)
        pyautogui.click()
        Core.send_message(update, "Destiny 2 started")


dynamiccmds = [Destiny()]
