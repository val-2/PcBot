import PcBotCore as Core


class Destiny(Core.DynamicCommand):
    def name(self):
        return 'destiny'

    def description(self):
        return 'Open Destiny 2'

    def requirements(self):
        import sys
        return ['pywinauto', 'pyautogui'] if sys.platform == 'win32' else []

    def can_be_executed(self):
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


class Refind(Core.DynamicCommand):
    def name(self):
        return 'refind'

    def description(self):
        return 'Change OS '

    def can_be_executed(self):
        return True

    def execute(self, update, context):
        import subprocess
        import sys

        oses = {'Linux': '"Boot @\\boot\\vmlinuz-linux-zen from Arch"', 'Windows': '"Boot Microsoft EFI boot from EFI system partition"'}
        reply_markup = Core.telegram.ReplyKeyboardMarkup([list(oses.keys())])

        Core.send_message(update, 'Choose or write the wanted OS', reply_markup=reply_markup)
        message = Core.msg_queue.get(timeout=None, reset_before_start=False, reset_after_return=True)[0]
        os_str = oses.get(message, message)
        refindscript = {'linux': ['refind-next-reboot'], 'win32': ['powershell', 'refind-next-reboot.ps1']}

        # import os
        # paths = {'linux': '/boot/', 'win32': 'M:/boot/'}
        # value = [i for i in sorted(os.listdir(paths[sys.platform]), key=lambda x: os.path.getmtime(f'{paths[sys.platform]}{x}')) if i[:7] == 'vmlinuz'][-1]
        # value = f'"Boot boot\\{value} from Manjaro"'

        try:
            subprocess.check_output([*refindscript[sys.platform], 'set', os_str], text=True)
        except subprocess.CalledProcessError:
            Core.send_message(update, 'Error while executing script', log_level=40, reply_markup=Core.telegram.ReplyKeyboardRemove())
        except FileNotFoundError:
            Core.send_message(update, 'Script not found', log_level=40, reply_markup=Core.telegram.ReplyKeyboardRemove())
        except Exception as e:
            Core.send_message(update, f'Generic error: {repr(e)}', log_level=40, reply_markup=Core.telegram.ReplyKeyboardRemove())
        else:
            Core.send_message(update, f'OS set for next reboot. Use /reboot to use it immediately', reply_markup=Core.telegram.ReplyKeyboardRemove())


dynamiccmds = [Destiny(), Refind()]
