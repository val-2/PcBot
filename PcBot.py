#!/home/val/venv/bin/python
import datetime
import getpass
import logging
import os.path
import pathlib
import runpy
import socket
import sys
import time
import traceback
from io import StringIO, BytesIO

import async_streamer
import interceptor
import pkg_resources
import pystray
import telegram
import urllib3
from PIL import Image, ImageDraw
from telegram.ext import Updater, Filters, CommandHandler, MessageHandler, CallbackQueryHandler

import PcBotCore as Core
import PcBotConfig


def name_to_command(c):
    d = {}
    for i in c:
        d[i.name()] = i
    return d


def block_until_connected():
    logged = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    while True:
        try:
            sock.connect(("api.telegram.org", 443))
            break
        except socket.error as e:
            if not logged:
                logger.warning(f"Connection lost. Exception:\n{traceback_exception(e)}")
                logged = True
            else:
                logger.log(15, f"Connection lost. Exception:\n{traceback_exception(e)}")
            time.sleep(3)
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()
    logger.info("Connection established")


def custom_logs():
    home = {'win32': os.path.join(pathlib.Path.home(), 'AppData', 'Local', 'pcbot'),
            'linux': os.path.join(pathlib.Path.home(), '.local', 'share', 'pcbot')}[sys.platform]

    try:
        os.mkdir(home)
    except FileExistsError:
        pass

    logs_fn = os.path.join(home, 'logs.txt')

    open(logs_fn, 'a').close()
    with open(logs_fn, 'r+') as f:
        data = f.readlines()
        if len(data) > 1000:
            f.seek(0)
            f.writelines(data[-1000:])
            f.truncate()

    stds = StringIO()
    sys.stdout = interceptor.Interceptor([sys.stdout, stds, open(logs_fn, 'a', encoding='UTF-8')])
    sys.stderr = interceptor.Interceptor([sys.stderr, stds, open(logs_fn, 'a', encoding='UTF-8')])

    log_date_format = '%Y-%m-%d %H:%M:%S'
    log_format = f'%(asctime)s {sys.platform} {getpass.getuser()} %(levelname)s %(module)s:%(lineno)d %(message)s'

    # noinspection PyTypeChecker
    logging.basicConfig(level=20, datefmt=log_date_format, format=log_format, stream=sys.stdout)


def traceback_exception(e):
    return f'{"".join(traceback.format_tb(e.__traceback__))}{repr(e)}'


def handle_critical_error(exc_value):
    logging.critical(f'Exception in PcBot main thread:\n{"".join(traceback_exception(exc_value))}')

    def critical_setup(icon):
        icon.visible = True
        icon.notify(f"Exception in PcBot main thread: {repr(exc_value)}")

    def _restart(icon):
        handle_critical_error.restart_program = True
        icon.stop()

    handle_critical_error.restart_program = False

    icon = pystray.Icon(f'PcBotException_{time.time()}')
    icon.menu = pystray.Menu(pystray.MenuItem('Restart', _restart), pystray.MenuItem('Exit', icon.stop))
    icon.icon = create_image('black')
    icon.run(setup=critical_setup)
    return handle_critical_error.restart_program


def toggle_debug():
    global debug
    debug = not debug
    logging.basicConfig(level=20-debug*5)


def check_requirements(requirements):
    unsatisfied_requirements = set()
    if isinstance(requirements, str):
        try:
            pkg_resources.require(requirements)
        except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as e:
            unsatisfied_requirements.add(str(e.req))
    else:
        for r in requirements:
            try:
                pkg_resources.require(r)
            except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as e:
                unsatisfied_requirements.add(str(e.req))
    return unsatisfied_requirements


def _stop_bot():
    global stop_loop
    logger.info('Stopping bot updater')
    updater.stop()
    logger.info('Bot updater stopped')
    logger.info('Stopping icon loop')
    stop_loop = True
    icon.stop()


