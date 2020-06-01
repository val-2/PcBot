import PcBotCore as Core


class Screen(Core.Command):
    def name(self):
        return 'screen'

    def description(self):
        return 'Get a screenshot'

    @Core.run_async
    def execute(self, update, context, ignore_args=False, cursor=True, lossless=None):
        import pyautogui
        import screen
        from PIL import Image, ImageDraw
        import io

        pyautogui.FAILSAFE = False

        args = Core.join_args(update)
        s = screen.screenshot(nparray=False)
        Core.t_bot.send_chat_action(chat_id=update.message.chat_id, action=Core.telegram.ChatAction.UPLOAD_PHOTO)
        if args and not ignore_args:
            lossless = True
        Core.logging.debug("Screenshot taken")
        im = Image.frombytes("RGB", s.size, s.bgra, "raw", "BGRX")
        if cursor:
            pos = pyautogui.position()
            radius = 7
            ImageDraw.ImageDraw(im).ellipse((pos.x - radius, pos.y - radius, pos.x + radius, pos.y + radius), fill="white", outline="black")

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
        Core.logging.debug("Screenshot sent")


class Keyboard(Core.Command):
    def name(self):
        return 'keyboard'

    def description(self):
        return 'Send keystrokes'

    @Core.run_async
    def execute(self, update, context):
        import pyautogui

        pyautogui.FAILSAFE = False

        args = Core.join_args(update)
        pyautogui.write(args)
        Core.logging.debug(f'Keys written: {args}')
        Core.send_message(update, f'"{args}" written')


class Mouse(Core.Command):
    def name(self):
        return 'mouse'

    def description(self):
        return 'Emulate mouse'

    @Core.run_async
    def execute(self, update, context):
        import pyautogui
        import time

        pyautogui.FAILSAFE = False

        custom_keyboard = [['double click', '⬆', 'right click'],
                           ['⬅', 'left click', '➡'],
                           ['reduce', '⬇', 'increase']]
        reply_markup = Core.telegram.ReplyKeyboardMarkup(custom_keyboard)

        ratio = 4
        self.x_move = pyautogui.size()[0] // ratio
        self.y_move = pyautogui.size()[1] // ratio

        def reduce():
            self.x_move //= ratio
            self.y_move //= ratio

        def increase():
            self.x_move *= ratio
            self.y_move *= ratio

        actions = {
            custom_keyboard[0][0]: pyautogui.doubleClick,
            custom_keyboard[0][1]: lambda: pyautogui.move(yOffset=-self.y_move),
            custom_keyboard[0][2]: pyautogui.rightClick,
            custom_keyboard[1][0]: lambda: pyautogui.move(xOffset=-self.x_move),
            custom_keyboard[1][1]: pyautogui.click,
            custom_keyboard[1][2]: lambda: pyautogui.move(xOffset=self.x_move),
            custom_keyboard[2][0]: reduce,
            custom_keyboard[2][1]: lambda: pyautogui.move(yOffset=self.y_move),
            custom_keyboard[2][2]: increase,
        }
        Core.logging.info("Mouse control started")
        Core.send_message(update, "Enter", reply_markup=reply_markup)

        Screen().execute(update, context, ignore_args=True)
        last = time.time()

        while True:
            message = Core.queue.get()[0]
            if message in actions:
                actions[message]()
                Core.logging.debug("Mouse action executed")
            elif message.lower() == "🆗":
                Core.send_message(update, "Exited", reply_markup=Core.telegram.ReplyKeyboardRemove())
                Core.logging.info("Mouse control terminated")
                break
            else:
                pyautogui.write(message)
            if time.time() - last > 6:
                Screen().execute(update, context, ignore_args=True)
                last = time.time()


