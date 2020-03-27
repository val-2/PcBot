#!/home/valerio/venv/bin/python

import datetime
import getpass
import logging
import os.path
import re
import socket
import sys
import urllib.request
from io import BytesIO, StringIO
from subprocess import check_output, Popen, run, PIPE, STDOUT, CalledProcessError
from time import sleep

import Xlib
import requests
import telegram
from PIL import Image, ImageDraw
from telegram.ext import Updater, Filters, CommandHandler, MessageHandler
from telegram.ext.dispatcher import run_async
import coloredlogs

from async_streamer import *
from interceptor import *
import config


while True:
    try:
        socket.setdefaulttimeout(10)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
        break
    except socket.error:
        logging.warning("Not connected to internet")
        sleep(3)


def send_message(update: telegram.Update, text, parse_mode=None, disable_web_page_preview=None, disable_notification=False, reply_to_message_id=None, reply_markup=None, timeout=None, **kwargs):
    while True:
        try:
            sent = update.message.bot.send_message(update.message.chat_id, text, parse_mode, disable_web_page_preview, disable_notification, reply_to_message_id, reply_markup, timeout, **kwargs)
            logging.debug(f'Message "{text}" sent to {update.message.chat.first_name}')
            break
        except telegram.error.NetworkError as e:
            if str(e) != "urllib3 HTTPError [SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC] decryption failed or bad record mac (_ssl.c:2508)":
                raise
            else:
                logging.warning("Network error")
    return sent


def join_args(update: telegram.Update):
    return " ".join(update.message["text"].split(" ")[1:])


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('10.255.255.255', 1))
    local_ip = s.getsockname()[0]
    s.close()
    return local_ip


def command_std(update, args, shell=False, confirmation='🆗\n'):
    output = check_output(args, shell, stderr=STDOUT, text=True)
    logging.debug(f"Bash command executed: {args if shell else ' '.join(args)}")
    logging.debug(f"Output: {output}")
    output += confirmation
    if output:
        send_message(update, output)
    return output


@run_async
def _restart():
    Popen([sys.executable] + sys.argv).wait()


@run_async
def start(update: telegram.Update = None, context: telegram.ext.CallbackContext = None, chat_id=None):
    oses = {'linux': 'Linux', 'win32': 'Windows', 'darwin': 'MacOS'}
    op_sys = oses.get(sys.platform, 'unknown OS')
    t_bot.send_message(update.message.chat_id if update else chat_id, f"{getpass.getuser()} started pc on {op_sys}", disable_notification=True)


@run_async
def screen(update: telegram.Update, context: telegram.ext.CallbackContext, ignore_args=False, cursor=True, lossless=None):
    args = join_args(update)
    s = screenshot(nparray=False)
    t_bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
    if args and not ignore_args:
        lossless = True
    logging.debug("Screenshot taken")
    im = Image.frombytes("RGB", s.size, s.bgra, "raw", "BGRX")
    if cursor:
        pos = pyautogui.position()
        radius = 7
        ImageDraw.ImageDraw(im).ellipse((pos.x - radius, pos.y - radius, pos.x + radius, pos.y + radius), fill="white", outline="black")

    f = BytesIO()
    im.save(f, format="png", optimize=True)
    f2 = BytesIO(f.getvalue())

    if lossless is None:
        if len(f2.getvalue()) < 200000:
            lossless = True
        else:
            lossless = False
    if lossless:
        context.bot.send_document(update.message.chat_id, f2, filename="screen.png")
    else:
        f = BytesIO()
        im.save(f, format="jpeg", optimize=True)
        f2 = BytesIO(f.getvalue())
        context.bot.send_document(update.message.chat_id, f2, filename="screen.jpg")
    logging.debug("Screenshot sent")