def _restart_bot():
    logger.info('Restarting program')
    _stop_bot()
    del sys.modules['dynamiccommands']
    del sys.modules['commands']
    global restart_program
    restart_program = True


def check_chat_id(update: telegram.Update):
    if update.message.chat_id not in config['chat_ids']:
        for c in config['chat_ids']:
            Core.send_message(c, f"Unauthorized user {update.message.from_user.name} with chat id {update.message.chat_id} sent message", log_level=logging.WARNING)
        Core.send_message(update, 'User not authorized')
        return False
    else:
        return True


# Commands

class Start(Core.Command):
    def name(self):
        return 'start'

    def description(self):
        return 'Send initial message'

    def execute(self, update=None, context=None, chat_id=None):
        oses = {'linux': 'Linux', 'win32': 'Windows', 'darwin': 'MacOS'}
        op_sys = oses.get(sys.platform, 'unknown OS')
        Core.t_bot.send_message(chat_id=update.message.chat_id if update else chat_id, text=f"{getpass.getuser()} started pc on {op_sys}", disable_notification=True)


class Status(Core.Command):
    def name(self):
        return 'status'

    def description(self):
        return 'Send bot status'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        Core.send_message(update, f"Bot started\nplatform={sys.platform}\nuser={getpass.getuser()}")


class RestartBot(Core.Command):
    def name(self):
        return 'restartbot'

    def description(self):
        return 'Restart bot'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        Core.send_message(update, 'Restarting bot...')
        import threading
        t = threading.Thread(target=_restart_bot)
        t.start()


class Stop(Core.Command):
    def name(self):
        return 'stop'

    def description(self):
        return 'Stop bot execution'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        Core.send_message(update, 'Shutting down bot...')
        import threading
        t = threading.Thread(target=_stop_bot)
        t.start()


class Commands(Core.Command):
    def name(self):
        return 'commands'

    def description(self):
        return 'Get all commands and respective descriptions for BotFather'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        commands_list = [f'{i.name()} - {i.description()}' for i in cmds.values()]
        Core.send_message(update, "\n".join(commands_list))


class Logs(Core.Command):
    def name(self):
        return 'logs'

    def description(self):
        return 'Get stout and stderr'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        Core.t_bot.send_document(update.message.chat_id, document=BytesIO(sys.stdout.get_std(1).getvalue().encode()), filename='logs.txt')


class Reload(Core.Command):
    def name(self):
        return 'reload'

    def description(self):
        return 'Reload all commands'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        del sys.modules['dynamiccommands']
        import dynamiccommands
        global dynamiccmds
        dynamiccmds = name_to_command(dynamiccommands.dynamiccmds)

        del sys.modules['commands']
        import commands
        global cmds
        cmds = get_cmds()
        dispatcher.handlers[0][0] = CommandHandler(cmds, handle_commands)

        Core.send_message(update, "Commands reloaded")


class DynamicCommands(Core.Command):
    def name(self):
        return 'dynamiccommands'

    def description(self):
        return 'Get all dynamic commands and respective descriptions'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if dynlist := '\n'.join([f'/{i.name()} - {i.description()}' for i in dynamiccmds.values() if i.can_be_executed()]):
            Core.send_message(update, dynlist)
        else:
            Core.send_message(update, 'No dynamic command available')


# Handles

def handle_commands(update: telegram.Update, context: telegram.ext.CallbackContext):
    message = update.message.text

    if check_chat_id(update):
        logger.info(f"Command received: {message}")
        command_str = message.split(" ")[0].lstrip("/")
        if command_str in cmds:
            try:
                cmds[command_str].execute(update, context)
            except Exception as e:
                Core.send_message(update, f"Exception during {command_str} execution: {repr(e)}", log_level=10)
                logger.error(f"Exception during {command_str} execution:\n{traceback_exception(e)}")
        else:
            Core.send_message(update, f"Command {message} doesn't exist", log_level=logging.WARNING)


