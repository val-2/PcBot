import PcBotCore as Core


class Destiny(Core.DynamicCommand):
    def name(self):
        return 'destiny'

    def description(self):
        return 'Open Destiny 2'

    def can_showup(self):
        import sys
        return sys.platform == 'win32'

    @Core.run_async
    def execute(self, update, context):
        import pywinauto
        import time
        import pyautogui
        import subprocess

        subprocess.Popen("start steam://rungameid/1085660", shell=True)
        for _ in range(100):
            if not pywinauto.Desktop(backend="uia").windows(title_re="Destiny 2", visible_only=True):
                time.sleep(1)
            else:
                break
        time.sleep(10)
        pyautogui.moveTo(0, 0)
        time.sleep(1)
        pyautogui.click()


dynamiccmds = [Destiny()]