class Cmd(Core.Command):
    def name(self):
        return 'cmd'

    def description(self):
        return 'Execute command'

    @Core.run_async
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
                    if str(e) != "urllib3 HTTPError [SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC] decryption failed or bad record mac (_ssl.c:2508)":
                        raise
                    else:
                        Core.logging.warning("Network error")

            inputs = Core.queue.get(0)
            for i in inputs:
                p.stdin.write(i + "\n")
                p.stdin.flush()
            # sleep(1)
            if p.poll() is not None:
                message += confirmation
                sent.edit_text(message)
                break
        Core.logging.info("core.Command executed")
        return output


class Ip(Core.Command):
    def name(self):
        return 'ip'

    def description(self):
        return 'Get locan and external IP'

    @Core.run_async
    def execute(self, update, context):
        import requests

        local_ip = self.get_local_ip()
        external_ip = requests.get('https://ident.me').text
        Core.logging.info(f"IPs: {local_ip} {external_ip}")
        Core.send_message(update, f"Local IP: {local_ip}\nExternal IP: {external_ip}")

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

    @Core.run_async
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
        sent = Core.send_message(update, message)

        times = 0
        while True:
            if times < 5:
                for link in args:
                    times = 0

                    try:
                        subprocess.check_output(["transmission-remote", "-a", link], shell=False, stderr=subprocess.STDOUT, text=True)
                    except subprocess.CalledProcessError as e:
                        Core.send_message(update, "Invalid link")
                        Core.logging.error(f"Invalid link: {link}  -  Error: {e}")
                        sys.exit(1)
                    Core.logging.info(f"Torrent added: {link}")

            message = transmission_url
            output = subprocess.check_output(["transmission-remote", "-l"], text=True).split("\n")
            if len(output) == 3 and times >= 5:
                break
            for i in range(1, len(output) - 2):
                if output[i].split()[1] == "100%":
                    subprocess.check_output(["transmission-remote", "-t", output[i].split()[0].split("*")[0], "-r"])
                    Core.logging.info(f"Torrent completed: {output[i][70:]}")
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
                args = Core.queue.get(3)
                times += 1
            else:
                time.sleep(3)
        sent.edit_text("All torrents downloaded")
        Core.logging.info("All torrents downloaded")


class Download(Core.Command):
    def name(self):
        return 'download'

    def description(self):
        return 'Download a file'

    @Core.run_async
    def execute(self, update, context):
        args = Core.join_args(update).split()
        times = 0
        if not args:
            Core.send_message(update, "Enter link:")

        while times < 5:
            for a in args:
                self._download(update, link=a)
                times = 0

            args = Core.queue.get(3)
            times += 1

    @staticmethod
    def _download(update, link):
        import requests
        import datetime
        import re
        import os
        import sys

        Core.logging.info(f"Download requested: {link}")
        try:
            r = requests.get(link, stream=True)
        except requests.exceptions.RequestException as e:
            Core.send_message(update, "Invalid link")
            Core.logging.error(f"Invalid link: {link}  -  Error: {e}")
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

        Core.logging.info(f"Starting download: {name}")
        sent = Core.send_message(update, f"Starting download: {name}")
        last_message = ""

        filename = name
        i = 0
        while os.path.exists(os.path.join(Core.downloads_directory, filename)):
            i += 1
            filename = f"{os.path.splitext(name)[0]} ({i}){os.path.splitext(name)[1]}"

        with open(os.path.join(Core.downloads_directory, filename), "wb") as f:
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
        Core.logging.info(f"Finished download: {name}")
        Core.send_message(update, f"Finished download: {name}")


class Lock(Core.Command):
    def name(self):
        return 'lock'

    def description(self):
        return 'Lock session'

    @Core.run_async
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
            if subprocess.run(["xdg-screensaver", "lock"]).returncode == 4:
                pass
        elif sys.platform == "win32":
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
        Core.send_message(update, f"{getpass.getuser()} screen locked")
        Core.logging.info("Screen locked")


