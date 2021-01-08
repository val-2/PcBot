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


class RefindLinux(Core.DynamicCommand):  # TODO unified refind command
    def name(self):
        return 'refindlinux'

    def description(self):
        return 'Make refind boot Linux on next reboot'

    def can_be_executed(self):
        return True

    def execute(self, update, context):
        import subprocess
        import sys

        refindscript = {'linux': ['refind-next-reboot'], 'win32': ['powershell', 'refind-next-reboot.ps1']}

        # import os
        # paths = {'linux': '/boot/', 'win32': 'M:/boot/'}
        # value = [i for i in sorted(os.listdir(paths[sys.platform]), key=lambda x: os.path.getmtime(f'{paths[sys.platform]}{x}')) if i[:7] == 'vmlinuz'][-1]
        # value = f'"Boot boot\\{value} from Manjaro"'

        if subprocess.check_output([*refindscript[sys.platform], 'set', f'"Boot @\\boot\\vmlinuz-linux-zen from Arch"'], text=True) == 'ok\n':
            Core.send_message(update, f'Linux set for next reboot. Use /reboot to use it immediately')
        else:
            Core.send_message(update, 'Failed to change OS for next reboot')
            Core.logging.error('Failed to change OS for next reboot')


class RefindWindows(Core.DynamicCommand):
    def name(self):
        return 'refindwindows'

    def description(self):
        return 'Make refind boot Windows on next reboot'

    def can_be_executed(self):
        return True

    def execute(self, update, context):
        import subprocess
        import sys

        refindscript = {'linux': ['refind-next-reboot'], 'win32': ['powershell', 'refind-next-reboot.ps1']}

        subprocess.check_output([*refindscript[sys.platform], 'set', 'Boot Microsoft EFI boot from EFI system partition'])
        if subprocess.check_output([*refindscript[sys.platform], 'set', 'Boot Microsoft EFI boot from EFI system partition'], text=True) == 'ok\n':
            Core.send_message(update, f'Windows set for next reboot. Use /reboot to use it immediately')
        else:
            Core.send_message(update, 'Failed to change OS for next reboot')
            Core.logging.error('Failed to change OS for next reboot')


class Test(Core.DynamicCommand):
    def name(self):
        return 'test'

    def description(self):
        return 'Just a test'

    def can_be_executed(self):
        return True

    def execute(self, update, context):
        import sys
        sys.exit(1)


dynamiccmds = [Destiny(), RefindLinux(), RefindWindows(), Test()]
