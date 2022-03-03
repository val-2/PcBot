#!/home/val/venv/bin/python
import datetime
import getpass
import inspect
import logging
import multiprocessing
import os.path
import pathlib
import socket
import sys
import threading
import time
import traceback
from io import StringIO, BytesIO

import pkg_resources
import rpyc
import telegram
import urllib3
from telegram.ext import Updater, Filters, CommandHandler, MessageHandler  # , CallbackQueryHandler

from pcbot import PcBotConfig
from pcbot import PcBotCore as Core
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


class Interceptor:
    def __init__(self, intercepted):
        self.intercepted = intercepted

    def __getattr__(self, item):
        attr = self.intercepted[0].__getattribute__(item)
        if hasattr(attr, '__call__'):
            def func(*args, **kwargs):
                result = attr(*args, **kwargs)
                for interc in self.intercepted[1:]:
                    interc.__getattribute__(item)(*args, **kwargs)
                return result

            return func
        else:
            for i in self.intercepted[1:]:
                i.__getattribute__(item)
            return attr


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
    sys.stdout = Interceptor([sys.stdout, stds, open(logs_fn, 'a', encoding='UTF-8', buffering=1)])
    sys.stderr = Interceptor([sys.stderr, stds, open(logs_fn, 'a', encoding='UTF-8', buffering=1)])

    log_date_format = '%Y-%m-%d %H:%M:%S'
    log_format = f'%(asctime)s {sys.platform} {getpass.getuser()} %(levelname)s %(module)s:%(lineno)d %(message)s'

    # noinspection PyTypeChecker
    logging.basicConfig(level=20, datefmt=log_date_format, format=log_format, stream=sys.stdout)
    sys.excepthook = handle_critical_error


def traceback_exception(e):
    return f'{"".join(traceback.format_tb(e.__traceback__))}{repr(e)}'


def handle_critical_error(exc_type, exc_value, exc_traceback):
    logging.critical(f'Exception in PcBot main thread:\n{"".join(traceback_exception(exc_value))}')
    if 'icon' in globals():
        if icon.connected:
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

    def __init__(self):
        self.connected = False
        self.fills = ['limegreen']
        self.p = multiprocessing.Process(target=PcBotIcon.main, daemon=True)
        self.p.start()
        threading.Thread(target=self.connect, daemon=True).start()

    def connect(self):
        for i in range(5):
            try:
                self.conn = rpyc.connect("localhost", 17778, service=PcBotService)
            except ConnectionRefusedError:
                logger.error('Connection to icon process failed. Retrying...')
                time.sleep(1)
                continue
            self.bgsrv = rpyc.BgServingThread(self.conn)
            self.change_image(self.fills[-1])
            self.connected = True
            logger.info('Connection to icon process established')
            return
        else:
            logger.critical('Failed to connect to icon process')
            self.p.terminate()

    def change_image(self, fill='limegreen'):
        if not self.connected:
            self.fills.append(fill)
        self.conn.root.change_image(fill)

    def visible(self, visible):
        self.conn.root.visible(visible)

    def notify(self, s):
        self.conn.root.notify(s)

    def menu(self, m):  # not working with callables
        self.conn.root.menu(m)

    def update_menu(self):
        self.conn.root.update_menu()


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


def check_commands_requirements(commands_list):
    unsatisfied_req = set()
    for c in commands_list:
        unsatisfied_req.update(check_requirements(c.requirements()))
    unsatisfied_req_str = "' '".join(unsatisfied_req)
    return unsatisfied_req_str


def check_chat_id(update: telegram.Update, chat_ids):
    if update.message.chat_id not in chat_ids:
        for conf in chat_ids:
            Core.send_message(conf, f"Unauthorized user {update.message.from_user.name} with chat id {update.message.chat_id} sent message", log_level=logging.WARNING)
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
        return 'Get all imported_commands and respective descriptions for BotFather'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        commands_list = [f'{i.name()} - {i.description()}' for i in self.pcbot.commands.values()]
        Core.send_message(update, "\n".join(commands_list))