class Logout(Core.Command):
    def name(self):
        return 'logout'

    def description(self):
        return 'Log out current user'

    @Core.run_async
    def execute(self, update, context):
        import time
        import subprocess
        import sys
        import getpass

        args = Core.join_args(update)
        if not args:
            args = "0"
        time.sleep(int(args))
        Core.logging.info("Current user core.logging output")
        Core.send_message(update, f"{getpass.getuser()} core.logging output")
        if sys.platform == "linux":
            subprocess.Popen(["logout"])
        elif sys.platform == "win32":
            subprocess.Popen(f"shutdown -l -f", shell=True)


class Suspend(Core.Command):
    def name(self):
        return 'suspend'

    def description(self):
        return 'Suspend session'

    @Core.run_async
    def execute(self, update, context):
        import time
        import subprocess
        import sys

        args = Core.join_args(update)
        if not args:
            args = "0"
        time.sleep(int(args))
        Core.logging.info("Suspending system")
        Core.send_message(update, "Suspending system")
        if sys.platform == "linux":
            subprocess.Popen(["systemctl", "suspend"])
        elif sys.platform == "win32":
            subprocess.Popen(f".\\nircmdc.exe standby", shell=True)


class Hibernate(Core.Command):
    def name(self):
        return 'hibernate'

    def description(self):
        return 'Hibernate computer'

    @Core.run_async
    def execute(self, update, context):
        import time
        import subprocess
        import sys

        args = Core.join_args(update)
        if not args:
            args = "0"
        time.sleep(int(args))
        Core.logging.info("Hibernating system")
        Core.send_message(update, "Hibernating system")
        if sys.platform == "linux":
            subprocess.Popen(["systemctl", "hibernate"])
        elif sys.platform == "win32":
            subprocess.Popen(f"shutdown -h", shell=True)


class Reboot(Core.Command):
    def name(self):
        return 'reboot'

    def description(self):
        return 'Reboot computer'

    @Core.run_async
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
            subprocess.Popen(["reboot"])
        elif sys.platform == "win32":
            subprocess.Popen(f"shutdown -r -f -t {args}", shell=True)


class Shutdown(Core.Command):
    def name(self):
        return 'shutdown'

    def description(self):
        return 'Shut down computer'

    @Core.run_async
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
            subprocess.Popen(f"shutdown -s -f -t {args}", shell=True)


class Volume(Core.Command):
    def name(self):
        return 'volume'

    def description(self):
        return 'Change volume'

    @Core.run_async
    def execute(self, update, context):
        import subprocess
        import sys

        args = Core.join_args(update)
        if args == "mute":
            if sys.platform == "linux":
                subprocess.check_output(["pulseaudio-ctl", "mute"])
            elif sys.platform == "win32":
                subprocess.check_output("./nircmdc.exe mutesysvolume 2", shell=True)
            Core.logging.info("Volume mute toggled")
            Core.send_message(update, "Volume mute toggled")
        elif args.isdigit():
            if sys.platform == "linux":
                subprocess.check_output(["pulseaudio-ctl", "set", args])
            elif sys.platform == "win32":
                subprocess.check_output("./nircmdc.exe changesysvolume " + str(int(int(args) / 100 * 65535)), shell=True)
            Core.logging.info(f"Volume set to {args}")
            Core.send_message(update, f"Volume set to {args}")


class MsgBox(Core.Command):
    def name(self):
        return 'msgbox'

    def description(self):
        return 'Display a messagebox'  # TODO

    @Core.run_async
    def execute(self, update, context):
        import wx
        import Xlib

        args = Core.join_args(update)
        Core.logging.info("MessageBox showed")
        Core.send_message(update, "MessageBox showed")
        try:
            import pyautogui
            wx.MessageBox(args, "Alert")
        except (KeyError, Xlib.error.DisplayConnectionError):
            print(args)
        Core.logging.info("MessageBox accepted")
        Core.send_message(update, "MessageBox accepted")


commands = [Screen(), Torrent(), Keyboard(), Mouse(), Cmd(), Ip(), Download(), Lock(), Logout(), Suspend(), Hibernate(), Reboot(), Shutdown(), Volume(), MsgBox()]
