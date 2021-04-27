import PcBotCore as Core


class Screen(Core.Command):
    def name(self):
        return 'screen'

    def description(self):
        return 'Get a screenshot'

    def requirements(self):
        return ['pyautogui', 'pillow']  # 'screenmss'

    def execute(self, update, context, ignore_args=False, cursor=True, lossless=None):
        import pyautogui
        import screenmss
        from PIL import Image, ImageDraw
        import io
        import sys

        pyautogui.FAILSAFE = False

        args = Core.join_args(update)
        s = screenmss.screenshot()
        Core.t_bot.send_chat_action(chat_id=update.message.chat_id, action=Core.telegram.ChatAction.UPLOAD_PHOTO)
        if args and not ignore_args:
            lossless = True
        Core.logger.debug("Screenshot taken")
        im = Image.frombytes("RGB", s.size, s.bgra, "raw", "BGRX")
        ImageDraw.ImageDraw(im).polygon(self.pointer_coords(pyautogui.position().x, pyautogui.position().y), fill="white", outline="black")

        f = io.BytesIO()
        im.save(f, format="png", optimize=True)
        f2 = io.BytesIO(f.getvalue())

        if lossless is None:
            if len(f2.getvalue()) < 200000:
                lossless = True
            else:
                lossless = False
        if lossless:
            context.bot.send_document(update.message.chat_id, f2, filename="screen.png")
        else:
            f = io.BytesIO()
            im.save(f, format="jpeg", optimize=True)
            f2 = io.BytesIO(f.getvalue())
            context.bot.send_document(update.message.chat_id, f2, filename="screen.jpg")
        Core.logger.debug("Screenshot sent")

    @staticmethod
    def pointer_coords(x, y):
        return x, y, x, y + 17, x + 5, y + 12, x + 12, y + 12


class Keyboard(Core.Command):
    def name(self):
        return 'keyboard'

    def description(self):
        return 'Send keystrokes'

    def requirements(self):
        return ['pyautogui']

    def execute(self, update, context):
        import pyautogui

        pyautogui.FAILSAFE = False

        args = Core.join_args(update)
        pyautogui.write(args)
        Core.send_message(update, f'Keys "{args}" written')


