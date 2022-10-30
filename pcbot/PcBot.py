import argparse
import datetime
import getpass
import inspect
import io
import logging
import multiprocessing
import os
import pathlib
import random
import socket
import subprocess
import sys
import threading
import time
import traceback

import customlogs
import pkg_resources
import rpyc
import telegram
import urllib3.exceptions
from customlogs import print
from telegram.ext import Updater, Filters, CommandHandler, MessageHandler  # , CallbackQueryHandler

from pcbot import PcBotConfig
from pcbot import PcBotCore as Core

if Core.GRAPHICAL_SESSION_SET:
    from pcbot import PcBotIcon


def dict_from_commands(commands_list):
    commands_dict = {}
    for i in commands_list:
        commands_dict[i.name()] = i
    return commands_dict


def block_until_connected():
    logged = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    while True:
        try:
            sock.connect(("api.telegram.org", 443))
            logger.info("Connection established")
            break
        except socket.error as e:
            if not logged:
                logger.warning(f"Connection lost. Exception:\n{traceback_exception(e)}")
                logged = True
            else:
                logger.log(15, f"Connection lost. Exception:\n{traceback_exception(e)}")
            time.sleep(1)
    logger.log(15, 'Shutting down socket')
    sock.shutdown(socket.SHUT_RDWR)
    logger.log(15, 'Closing socket')
    sock.close()


def get_local_dir():
    return {'win32': pathlib.Path.home()/'AppData'/'Local'/'pcbot',
            'linux': pathlib.Path.home()/'.local'/'share'/'pcbot'}[sys.platform]


def traceback_exception(e):
    return f'{"".join(traceback.format_tb(e.__traceback__))}{repr(e)}'


def handle_critical_error(exc_type, exc_value, exc_traceback):
    logging.critical(f'Exception in PcBot main thread:\n{traceback_exception(exc_value)}')
    if icon.is_connected():
        icon.change_image('black')
        icon.notify(f"Exception in PcBot main thread: {repr(exc_value)}")


def toggle_debug():
    logger.setLevel(35 - logger.level)
    status = {False: "disabled", True: "enabled"}[logger.level <= 15]
    logging.info(f'Debug logging {status}')
    return status


class Icon:
    conn: rpyc.core.protocol.Connection
    bgsrv: rpyc.BgServingThread
    process: multiprocessing.Process
    connect_lock = threading.Lock()
    port = random.randint(10000, 65535)

    def __init__(self):
        self.fill = 'limegreen'
        self._visible = False
        if Core.GRAPHICAL_SESSION_SET:
            logging.info('Starting icon process')
            self.process = multiprocessing.Process(target=PcBotIcon.main, args=(self.port,), daemon=True)
            self.process.start()
            threading.Thread(target=self.connect, daemon=True).start()

    def connect(self):
        if self.connect_lock.acquire(blocking=False):
            time.sleep(.5)
            for i in range(5):
                try:
                    self.conn = rpyc.connect("localhost", self.port, service=PcBotService)
                except ConnectionRefusedError:
                    logger.error('Connection to icon process failed. Retrying...')
                    time.sleep(1)
                    continue
                self.bgsrv = rpyc.BgServingThread(self.conn)
                self.visible = True
                self.change_image(self.fill)
                logger.info('Connection to icon process established')
                return
            else:
                logger.critical('Failed to connect to icon process')
                self.process.terminate()
        else:
            logger.warning('Icon connection already in progress')

    def is_connected(self):
        return Core.GRAPHICAL_SESSION_SET and hasattr(self, 'conn') and not self.conn.closed

    def close(self):
        if self.is_connected():
            self.conn.close()
            self.bgsrv.stop()
            self.process.terminate()

    def change_image(self, fill: str = 'limegreen'):
        if self.is_connected():
            try:
                self.conn.root.change_image(fill)
                self.fill = fill
            except TimeoutError:
                logger.error('Timeout while changing icon image')

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, visible: bool):
        if self.is_connected():
            try:
                self.conn.root.visible(visible)
                self._visible = visible
            except TimeoutError:
                logger.error('Timeout while changing icon visibility')

    def notify(self, s: str):
        if self.is_connected():
            try:
                self.conn.root.notify(s)
            except TimeoutError:
                logger.error('Timeout while notifying')

    def menu(self, m):  # not working with callables
        if self.is_connected():
            try:
                self.conn.root.menu(m)
            except TimeoutError:
                logger.error('Timeout while updating menu')

    def update_menu(self):
        if self.is_connected():
            try:
                self.conn.root.update_menu()
            except TimeoutError:
                logger.error('Timeout while updating menu')


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
    logging.info('Stopping bot')
    os._exit(0)
    # logging.info('Stopping bot updater')
    # updater.stop()
    # logger.info('Bot updater stopped')
    # logger.info('Stopping main loop')
    # global stop_loop
    # stop_loop = True