class Logs(Core.Command):
    def name(self):
        return 'logs'

    def description(self):
        return 'Get stout and stderr'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        context.bot.send_document(update.message.chat_id, document=BytesIO(sys.stdout.intercepted[1].getvalue().encode()), filename='logs.txt')


class Debug(Core.Command):
    def name(self):
        return 'debug'

    def description(self):
        return 'Toggle debug'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        Core.send_message(update, f'Debug logging {toggle_debug()}')


class Reload(Core.Command):  # TODO probably not working
    def name(self):
        return 'reload'

    def description(self):
        return 'Reload all imported_commands'

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        del sys.modules['dynamiccommands']
        import dynamiccommands
        self.pcbot.dynamic_commands = dict_from_commands(dynamiccommands.dynamic_commands)

        del sys.modules['imported_commands']
        self.pcbot.imported_commands = self.pcbot.refresh_cmds()
        self.pcbot.dispatcher.handlers[0][0] = CommandHandler(self.pcbot.imported_commands, self.pcbot.handle_commands)

        Core.send_message(update, "Commands reloaded")


class DynamicCommands(Core.Command):
    def name(self):
        return 'dynamiccommands'

    def description(self):
        return 'Get all dynamic imported_commands and respective descriptions'

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
        self.chat_ids = config['chat_ids']
        self.local_directory = local_directory
        self.commands_list = self.instance_commands_if_not(commands_list)
        self.commands = {}
        self.dynamic_commands_list = self.instance_commands_if_not(dynamic_commands_list)
        self.dynamic_commands = {}
        self.stop_loop = threading.Event()
        self.prepared = False

    def prepare(self):
        Core.home = self.local_directory
        Core.media = f'{Core.home}/Media'
        try:
            os.mkdir(Core.media)
        except FileExistsError:
            pass

        unsatisfied_commands_req = check_commands_requirements(self.commands_list)
        if unsatisfied_commands_req:
            logger.warning(f"Unsatisfied imported_commands requirement(s): '{unsatisfied_commands_req}'")
        self.commands = self.refresh_cmds()

        unsatisfied_dynamic_commands_req = check_commands_requirements(self.dynamic_commands_list)
        if unsatisfied_dynamic_commands_req:
            logger.warning(f"Unsatisfied dynamic imported_commands requirement(s): '{unsatisfied_dynamic_commands_req}'")
        self.dynamic_commands = dict_from_commands(self.dynamic_commands_list)

        self.updater = Updater(token=self.config['bot_token'])
        self.dispatcher = self.updater.dispatcher
        self.t_bot = telegram.Bot(token=self.config['bot_token'])

        self.dispatcher.add_handler(CommandHandler(list(self.commands), self.handle_commands, run_async=True))
        self.dispatcher.add_handler(MessageHandler(Filters.text, self.handle_text_dynamiccmds, run_async=True))
        self.dispatcher.add_handler(MessageHandler(Filters.photo, self.handle_photo, run_async=True))
        self.dispatcher.add_handler(MessageHandler(Filters.document, self.handle_file, run_async=True))
        # self.dispatcher.add_handler(MessageHandler(Filters.entity(telegram.MessageEntity.BOT_COMMAND), handle_commands, run_async=True))  # TODO what does it do
        # TODO self.dispatcher.add_handler(CallbackQueryHandler(handle_buttons, run_async=True))
        self.dispatcher.add_handler(MessageHandler(Filters.all, self.handle_all_the_rest, run_async=True))
        self.dispatcher.add_error_handler(self.handle_errors)

        self.prepared = True

    def instance_commands_if_not(self, commands):
        return [c(self) if inspect.isclass(c) else c for c in commands]

    def refresh_cmds(self):
        commands_list = self.instance_commands_if_not([Status, DynamicCommands, *self.commands_list, Start, Commands, Logs, Debug, Reload, Stop])
        return dict_from_commands(commands_list)

    def start(self):
        if not self.prepared:
            self.prepare()

        while True:
            block_until_connected()
            try:
                self.updater.start_polling()
                break
            except telegram.error.NetworkError:
                continue

        # for c_id in self.chat_ids:
        #     Start().execute(chat_id=c_id)

        logger.info("Bot started")

        logging.info('Main loop started')
        while not self.stop_loop.is_set():
            try:
                time.sleep(4)
                for c_id in self.chat_ids:
                    self.t_bot.send_chat_action(chat_id=c_id, action=telegram.ChatAction.TYPING)
            except telegram.error.TimedOut:
                logging.debug('Sending typing chat action failed')
            except (urllib3.exceptions.HTTPError, telegram.error.NetworkError):
                icon.change_image('red')
                block_until_connected()
                icon.change_image()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.critical(f"Exception not handled in main loop:\n{traceback_exception(e)}")
                icon.notify(f"Exception not handled in main loop: {repr(e)}")
        icon.bgsrv.stop()
        icon.conn.close()
        self.stop_loop.clear()
        self.updater.stop()
        logger.info('Main loop ended')

    # Handles

    def handle_commands(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        message = update.message.text

        if not check_chat_id(update, self.chat_ids):
            return
        logger.info(f"Command received: {message}")
        command_str = message.split(" ")[0].lstrip("/")
        if command_str in self.commands:
            try:
                self.commands[command_str].execute(update, context)
            except Exception as e:
                Core.send_message(update, f"Exception during {command_str} execution: {repr(e)}", log_level=10)
                logger.error(f"Exception during {command_str} execution:\n{traceback_exception(e)}")
        else:
            Core.send_message(update, f"Command {message} doesn't exist", log_level=logging.WARNING)

    def handle_text_dynamiccmds(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        message = update.message.text
        if not check_chat_id(update, self.chat_ids):
            return
        if message[0] == '/':
            if (command_str := message.split(" ")[0].lstrip("/")) in self.dynamic_commands:
                logger.info(f"Dynamic command received: {message}")
                if self.dynamic_commands[command_str].can_be_executed():
                    try:
                        self.dynamic_commands[command_str].execute(update, context)
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

    def handle_photo(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if not check_chat_id(update, self.chat_ids):
            return
        file = update.message.effective_attachment[2]
        logger.info("Photo received")
        file.get_file().download(os.path.join(Core.media, f"Photo_{str(datetime.datetime.now())}"))

    def handle_file(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if not check_chat_id(update, self.chat_ids):
            return
        file = update.message.effective_attachment
        filename = file.file_name
        logger.info(f"File received: {filename}")
        file.get_file().download(os.path.join(Core.media, f"{filename}_{str(datetime.datetime.now())}"))

    def handle_all_the_rest(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        if check_chat_id(update, self.chat_ids):
            return
        logger.warning(f"Unhandled message received: {update.message}")
        Core.send_message(update, "Unhandled message")

    def handle_errors(self, update, context: telegram.ext.CallbackContext):
        try:
            raise context.error
        except telegram.error.Conflict as e:
            logger.critical(f'Stopping bot: other bot instance detected. Exception:\n{traceback_exception(e)}')
            os._exit(1)
        except telegram.error.NetworkError:
            pass
        except Exception as e:
            logger.error(f"Exception not handled in handle_errors:{traceback_exception(e)}")


def main():
    from pcbot.commands import commands

    try:
        from pcbot.dynamiccommands import dynamic_commands
    except ModuleNotFoundError:
        dynamic_commands = []

    global icon
    icon = Icon()

    pcbot = PcBot(PcBotConfig.get_config(), PcBotConfig.get_local_directory(), commands, dynamic_commands)
    pcbot.start()


custom_logs()
logger = logging.getLogger(__name__)
logger.setLevel(20)

icon: Icon

if __name__ == '__main__':
    main()
    # TODO show logs or logs folder in icon menu
    # TODO args parse -d to start as daemon and return