@run_async
def keyboard(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    pyautogui.write(args)
    logging.debug(f'Keys written: {args}')
    send_message(update, f'"{args}" written')


@run_async
def mouse(update: telegram.Update, context: telegram.ext.CallbackContext):
    custom_keyboard = [['double click', '⬆', 'right click'],
                       ['⬅', 'left click', '➡'],
                       ['reduce', '⬇', 'increase']]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)

    ratio = 4
    mouse.x_move = pyautogui.size()[0] // ratio
    mouse.y_move = pyautogui.size()[1] // ratio

    def reduce():
        mouse.x_move //= ratio
        mouse.y_move //= ratio

    def increase():
        mouse.x_move *= ratio
        mouse.y_move *= ratio

    actions = {
        custom_keyboard[0][0]: pyautogui.doubleClick,
        custom_keyboard[0][1]: lambda: pyautogui.move(yOffset=-mouse.y_move),
        custom_keyboard[0][2]: pyautogui.rightClick,
        custom_keyboard[1][0]: lambda: pyautogui.move(xOffset=-mouse.x_move),
        custom_keyboard[1][1]: pyautogui.click,
        custom_keyboard[1][2]: lambda: pyautogui.move(xOffset=mouse.x_move),
        custom_keyboard[2][0]: reduce,
        custom_keyboard[2][1]: lambda: pyautogui.move(yOffset=mouse.y_move),
        custom_keyboard[2][2]: increase,
    }
    logging.info("Mouse control started")
    send_message(update, "Enter", reply_markup=reply_markup)

    screen(update, context, ignore_args=True)
    last = time()

    while True:
        message = queue.get()[0]
        if message in actions:
            actions[message]()
            logging.debug("Mouse action executed")
        elif message.lower() == "🆗":
            send_message(update, "Exited", reply_markup=telegram.ReplyKeyboardRemove())
            logging.info("Mouse control terminated")
            break
        else:
            pyautogui.write(message)
        if time() - last > 6:
            screen(update, context, ignore_args=True)
            last = time()


def restart(update: telegram.Update, context: telegram.ext.CallbackContext):
    _restart()
    updater.stop()


@run_async
def cmd(update: telegram.Update, context: telegram.ext.CallbackContext, args=None, confirmation='🆗\n', shell=True):
    if not args:
        args = join_args(update)
        message = args + "\n"
    else:
        if isinstance(args, list):
            message = " ".join(args) + "\n"
        else:
            message = args + "\n"
    p = Popen(args, shell=shell, stdout=PIPE, stderr=STDOUT, stdin=PIPE, text=True)
    sent = send_message(update, message)
    stdout = AsyncReader(p.stdout.readline)
    while True:
        output = "".join(stdout.get(0.1))
        if output:
            message += output
            try:
                sent.edit_text(message)
            except telegram.error.TimedOut as e:
                pass
        inputs = queue.get(0)
        for i in inputs:
            p.stdin.write(i + "\n")
            p.stdin.flush()
        # sleep(1)
        if p.poll() is not None:
            message += confirmation
            sent.edit_text(message)
            break
    logging.info("Command executed")
    return output


@run_async
def ip(update: telegram.Update, context: telegram.ext.CallbackContext):
    local_ip = get_local_ip()
    external_ip = urllib.request.urlopen('https://ident.me').read().decode('utf8')
    logging.info(f"IPs: {local_ip} {external_ip}")
    send_message(update, f"Local IP: {local_ip}\nExternal IP: {external_ip}")


@run_async
def torrent(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update).split()

    local_ip = get_local_ip()
    transmission_url = f"{local_ip}:9091/transmission/web/"
    message = transmission_url
    last_message = message
    sent = send_message(update, message)

    times = 0
    while True:
        if times < 5:
            for link in args:
                times = 0

                try:
                    check_output(["transmission-remote", "-a", link], shell=False, stderr=STDOUT, text=True)
                except CalledProcessError as e:
                    send_message(update, "Invalid link")
                    logging.error(f"Invalid link: {link}  -  Error: {e}")
                    sys.exit(1)
                logging.info(f"Torrent added: {link}")

        message = transmission_url
        output = check_output(["transmission-remote", "-l"], text=True).split("\n")
        if len(output) == 3 and times >= 5:
            break
        for i in range(1, len(output) - 2):
            if output[i].split()[1] == "100%":
                check_output(["transmission-remote", "-t", output[i].split()[0].split("*")[0], "-r"])
                logging.info(f"Torrent completed: {output[i][70:]}")
                send_message(update, f"Torrent completed: {output[i][70:]}")
            else:
                message += "\n▶" + output[i][8:11] + output[i][13:32] + output[i][70:]
        message += f"\n{datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
        if last_message != message:
            try:
                sent.edit_text(message)
            except telegram.error.TimedOut:
                pass
            last_message = message

        if times < 5:
            args = queue.get(3)
            times += 1
        else:
            sleep(3)
    sent.edit_text("All torrents downloaded")
    logging.info("All torrents downloaded")


@run_async
def _download(update, link):
    logging.info(f"Download requested: {link}")
    try:
        r = requests.get(link, stream=True)
    except requests.exceptions.RequestException as e:
        send_message(update, "Invalid link")
        logging.error(f"Invalid link: {link}  -  Error: {e}")
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

    logging.info(f"Starting download: {name}")
    sent = send_message(update, f"Starting download: {name}")
    last_message = ""

    filename = name
    i = 0
    while os.path.exists(os.path.join(downloads_directory, filename)):
        i += 1
        filename = f"{os.path.splitext(name)[0]} ({i}){os.path.splitext(name)[1]}"

    with open(os.path.join(downloads_directory, filename), "wb") as f:
        for chunk in r.iter_content(chunk_size=2**22):
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
                except telegram.error.TimedOut:
                    pass
            last_message = message
    logging.info(f"Finished download: {name}")
    send_message(update, f"Finished download: {name}")