class PcBotService(rpyc.Service):
    @staticmethod
    def exposed_toggle_debug():
        toggle_debug()

    @staticmethod
    def exposed_stop_bot():
        _stop_bot()


def check_commands_requirements(commands):
    commands_list = list(commands.values())
    unsatisfied_req = set()
    for c in commands_list:
        unsatisfied_req.update(check_requirements(c.requirements()))
    unsatisfied_req_str = "' '".join(unsatisfied_req)
    return unsatisfied_req_str


# Commands

class Start(Core.Command):
    def name(self):
        return 'start'

    def description(self):
        return 'Send initial message'

    def execute(self, update, context: telegram.ext.CallbackContext = None, chat_id: str = None):
        oses = {'linux': 'Linux', 'win32': 'Windows', 'darwin': 'MacOS'}
        op_sys = oses.get(sys.platform, 'unknown OS')
        msg_text = f"{getpass.getuser()} started pc on {op_sys}"
        if isinstance(update, telegram.Update):
            Core.send_message(update, text=msg_text, disable_notification=True)
        else:
            Core.send_message_chat_id(chat_id=chat_id, text=msg_text, bot=self.pcbot.t_bot, disable_notification=True)


class Status(Core.Command):
    def name(self):
        return 'status'

    def description(self):
        return 'Send bot status'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        Core.send_message(update, f"Bot started\nplatform={sys.platform}\nuser={getpass.getuser()}")


class Stop(Core.Command):
    def name(self):
        return 'stop'

    def description(self):
        return 'Stop bot execution'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        Core.send_message(update, 'Shutting down bot...')
        t = threading.Thread(target=_stop_bot)
        t.start()


class Commands(Core.Command):
    def name(self):
        return 'commands'

    def description(self):
        return 'Get all commands and their respective descriptions for BotFather'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        commands_list = [f'{i.name()} - {i.description()}' for i in self.pcbot.commands.values() if i.can_be_used()]
        Core.send_message(update, "\n".join(commands_list))


class Logs(Core.Command):
    def name(self):
        return 'logs'

    def description(self):
        return 'Get stout and stderr'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        context.bot.send_document(update.message.chat_id, document=io.BytesIO(sys.stdout.intercepted[1].getvalue().encode()), filename='logs.txt')


class Debug(Core.Command):
    def name(self):
        return 'debug'

    def description(self):
        return 'Toggle debug'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        Core.send_message(update, f'Debug logging {toggle_debug()}')


class Reload(Core.Command):
    def name(self):
        return 'reload'

    def description(self):
        return 'Reload all commands'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if 'pcbot.dynamiccommands' in sys.modules:
            del sys.modules['pcbot.dynamiccommands']
        else:
            Core.send_message(update, 'Dynamic commands module was not loaded')
        try:
            from pcbot.dynamiccommands import dynamic_commands
        except ModuleNotFoundError:
            dynamic_commands = []

        self.pcbot.dynamic_commands = self.pcbot.reload_dynamic_commands(dynamic_commands)

        del sys.modules['pcbot.commands']
        from pcbot.commands import commands
        self.pcbot.commands = self.pcbot.reload_commands(commands)
        self.pcbot.dispatcher.handlers[0][0] = CommandHandler(self.pcbot.commands, self.pcbot.handle_commands)

        Core.send_message(update, "Commands reloaded")


class DynamicCommands(Core.Command):
    def name(self):
        return 'dynamiccommands'

    def description(self):
        return 'Get all dynamic commands and respective descriptions'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if dynlist := '\n'.join([f'/{i.name()} - {i.description()}' for i in self.pcbot.dynamic_commands.values() if i.can_be_executed()]):
            Core.send_message(update, dynlist)
        else:
            Core.send_message(update, 'No dynamic command available')