def handle_text_dynamiccmds(update: telegram.Update, context: telegram.ext.CallbackContext):
    message = update.message.text

    if check_chat_id(update):
        if message[0] == '/':
            if (command_str := message.split(" ")[0].lstrip("/")) in dynamiccmds:
                logger.info(f"Dynamic command received: {message}")
                if dynamiccmds[command_str].can_be_executed():
                    try:
                        dynamiccmds[command_str].execute(update, context)
                    except Exception as e:
                        Core.send_message(update, f"Exception during {command_str} execution: {repr(e)}", log_level=10)
                        logger.error(f"Exception during {command_str} execution:\n{traceback_exception(e)}")
                else:
                    Core.send_message(update, f"Dynamic command {command_str} not executable")
            else:
                Core.send_message(update, f"Unknown dynamic command: {message}")
        else:
            logger.info(f"Message received: {message}")
            Core.msg_queue.put(message)


def handle_photo(update: telegram.Update, context: telegram.ext.CallbackContext):
    if check_chat_id(update):
        file = update.message.effective_attachment[2]
        logger.info("Photo received")
        file.get_file().download(os.path.join(Core.media, f"Photo_{str(datetime.datetime.now())}"))


def handle_file(update: telegram.Update, context: telegram.ext.CallbackContext):
    if check_chat_id(update):
        file = update.message.effective_attachment
        filename = file.file_name
        logger.info(f"File received: {filename}")
        file.get_file().download(os.path.join(Core.media, f"{filename}_{str(datetime.datetime.now())}"))


def handle_all_the_rest(update: telegram.Update, context: telegram.ext.CallbackContext):
    if check_chat_id(update):
        logger.warning(f"Unhandled message received: {update.message}")
        Core.send_message(update, "Unhandled message")


def handle_errors(update: telegram.Update, context: telegram.ext.CallbackContext):
    try:
        raise context.error
    except telegram.error.Conflict as e:
        logger.critical(f'Stopping bot: other bot instance detected. Exception:\n{traceback_exception(e)}')
        os._exit(1)
    except telegram.error.NetworkError:
        pass
    except Exception as e:
        logger.error(f"Exception not handled in handle_errors:{traceback_exception(e)}")