class Mouse(Core.Command):
    def name(self):
        return 'mouse'

    def description(self):
        return 'Emulate mouse'

    def requirements(self):
        return ['pyautogui', 'pillow']  # 'screenmss'

    def execute(self, update, context):
        import pyautogui

        pyautogui.FAILSAFE = False

        custom_keyboard = [['double click', '⬆', 'right click'],
                           ['⬅',       'left click',       '➡'],
                           ['reduce',       '⬇',   'increase']]
        reply_markup = Core.telegram.ReplyKeyboardMarkup(custom_keyboard)

        self.multiplier = 0.25

        def increase():
            self.multiplier *= 4 if min(pyautogui.size()) * self.multiplier >= 1 else self.multiplier

        def reduce():
            self.multiplier /= 4 if min(pyautogui.size()) * self.multiplier >= 1 else self.multiplier

        actions = {
            'double click': pyautogui.doubleClick,
            '⬆': lambda: pyautogui.move(yOffset=-pyautogui.size()[1] * self.multiplier, xOffset=0),
            'right click': pyautogui.rightClick,
            '⬅': lambda: pyautogui.move(xOffset=-pyautogui.size()[0] * self.multiplier, yOffset=0),
            'left click': pyautogui.click,
            '➡': lambda: pyautogui.move(xOffset=pyautogui.size()[0] * self.multiplier, yOffset=0),
            'reduce': reduce,
            '⬇': lambda: pyautogui.move(yOffset=pyautogui.size()[1] * self.multiplier, xOffset=0),
            'increase': increase,
        }
        Core.send_message(update, "Mouse control started", reply_markup=reply_markup)

        while True:
            if not (message := Core.msg_queue.get(timeout=3)):
                self.send_grid(update, context)
                Core.send_message(update, str(self.multiplier))
                Core.msg_queue.get(reset_before_start=False, reset_after_return=False)
                continue
            if message[0] in actions:
                actions[message[0]]()
                Core.logger.info("Mouse action executed")
            elif message[0].lower() == "🆗":
                Core.send_message(update, "Mouse control exited", reply_markup=Core.telegram.ReplyKeyboardRemove())
                break
            else:
                pyautogui.write(message)
                Core.send_message(update, f'Keys "{message}" pressed')

    def send_grid(self, update, context):
        import pyautogui
        import screenmss
        from PIL import Image, ImageDraw
        import io
        import math

        pyautogui.FAILSAFE = False

        s = screenmss.screenshot()
        Core.logger.debug("Screenshot taken")
        Core.t_bot.send_chat_action(chat_id=update.message.chat_id, action=Core.telegram.ChatAction.UPLOAD_PHOTO)
        im = Image.frombytes("RGB", s.size, s.bgra, "raw", "BGRX")

        if min(pyautogui.size()) * self.multiplier > 17:
            offset_x = pyautogui.position().x % (pyautogui.size()[0] * self.multiplier)
            offset_y = pyautogui.position().y % (pyautogui.size()[1] * self.multiplier)
            horizontal_pos = [offset_x + i * (pyautogui.size()[0] * self.multiplier) for i in range(0, math.ceil((pyautogui.size()[0]-offset_x) / (pyautogui.size()[0] * self.multiplier)))]
            vertical_pos = [offset_y + i * (pyautogui.size()[1] * self.multiplier) for i in range(0, math.ceil((pyautogui.size()[1]-offset_y) / (pyautogui.size()[1] * self.multiplier)))]
            for x in horizontal_pos:
                for y in vertical_pos:
                    ImageDraw.ImageDraw(im, "RGBA").polygon(self.pointer_coords(x, y), fill=(0, 0, 0, 100), outline=(255, 255, 255, 100))

        ImageDraw.ImageDraw(im).polygon(self.pointer_coords(pyautogui.position().x, pyautogui.position().y), fill="white", outline="black")

        f = io.BytesIO()
        im.save(f, format="png", optimize=True)
        f2 = io.BytesIO(f.getvalue())

        if len(f2.getvalue()) < 200000:
            context.bot.send_document(update.message.chat_id, f2, filename="screen.png")
        else:
            f = io.BytesIO()
            im.save(f, format="jpeg", optimize=True)
            f2 = io.BytesIO(f.getvalue())
            context.bot.send_document(update.message.chat_id, f2, filename="screen.jpg")
        Core.logger.debug("Screenshot sent")

    @staticmethod
    def pointer_coords(x, y):
        return x, y, x, y+17, x+5, y+12, x+12, y+12


class Cmd(Core.Command):
    def name(self):
        return 'cmd'

    def description(self):
        return 'Execute command'

    def execute(self, update, context, args=None, confirmation='🆗\n', shell=True):
        import subprocess
        import async_streamer

        if not args:
            args = Core.join_args(update)
            message = args + "\n"
        else:
            if isinstance(args, list):
                message = " ".join(args) + "\n"
            else:
                message = args + "\n"
        p = subprocess.Popen(args, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True)
        sent = Core.send_message(update, message)
        stdout = async_streamer.AsyncReader(p.stdout.readline)
        while True:
            output = "".join(stdout.get(0.1))
            if output:
                message += output
                try:
                    sent.edit_text(message)
                except Core.telegram.error.TimedOut as e:
                    if str(e) == "urllib3 HTTPError [SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC] decryption failed or bad record mac (_ssl.c:2508)":
                        Core.logger.warning("Network error while editing message for cmd")
                    else:
                        raise
            inputs = Core.msg_queue.get(0)
            for i in inputs:
                p.stdin.write(i + "\n")
                p.stdin.flush()
            # sleep(1)
            if p.poll() is not None:
                message += confirmation
                sent.edit_text(message)
                break
        Core.logger.info("Command executed")
        return output


class Ip(Core.Command):
    def name(self):
        return 'ip'

    def description(self):
        return 'Get locan and external IP'

    def requirements(self):
        return ['requests']

    def execute(self, update, context):
        import requests

        local_ip = self.get_local_ip()
        external_ip = requests.get('https://ident.me').text
        Core.send_message(update, f"Local IP: {local_ip}    External IP: {external_ip}")

    @staticmethod
    def get_local_ip():
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip


class Torrent(Core.Command):
    def name(self):
        return 'torrent'

    def description(self):
        return 'Download a torrent'

    def execute(self, update, context):
        import subprocess
        import sys
        import datetime
        import time
        args = Core.join_args(update).split()

        local_ip = Ip.get_local_ip()
        transmission_url = f"{local_ip}:9091/transmission/web/"
        message = transmission_url
        last_message = message
        sent = Core.send_message(update, message, log_level=10)

        times = 0
        while True:
            if times < 5:
                for link in args:
                    times = 0

                    try:
                        subprocess.check_output(["transmission-remote", "-a", link], stderr=subprocess.STDOUT, text=True)
                    except subprocess.CalledProcessError as e:
                        Core.send_message(update, f"Invalid link: {link}", log_level=40)
                        sys.exit(1)
                    Core.logger.info(f"Torrent added: {link}")

            message = transmission_url
            output = subprocess.check_output(["transmission-remote", "-l"], text=True).split("\n")
            if len(output) == 3 and times >= 5:
                break
            for i in range(1, len(output) - 2):
                if output[i].split()[1] == "100%":
                    subprocess.check_output(["transmission-remote", "-t", output[i].split()[0].split("*")[0], "-r"])
                    Core.send_message(update, f"Torrent completed: {output[i][70:]}")
                else:
                    message += "\n▶" + output[i][8:11] + output[i][13:32] + output[i][70:]
            message += f"\n{datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
            if last_message != message:
                try:
                    sent.edit_text(message)
                except Core.telegram.error.TimedOut:
                    pass
                last_message = message

            if times < 5:
                args = Core.msg_queue.get(3)
                times += 1
            else:
                time.sleep(3)
        sent.edit_text("All torrents downloaded")
        Core.logger.info("All torrents downloaded")


class Download(Core.Command):
    def name(self):
        return 'download'

    def description(self):
        return 'Download a file'

    def requirements(self):
        return ['requests']

    def execute(self, update, context):
        args = Core.join_args(update).split()
        times = 0
        if not args:
            Core.send_message(update, "Enter link:", log_level=10)

        while times < 5:
            for a in args:
                self._download(update, link=a)
                times = 0

            args = Core.msg_queue.get(3)
            times += 1

    @staticmethod
    def _download(update, link):
        import requests
        import datetime
        import re
        import os
        import sys

        Core.logger.info(f"Download requested: {link}")
        try:
            r = requests.get(link, stream=True)
        except requests.exceptions.RequestException as e:
            Core.send_message(update, "Invalid link", log_level=40)
            sys.exit(1)
        try:
            name = re.findall("filename=(.+)", r.headers["content-disposition"])[0]
        except KeyError:
            name = link.split("/")[-1]

        try:
            file_size = int(r.headers['Content-Length'])
        except KeyError:
            file_size = -1
        downloaded_bites = 0

        sent = Core.send_message(update, f"Starting download: {name}")
        last_message = ""

        filename = name
        i = 0
        while os.path.exists(os.path.join(Core.media, filename)):
            i += 1
            filename = f"{os.path.splitext(name)[0]} ({i}){os.path.splitext(name)[1]}"

        with open(os.path.join(Core.media, filename), "wb") as f:
            for chunk in r.iter_content(chunk_size=2 ** 22):
                f.write(chunk)
                downloaded_bites += len(chunk)
                if file_size != -1:
                    message = f"{name}\nDownloaded: {int(downloaded_bites / file_size * 100)}% - {downloaded_bites} / {file_size} bytes"
                else:
                    message = f"{name}\nDownloaded: {downloaded_bites} bytes"
                message += f"\n{datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
                if last_message != message:
                    try:
                        sent.edit_text(message)
                    except Core.telegram.error.TimedOut:
                        pass
                last_message = message
        Core.send_message(update, f"Finished download: {name}")


class Lock(Core.Command):
    def name(self):
        return 'lock'

    def description(self):
        return 'Lock session'

    def execute(self, update, context):
        import time
        import sys
        import subprocess
        import getpass

        args = Core.join_args(update)
        if not args:
            args = "0"
        time.sleep(int(args))
        if sys.platform == "linux":
            subprocess.check_output(["loginctl", "lock-session"])
        elif sys.platform == "win32":
            subprocess.check_output(['rundll32.exe' 'user32.dll,LockWorkStation'])
        Core.send_message(update, f"{getpass.getuser()}'s screen locked")