class PcBot:
    updater: Updater
    dispatcher: telegram.ext.Dispatcher
    t_bot: telegram.Bot

    def __init__(self, config, local_directory, commands_list, dynamic_commands_list):
        self.config = config
        self.local_directory = local_directory
        self.commands = self.reload_commands(commands_list)
        self.dynamic_commands = self.reload_dynamic_commands(dynamic_commands_list)
        self.stop_loop = threading.Event()
        self._prepared = False

    def prepare(self):
        Core.home = self.local_directory
        Core.media = Core.home/'Media'
        Core.media.mkdir(parents=True, exist_ok=True)

        unsatisfied_commands_req = check_commands_requirements(self.commands)
        if unsatisfied_commands_req:
            logger.warning(f"Unsatisfied commands requirement(s): '{unsatisfied_commands_req}'")

        unsatisfied_dynamic_commands_req = check_commands_requirements(self.dynamic_commands)
        if unsatisfied_dynamic_commands_req:
            logger.warning(f"Unsatisfied dynamic commands requirement(s): '{unsatisfied_dynamic_commands_req}'")

        self.updater = Updater(token=self.config.bot_token)
        self.dispatcher = self.updater.dispatcher
        self.t_bot = telegram.Bot(token=self.config.bot_token)

        self.dispatcher.add_handler(CommandHandler(list(self.commands), self.handle_commands, run_async=True))
        self.dispatcher.add_handler(MessageHandler(Filters.text, self.handle_text_dynamiccmds, run_async=True))
        self.dispatcher.add_handler(MessageHandler(Filters.photo, self.handle_photo, run_async=True))
        self.dispatcher.add_handler(MessageHandler(Filters.document, self.handle_file, run_async=True))
        # TODO self.dispatcher.add_handler(CallbackQueryHandler(handle_buttons, run_async=True))
        self.dispatcher.add_handler(MessageHandler(Filters.all, self.handle_all_the_rest, run_async=True))
        self.dispatcher.add_error_handler(self.handle_errors)

        self._prepared = True

    def instance_commands_if_not(self, commands):
        return [c(self) if inspect.isclass(c) else c for c in commands]

    def reload_commands(self, commands_list: list[Core.Command]):
        all_commands_list = self.instance_commands_if_not([Status, DynamicCommands, *commands_list, Start, Commands, Logs, Debug, Reload, Stop])
        all_commands_list = [c for c in all_commands_list if c.can_be_used]
        return dict_from_commands(all_commands_list)

    def reload_dynamic_commands(self, dynamic_commands_list: list[Core.Command]):
        all_dynamic_commands_list = self.instance_commands_if_not(dynamic_commands_list)
        return dict_from_commands(all_dynamic_commands_list)

    @staticmethod
    def start_icon():
        global icon
        icon = Icon()

    def start(self):
        if not self._prepared:
            self.prepare()

        while True:
            block_until_connected()
            try:
                self.updater.start_polling()
                break
            except telegram.error.NetworkError:
                logger.warning("Network error, retrying...")
                continue

        # for c_id in self.config.chat_ids:
        #     Start().execute(chat_id=c_id)

        logger.info("Bot started")

        logging.info('Main loop started')
        while not self.stop_loop.is_set():
            # if Core.GRAPHICAL_SESSION_SET and not icon.is_connected():
            #     self.start_icon()
            try:
                time.sleep(4)  # the sleep must stay inside the try block, otherwise it will not catch the KeyboardInterrupt
                for c_id in self.config.chat_ids:
                    self.t_bot.send_chat_action(chat_id=c_id, action=telegram.ChatAction.TYPING)
            except KeyboardInterrupt:
                break
            except telegram.error.TimedOut:
                logging.debug('Sending typing chat action failed')
            except (urllib3.exceptions.HTTPError, telegram.error.NetworkError):
                logging.warning(f'Sending typing chat action failed')
                icon.change_image('red')
                block_until_connected()
                icon.change_image()
            except Exception as e:
                logger.critical(f"Exception not handled in main loop:\n{traceback_exception(e)}")
                icon.notify(f"Exception not handled in main loop: {repr(e)}")
        icon.close()
        self.stop_loop.clear()
        self.updater.stop()
        logger.info('Main loop ended')

    # Handles

    def handle_commands(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        message = update.message.text

        if not self.check_chat_id(update, context):
            return

        logger.info(f"Command received: {message}")
        command_str = message.split(" ")[0].lstrip("/")
        if command_str not in self.commands:
            Core.send_message(update, f"Command {message} doesn't exist", log_level=logging.WARNING)
            return

        try:
            self.commands[command_str].execute(update, context)
        except Exception as e:
            Core.send_message(update, f"Exception during {command_str} execution: {repr(e)}", log_level=10)
            logger.error(f"Exception during {command_str} execution:\n{traceback_exception(e)}")

    def handle_text_dynamiccmds(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        message = update.message.text
        if not self.check_chat_id(update, context):
            return

        if message[0] != '/':
            logger.info(f"Message received: {message}")
            Core.msg_queue.put(message)
            return

        if (command_str := message.split(" ")[0].lstrip("/")) not in self.dynamic_commands:
            Core.send_message(update, f"Unknown dynamic command: {message}")
            return

        logger.info(f"Dynamic command received: {message}")
        if not self.dynamic_commands[command_str].can_be_executed():
            Core.send_message(update, f"Dynamic command {command_str} not executable")
            return

        try:
            self.dynamic_commands[command_str].execute(update, context)
        except Exception as e:
            Core.send_message(update, f"Exception during {command_str} execution: {repr(e)}", log_level=10)
            logger.error(f"Exception during {command_str} execution:\n{traceback_exception(e)}")

    def handle_photo(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if not self.check_chat_id(update, context):
            return

        file = update.message.effective_attachment[2]
        logger.info("Photo received")
        file.get_file().download(str(Core.media/f"Photo_{str(datetime.datetime.now())}"))

    def handle_file(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if not self.check_chat_id(update, context):
            return

        file = update.message.effective_attachment
        filename = file.file_name
        logger.info(f"File received: {filename}")
        file.get_file().download(str(Core.media/f"{filename}_{str(datetime.datetime.now())}"))

    def handle_all_the_rest(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if not self.check_chat_id(update, context):
            return

        logger.warning(f"Unhandled message received: {update.message}")
        Core.send_message(update, "Unhandled message")

    @staticmethod
    def handle_errors(update: telegram.Update, context: telegram.ext.CallbackContext):
        try:
            raise context.error
        except telegram.error.Conflict as e:
            logger.critical(f'Stopping bot: other bot instance detected. Exception:\n{traceback_exception(e)}')
            icon.close()
            os._exit(1)
        except telegram.error.NetworkError:
            pass
        except Exception as e:
            logger.error(f"Exception not handled in handle_errors:\n{traceback_exception(e)}")

    def check_chat_id(self, update: telegram.Update, context: telegram.ext.CallbackContext):  # TODO otp
        if len(self.config.chat_ids) == 0:
            if input(f"Accept chat_id as authenticated? (y/n)") == "y":
                self.config.chat_ids.append(update.message.chat_id)
                PcBotConfig.save_config(self.config)
                return True

        if update.message.chat_id in self.config.chat_ids:
            return True

        for conf in self.config.chat_ids:
            Core.send_message(conf, f"Unauthorized user {update.message.from_user.name} with chat id {update.message.chat_id} sent message", log_level=logging.WARNING)
        Core.send_message(update, f"Your chat id is {update.message.chat_id}")
        return False


def main():
    customlogs.custom_logs(logs_filename=pathlib.Path(__file__).parent.parent.absolute() / 'logs' / f'pcbot_{sys.platform}.log',
                           log_format=f'[%(levelname)s] %(asctime)s {sys.platform} {getpass.getuser()} %(process)d %(module)s:%(lineno)d %(message)s')

    global logger
    sys.excepthook = handle_critical_error
    logger = logging.getLogger(__name__)
    logger.setLevel(20)

    parser = argparse.ArgumentParser(description="PcBot")
    parser.add_argument("-d", "--daemon", help="Start program as daemon", action="store_true", default=False)
    parser.add_argument("-m", "--message", help="Send message to all authenticated users", default=None)  # TODO
    args = parser.parse_args(sys.argv[1:])

    if args.daemon:
        new_args = list(filter(lambda val: val not in ['-d', '--daemon'], sys.argv))
        subprocess.Popen(new_args, close_fds=True)
        print("Daemon started")
        sys.exit(0)

    from pcbot.commands import commands

    try:
        from pcbot.dynamiccommands import dynamic_commands
    except ModuleNotFoundError as e:
        if "dynamiccommands" in str(e):
            logger.warning("Dynamic commands module not found")
            dynamic_commands = []
        else:
            raise e

    global icon
    icon = Icon()

    logger.info(f"Local directory: {PcBotConfig.get_local_directory().as_uri()}")
    pcb = PcBot(PcBotConfig.get_config(), PcBotConfig.get_local_directory(), commands, dynamic_commands)
    pcb.start()


logger: logging.Logger

icon: Icon

if __name__ == '__main__':
    main()
    # TODO create a way to send text messages, images, audio, ..., with or without notification, ... from other programs
    # probably creating a rpyc server that starts in main()