def create_image(fill='limegreen'):
    x = 21
    y = x * 5 // 6
    image = Image.new('RGBA', (x+1, y+1))
    final_image = Image.new('RGBA', (x+1, x+1))
    dc = ImageDraw.Draw(image)

    x0_display = int(x*.1)
    y0_display = int(y*.12)
    x0_stand = int(x*.45)
    y0_stand = int(y*.8)
    x0_base = int(x*.30)
    y0_base = int(y*39/40+1)

    dc.rectangle((x0_base, y0_base, x-x0_base, y), fill='lightgray')  # base
    dc.rectangle((x0_stand, y0_stand, x-x0_stand, y0_base), fill='lightgray')  # stand
    dc.rectangle((0, 0, x, y0_stand), fill='white')  # frame
    dc.rectangle((x0_display, y0_display, x-x0_display, y0_stand-y0_display), fill=fill)  # display
    final_image.paste(image, (max(0, (y-x)//2), max(0, (x-y)//2)))
    return final_image


if __name__ == '__main__':
    custom_logs()
    while True:
        try:
            restart_program = runpy.run_path(__file__).get('restart_program', False)
        except Exception as e:
            restart_program = handle_critical_error(e)
        if restart_program:
            logging.info('Program thread exited. Restarting...')
        else:
            break
    logging.info('Main thread exited')
else:
    debug = False

    local_directory = {'win32': os.path.join(pathlib.Path.home(), 'AppData', 'Local', 'pcbot'), 'linux': os.path.join(pathlib.Path.home(), '.local', 'share', 'pcbot')}
    config = PcBotConfig.get_config()
    Core.home = local_directory[sys.platform]
    Core.media = f'{Core.home}/Media'
    try:
        os.mkdir(Core.media)
    except FileExistsError:
        pass

    logs_filename = os.path.join(Core.home, 'logs.txt')
    logger = logging.getLogger(__name__)

    if __name__ != '<run_path>':
        logger.critical("Program not started in the standard way")

    import commands

    unsatisfied_req = set()
    for c in commands.commands:
        unsatisfied_req.update(check_requirements(c.requirements()))
    if unsatisfied_req:
        unsatisfied_req_str = "' '".join(unsatisfied_req)
        logger.warning(f"Unsatisfied commands requirement(s): '{unsatisfied_req_str}'")

    def get_cmds():
        return name_to_command([Status(), DynamicCommands(), *commands.commands, Start(), Commands(), Logs(), Reload(), RestartBot(), Stop()])

    cmds = get_cmds()

    try:
        import dynamiccommands
        dynamiccmds = dynamiccommands.dynamiccmds
    except ModuleNotFoundError:
        dynamiccmds = []

    unsatisfied_req_dyn = set()
    for d in dynamiccmds:
        unsatisfied_req_dyn.update(check_requirements(d.requirements()))
    if unsatisfied_req_dyn:
        unsatisfied_req_dyn_str = "' '".join(unsatisfied_req_dyn)
        logger.warning(f"Unsatisfied dynamic commands requirement(s): '{unsatisfied_req_dyn_str}'")

    dynamiccmds = name_to_command(dynamiccmds)

    icon = pystray.Icon(f'PcBot_{time.time()}')
    icon.menu = pystray.Menu(pystray.MenuItem('Debug', toggle_debug), pystray.MenuItem('Restart', _restart_bot), pystray.MenuItem('Exit', _stop_bot))

    updater = Updater(token=config['bot_token'], use_context=True)
    dispatcher = updater.dispatcher
    Core.t_bot = telegram.Bot(token=config['bot_token'])

    Core.msg_queue = async_streamer.AsyncWriter()

    dispatcher.add_handler(CommandHandler(cmds, handle_commands, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_text_dynamiccmds, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.document, handle_file, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.entity(telegram.MessageEntity.BOT_COMMAND), handle_commands, run_async=True))
    # TODO dispatcher.add_handler(CallbackQueryHandler(handle_buttons, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.all, handle_all_the_rest, run_async=True))
    dispatcher.add_error_handler(handle_errors)

    while True:
        block_until_connected()
        try:
            updater.start_polling()
            break
        except telegram.error.NetworkError:
            continue
    for c_id in config['chat_ids']:
        Start().execute(chat_id=c_id)

    logger.info(f"Logs file: {logs_filename}")
    logger.info("Bot started")

    stop_loop = False

    def icon_loop(icon=None):
        global stop_loop
        icon.visible = True
        logging.info('Icon loop started')
        while not stop_loop:
            try:
                time.sleep(4)
                for c_id in config['chat_ids']:
                    Core.t_bot.send_chat_action(chat_id=c_id, action=telegram.ChatAction.TYPING)
            except telegram.error.TimedOut:
                logging.debug('Sending typing chat action failed')
            except (urllib3.exceptions.HTTPError, telegram.error.NetworkError):
                icon.icon = create_image('red')
                block_until_connected()
                icon.icon = create_image()
            except Exception as e:
                logger.critical(f"Exception not handled in icon loop:\n{traceback_exception(e)}")
                icon.notify(f"Exception not handled in icon loop: {repr(e)}")
        icon.visible = False
        stop_loop = False
        logger.info('Icon loop ended')

    icon.icon = create_image()
    icon.run(setup=icon_loop)

    if icon._running:
        logger.info('Stopping icon loop')
        try:
            stop_loop = True
            icon.stop()
        except Exception as e:
            logger.error(f'Exception while stopping icon:\n{traceback_exception(e)}')