class Logout(Core.Command):
    def name(self):
        return 'logout'

    def description(self):
        return 'Log out current user'

    def execute(self, update, context):
        import time
        import subprocess
        import sys
        import getpass

        args = Core.join_args(update)
        if not args:
            args = "0"
        time.sleep(int(args))
        Core.send_message(update, f"{getpass.getuser()}: log out")
        if sys.platform == "linux":
            subprocess.check_output(["loginctl", "terminate-session"])
        elif sys.platform == "win32":
            subprocess.check_output(['shutdown', '-l', '-f'])


class Suspend(Core.Command):
    def name(self):
        return 'suspend'

    def description(self):
        return 'Suspend session'

    def execute(self, update, context):
        import time
        import subprocess
        import sys

        args = Core.join_args(update)
        if not args:
            args = "0"
        time.sleep(int(args))
        Core.send_message(update, "Suspending system")
        if sys.platform == "linux":
            subprocess.check_output(["systemctl", "suspend"])
        elif sys.platform == "win32":
            try:
                subprocess.check_output(['nircmdc.exe', 'standby'])
            except FileNotFoundError:
                Core.send_message(update, 'Warning: this command will hibernate if hibernation is active. Disable hibernation or add nircmdc.exe to path')
                subprocess.check_output(['rundll32.exe', 'powrprof.dll,SetSuspendState', '0,1,0'])


class Hibernate(Core.Command):
    def name(self):
        return 'hibernate'

    def description(self):
        return 'Hibernate computer'

    def execute(self, update, context):
        import time
        import subprocess
        import sys

        args = Core.join_args(update)
        if not args:
            args = "0"
        time.sleep(int(args))
        Core.send_message(update, "Hibernating system")
        if sys.platform == "linux":
            subprocess.check_output(["systemctl", "hibernate"])
        elif sys.platform == "win32":
            subprocess.check_output(['shutdown', '-h'])


class Reboot(Core.Command):
    def name(self):
        return 'reboot'

    def description(self):
        return 'Reboot computer'

    def execute(self, update, context):
        args = Core.join_args(update)
        if not args:
            args = "0"
        import time
        import subprocess
        import sys

        Core.send_message(update, "Rebooting system")
        if sys.platform == "linux":
            time.sleep(int(args))
            subprocess.check_output(["reboot"])
        elif sys.platform == "win32":
            subprocess.check_output(['shutdown', '-r', '-f', '-t', args])


class Shutdown(Core.Command):
    def name(self):
        return 'shutdown'

    def description(self):
        return 'Shut down computer'

    def execute(self, update, context):
        import time
        import subprocess
        import sys

        args = Core.join_args(update)
        if not args:
            args = "0"
        Core.send_message(update, "Shutting down system")
        if sys.platform == "linux":
            time.sleep(int(args))
            subprocess.Popen(["poweroff"])
        elif sys.platform == "win32":
            subprocess.Popen(['shutdown', '-s', '-f', '-t', args])


class Volume(Core.Command):
    def name(self):
        return 'volume'

    def description(self):
        return 'Change volume'

    def requirements(self):
        return ['pyautogui;platform_system=="Windows"']

    def execute(self, update, context):
        import subprocess
        import sys
        import pyautogui

        args = Core.join_args(update)
        if args == "mute":
            if sys.platform == "linux":
                subprocess.check_output(["pulseaudio-ctl", "mute"])
            elif sys.platform == "win32":
                pyautogui.press('volumemute')
            Core.send_message(update, "Volume mute toggled")
        elif args.isdigit():
            if sys.platform == "linux":
                subprocess.check_output(["pulseaudio-ctl", "set", args])
            elif sys.platform == "win32":
                subprocess.check_output("./nircmdc.exe changesysvolume " + str(int(int(args) / 100 * 65535)), shell=True)
            Core.send_message(update, f"Volume set to {args}")


class MsgBox(Core.Command):
    def name(self):
        return 'msgbox'

    def description(self):
        return 'Display a messagebox'

    def requirements(self):
        return ['PyMsgBox']

    def execute(self, update, context):
        import pymsgbox
        import _tkinter

        args = Core.join_args(update)
        try:
            Core.send_message(update, "Showing MessageBox...")
            pymsgbox.alert(text=args)
            Core.send_message(update, "MessageBox accepted")
        except _tkinter.TclError:
            Core.send_message(update, "Display not connected. Msgbox unavailable")


commands = [Screen(), Torrent(), Keyboard(), Mouse(), Cmd(), Ip(), Download(), Lock(), Logout(), Suspend(), Hibernate(), Reboot(), Shutdown(), Volume(), MsgBox()]