@run_async
def download(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update).split()
    times = 0
    if not args:
        send_message(update, "Enter link:")

    while times < 5:
        for a in args:
            _download(update, link=a)
            times = 0

        args = queue.get(3)
        times += 1


@run_async
def lock(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    if not args:
        args = "0"
    sleep(int(args))
    if sys.platform == "linux":
        if run(["xdg-screensaver", "lock"]).returncode == 4:
            pass
    elif sys.platform == "win32":
        Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
    send_message(update, f"{getpass.getuser()} screen locked")
    logging.info("Screen locked")


@run_async
def logout(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    if not args:
        args = "0"
    sleep(int(args))
    logging.info("Current user logging output")
    send_message(update, f"{getpass.getuser()} logging output")
    if sys.platform == "linux":
        Popen(["logout"])
    elif sys.platform == "win32":
        Popen(f"shutdown -l -f", shell=True)


@run_async
def suspend(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    if not args:
        args = "0"
    sleep(int(args))
    logging.info("Suspending system")
    send_message(update, "Suspending system")
    if sys.platform == "linux":
        Popen(["systemctl", "suspend"])
    elif sys.platform == "win32":
        Popen(f".\\nircmdc.exe standby", shell=True)


@run_async
def hibernate(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    if not args:
        args = "0"
    sleep(int(args))
    logging.info("Hibernating system")
    send_message(update, "Hibernating system")
    if sys.platform == "linux":
        Popen(["systemctl", "hibernate"])
    elif sys.platform == "win32":
        Popen(f"shutdown -h", shell=True)


@run_async
def reboot(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    if not args:
        args = "0"
    send_message(update, "Rebooting system")
    if sys.platform == "linux":
        sleep(int(args))
        Popen(["reboot"])
    elif sys.platform == "win32":
        Popen(f"shutdown -r -f -t {args}", shell=True)


@run_async
def shutdown(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    if not args:
        args = "0"
    send_message(update, "Shutting down system")
    if sys.platform == "linux":
        sleep(int(args))
        Popen(["poweroff"])
    elif sys.platform == "win32":
        Popen(f"shutdown -s -f -t {args}", shell=True)


@run_async
def volume(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    if args == "mute":
        if sys.platform == "linux":
            check_output(["pulseaudio-ctl", "mute"])
        elif sys.platform == "win32":
            check_output("./nircmdc.exe mutesysvolume 2", shell=True)
        logging.info("Volume mute toggled")
        send_message(update, "Volume mute toggled")
    elif args.isdigit():
        if sys.platform == "linux":
            check_output(["pulseaudio-ctl", "set", args])
        elif sys.platform == "win32":
            check_output("./nircmdc.exe changesysvolume " + str(int(int(args) / 100 * 65535)), shell=True)
        logging.info(f"Volume set to {args}")
        send_message(update, f"Volume set to {args}")


@run_async
def status(update: telegram.Update, context: telegram.ext.CallbackContext):
    send_message(update, f"Bot started\ndisplay_set={display_set}\nplatform={sys.platform}\nuser={getpass.getuser()}")


@run_async
def msgbox(update: telegram.Update, context: telegram.ext.CallbackContext):
    args = join_args(update)
    logging.info("MessageBox showed")
    send_message(update, "MessageBox showed")
    if display_set:
        wx.MessageBox(args, "Alert")
    else:
        print(args)
    logging.info("MessageBox accepted")
    send_message(update, "MessageBox accepted")


@run_async
def getcommands(update: telegram.Update, context: telegram.ext.CallbackContext):
    commands_list = ("status - Get status of bot", "screen - Get a screenshot", "torrent - Download a torrent", "download - Download a file", "log - Get stdout and stderr", "ip - Get local and external IPs",
                     "mouse - Control mouse", "cmd - Execute a command", "lock - Lock computer", "logout - Log out current user", "suspend - Suspend computer", "hibernate - Hibernate computer", "reboot - Reboot computer",
                     "shutdown - Shut down computer", "volume - Change volume or mute", "msgbox - Display a messagebox", "restart - Restart bot", "keyboard - Emulate keyboard", "getcommands - Get list of commands",
                     "start - Get initial message")
    missing = set(commands + x_commands) - set(i.split()[0] for i in commands_list)
    if missing:
        logging.error(f"Commmands not written in getcommands: {', '.join([i for i in missing])}")
    not_existing = set(i.split()[0] for i in commands_list) - set(commands + x_commands)
    if not_existing:
        logging.error(f"Commmands not existing written in getcommands: {', '.join([i for i in not_existing])}")
    send_message(update, "\n".join(commands_list))


@run_async
def log(update: telegram.Update, context: telegram.ext.CallbackContext):
    send_message(update, sys.stdout.get_std(1).getvalue())


# Handles

def handle_commands(update: telegram.Update, context: telegram.ext.CallbackContext):
    message = update.message.text
    chat_id = update.message.chat_id
    if chat_id == config.chat_id:
        logging.info(f"Command arrived: {message}")
        try:
            command_str = message.split(" ")[0].lstrip("/")
            if command_str in commands or (display_set and command_str in x_commands):
                eval(command_str)(update, context)
        except NameError:
            send_message(update, f"Command {message} doesn't exist or can't be executed")
            logging.warning(f"Command {message} doesn't exist or can't be executed")
    else:
        logging.critical(update)
        send_message(update, "SOS\n" + str(update))


def handle_text(update: telegram.Update, context: telegram.ext.CallbackContext):
    message = update.message.text
    chat_id = update.message.chat_id
    if chat_id == config.chat_id:
        logging.info(f"Message arrived: {message}")
    else:
        logging.critical(update)
        send_message(update, "SOS\n" + str(update))
    queue.put(message)


def handle_photo(update: telegram.Update, context: telegram.ext.CallbackContext):
    file = update.message.effective_attachment[2]
    logging.info("Photo arrived")
    file.get_file().download(os.path.join(downloads_directory, f"Photo_{str(datetime.datetime.now())}"))


def handle_file(update: telegram.Update, context: telegram.ext.CallbackContext):
    file = update.message.effective_attachment
    filename = file.file_name
    logging.info(f"File arrived: {filename}")
    file.get_file().download(os.path.join(downloads_directory, f"{filename}_{str(datetime.datetime.now())}"))


def unknown(update: telegram.Update, context: telegram.ext.CallbackContext):
    logging.critical(f"Unknown message received: {update.message}")


def handle_errors(update: telegram.Update, context: telegram.ext.CallbackContext):
    try:
        raise context.error
    except telegram.error.Conflict as e:
        logging.error(e)
        logging.critical('Stopping bot')
        os._exit(1)


if __name__ == '__main__':
    stds = StringIO()
    sys.stdout = Interceptor([sys.stdout, stds, open('logs.txt', 'a')])
    sys.stderr = Interceptor([sys.stderr, stds, open('logs.txt', 'a')])

    log_date_format = '%Y-%m-%d %H:%M:%S'
    log_format = f'%(asctime)s {getpass.getuser()} %(levelname)s %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, datefmt=log_date_format, format=log_format)
    # coloredlogs.install(stream=sys.stdout, level=logging.INFO, datefmt=log_date_format, fmt=log_format)

    if sys.platform == "win32":
        import winreg
        sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        downloads_guid = '{374DE290-123F-4565-9164-39C4925E467B}'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
            downloads_directory = winreg.QueryValueEx(key, downloads_guid)[0]
    elif sys.platform == "linux":
        from gi.repository import GLib
        downloads_directory = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
    else:
        raise NotImplementedError

    display_set = False

    updater = Updater(token=config.bot_token, use_context=True,)
    dispatcher = updater.dispatcher
    t_bot = telegram.Bot(token=config.bot_token)

    commands = ["cmd", "ip", "torrent", "lock", "logout", "suspend", "hibernate", "reboot", "shutdown", "volume", "msgbox", "restart", "status", "getcommands", "download", "log", "start"]
    x_commands = ["screen", "keyboard", "mouse"]

    for c in commands + x_commands:
        dispatcher.add_handler(CommandHandler(c, handle_commands))

    dispatcher.add_handler(MessageHandler(Filters.text, handle_text))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo))
    dispatcher.add_handler(MessageHandler(Filters.document, handle_file))
    dispatcher.add_handler(MessageHandler(Filters.entity(telegram.MessageEntity.BOT_COMMAND), handle_commands))
    dispatcher.add_handler(MessageHandler(Filters.all, unknown))
    dispatcher.add_error_handler(handle_errors)

    queue = AsyncWriter()

    updater.start_polling()
    start(chat_id=config.chat_id)
    logging.info("Bot started")

    while not display_set:
        try:
            from screen import *
            import pyautogui
            import wx

            app = wx.App()

            # import wxasync
            # app = wxasync.WxAsyncApp()

            pyautogui.FAILSAFE = False

            display_set = True
        except (KeyError, Xlib.error.DisplayConnectionError):
            sleep(15)

    while True:
        try:
            t_bot.send_chat_action(chat_id=config.chat_id, action=telegram.ChatAction.TYPING)
            sleep(4)
        except telegram.error.TimedOut:
            pass
