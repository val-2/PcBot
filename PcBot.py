#!/home/val/venv/bin/python
import datetime
import getpass
import json
import logging
import os.path
import pathlib
import socket
import sys
import traceback
from io import StringIO, BytesIO
from time import sleep

import async_streamer
import interceptor
import pkg_resources
import telegram
import urllib3
from telegram.ext import Updater, Filters, CommandHandler, MessageHandler

import PcBotCore as Core


# import pystray  # TODO systray


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
        except socket.error:
            if not logged:
                logger.warning("Waiting for connection...")
                logged = True
            sleep(3)
    sock.close()
    logger.info("Connection established")


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


# def restart(update: telegram.Update, context: telegram.ext.CallbackContext):
#     _restart()
#     updater.stop()
#
#
# @run_async
# def _restart():
#     Popen([sys.executable] + sys.argv).wait()


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

    def execute(self, update, context):
        Core.send_message(update, f"Bot started\nplatform={sys.platform}\nuser={getpass.getuser()}")


class Commands(Core.Command):
    def name(self):
        return 'commands'

    def description(self):
        return 'Get all commands and respective descriptions for BotFather'

    def execute(self, update, context):
        commands_list = [f'{i.name()} - {i.description()}' for i in cmds.values()]
        Core.send_message(update, "\n".join(commands_list))


class Logs(Core.Command):
    def name(self):
        return 'logs'

    def description(self):
        return 'Get stout and stderr'

    def execute(self, update, context):
        Core.t_bot.send_document(update.message.chat_id, document=BytesIO(sys.stdout.get_std(1).getvalue().encode()), filename='logs.txt')


class Reload(Core.Command):
    def name(self):
        return 'reload'

    def description(self):
        return 'Reload all commands'

    def execute(self, update, context):
        del sys.modules['dynamiccommands']
        import dynamiccommands
        global dynamiccmds
        dynamiccmds = name_to_command(dynamiccommands.dynamiccmds)

        del sys.modules['commands']
        import commands
        global cmds
        cmds = name_to_command([Status(), DynamicCommands(), *commands.commands, Start(), Commands(), Logs(), Reload()])
        dispatcher.handlers[0][0] = CommandHandler(cmds, handle_commands)

        Core.send_message(update, "Commands reloaded")


class Stop(Core.Command):
    def name(self):
        return 'stop'

    def description(self):
        return 'Stop bot execution'

    def execute(self, update, context):
        Core.send_message(update, 'Stopping bot...')
        os._exit(1)


class DynamicCommands(Core.Command):
    def name(self):
        return 'dynamiccommands'

    def description(self):
        return 'Get all dynamic commands and respective descriptions'

    def execute(self, update, context):
        if dynlist := '\n'.join([f'/{i.name()} - {i.description()}' for i in dynamiccmds.values() if i.can_showup()]):
            Core.send_message(update, dynlist)
        else:
            Core.send_message(update, 'No dynamic command available')


# Handles

def handle_commands(update: telegram.Update, context: telegram.ext.CallbackContext):
    message = update.message.text
    chat_id = update.message.chat_id
    if chat_id in config['chat_ids']:
        logger.info(f"Command received: {message}")
        command_str = message.split(" ")[0].lstrip("/")
        if command_str in cmds:
            try:
                cmds[command_str].execute(update, context)
            except Exception as e:
                Core.send_message(update, f"Calling command {command_str} threw {e.__repr__()}", log_level=10)
                logger.error(f"Calling command {command_str} threw {e.__repr__()}\n{''.join(traceback.format_tb(e.__traceback__))}")
        else:
            Core.send_message(update, f"Command {message} doesn't exist", log_level=logging.WARNING)
    else:
        logger.critical(update)
        Core.send_message(update, "SOS\n" + str(update), log_level=logging.CRITICAL)


def handle_text_dynamiccmds(update: telegram.Update, context: telegram.ext.CallbackContext):
    message = update.message.text
    chat_id = update.message.chat_id

    if chat_id in config['chat_ids']:
        if message[0] == '/':
            if (command_str := message.split(" ")[0].lstrip("/")) in dynamiccmds:
                logger.info(f"Dynamic command received: {message}")
                if dynamiccmds[command_str].can_showup():
                    try:
                        dynamiccmds[command_str].execute(update, context)
                    except Exception as e:
                        Core.send_message(update, f"Calling dynamic command {command_str} threw {e.__repr__()}", log_level=10)
                        logger.error(f"Calling dynamic command {command_str} threw {e.__repr__()}\n{''.join(traceback.format_tb(e.__traceback__))}")
                else:
                    Core.send_message(update, f"The dynamic command {command_str} cannot be executed")  # TODO specify sender
            else:
                logger.info(f"Unknown dynamic command: {message}")
                Core.send_message(update, f"Unknown dynamic command: {message}")
        else:
            logger.info(f"Message received: {message}")
            Core.msg_queue.put(message)
    else:
        logger.critical(update)
        Core.send_message(update, "SOS\n" + str(update))


def handle_photo(update: telegram.Update, context: telegram.ext.CallbackContext):
    file = update.message.effective_attachment[2]
    logger.info("Photo received")
    file.get_file().download(os.path.join(Core.media, f"Photo_{str(datetime.datetime.now())}"))


def handle_file(update: telegram.Update, context: telegram.ext.CallbackContext):
    file = update.message.effective_attachment
    filename = file.file_name
    logger.info(f"File received: {filename}")
    file.get_file().download(os.path.join(Core.media, f"{filename}_{str(datetime.datetime.now())}"))


def unknown(update: telegram.Update, context: telegram.ext.CallbackContext):
    logger.critical(f"Unknown message received: {update.message}")
    Core.send_message(update, "Unknown message")


def handle_errors(update: telegram.Update, context: telegram.ext.CallbackContext):
    try:
        raise context.error
    except telegram.error.Conflict as e:
        logger.critical(f'Stopping bot. Other bot instance detected. Exception:\n{e}')
        os._exit(1)
    except telegram.error.NetworkError:
        pass
    except Exception as e:
        logger.error(f"Exception not handled in handle_errors: {e.__repr__()}\n{''.join(traceback.format_tb(e.__traceback__))}")


if __name__ == '__main__':
    home_directories = {'win32': os.path.join(pathlib.Path.home(), 'AppData', 'Local', 'pcbot'), 'linux': os.path.join(pathlib.Path.home(), '.local', 'share' 'pcbot')}
    config_files = {'win32': os.path.join(pathlib.Path.home(), 'AppData', 'Local', 'pcbot', 'config.json'), 'linux': os.path.join(pathlib.Path.home(), '.config', 'pcbot', 'config.json')}

    for config_file in [config_files[sys.platform]]:
        if os.path.exists(config_file):
            config = json.load(open(config_file))
            break
    else:
        config = {'bot_token': input('Insert bot token:\n'), 'chat_ids': [int(input('Insert chat id\n'))]}
        os.mkdir(os.path.split(config_files[sys.platform])[0])
        json.dump(config, open(config_files[sys.platform], 'w'), indent=4)

    Core.home = home_directories[sys.platform]
    Core.media = f'{Core.home}/Media'
    try:
        os.mkdir(Core.home)
        os.mkdir(Core.media)
    except FileExistsError:
        pass

    logs_filename = os.path.join(Core.home, 'logs.txt')
    open(logs_filename, 'a').close()
    with open(logs_filename, 'r+') as f:
        data = f.readlines()
        f.seek(0)
        f.writelines(data[-1000:])
        f.truncate()

    stds = StringIO()
    sys.stdout = interceptor.Interceptor([sys.stdout, stds, open(logs_filename, 'a', encoding='UTF-8')])
    sys.stderr = interceptor.Interceptor([sys.stderr, stds, open(logs_filename, 'a', encoding='UTF-8')])

    log_date_format = '%Y-%m-%d %H:%M:%S'
    log_format = f'%(asctime)s {sys.platform} {getpass.getuser()} %(levelname)s %(message)s'
    # noinspection PyTypeChecker
    logging.basicConfig(level=logging.INFO, datefmt=log_date_format, format=log_format, stream=sys.stdout)
    logger = logging.getLogger(__name__)
    # coloredlogs.install(stream=sys.stdout, level=logging.INFO, datefmt=log_date_format, fmt=log_format)    handlers=[logging.FileHandler('logs.txt', 'a', 'UTF-8'), logging.StreamHandler(sys.stdout)]

    debug = False

    import commands

    unsatisfied_req = set()
    for c in commands.commands:
        unsatisfied_req.update(check_requirements(c.requirements()))
    if unsatisfied_req:
        unsatisfied_req_str = "' '".join(unsatisfied_req)
        logger.warning(f"Unsatisfied commands requirement(s) detected: '{unsatisfied_req_str}'")

    cmds = name_to_command([Status(), DynamicCommands(), *commands.commands, Start(), Commands(), Logs(), Reload(), Stop()])

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
        logger.warning(f"Unsatisfied dynamic commands requirement(s) detected: '{unsatisfied_req_dyn_str}'")

    dynamiccmds = name_to_command(dynamiccmds)

    updater = Updater(token=config['bot_token'], use_context=True)
    dispatcher = updater.dispatcher
    Core.t_bot = telegram.Bot(token=config['bot_token'])

    Core.msg_queue = async_streamer.AsyncWriter()

    dispatcher.add_handler(CommandHandler(cmds, handle_commands))

    dispatcher.add_handler(MessageHandler(Filters.text, handle_text_dynamiccmds, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.document, handle_file, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.entity(telegram.MessageEntity.BOT_COMMAND), handle_commands, run_async=True))
    dispatcher.add_handler(MessageHandler(Filters.all, unknown, run_async=True))
    dispatcher.add_error_handler(handle_errors)

    block_until_connected()

    while True:
        try:
            updater.start_polling()
            break
        except telegram.error.NetworkError:
            block_until_connected()

    for c_id in config['chat_ids']:
        Start().execute(chat_id=c_id)
    logger.info(f"Logs file: {logs_filename}")
    logger.info("Bot started")

    while True:
        try:
            sleep(4)
            for c_id in config['chat_ids']:
                Core.t_bot.send_chat_action(chat_id=c_id, action=telegram.ChatAction.TYPING)
        except telegram.error.TimedOut:
            pass
        except (urllib3.exceptions.HTTPError, telegram.error.NetworkError):
            block_until_connected()
        except KeyboardInterrupt:
            import signal
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception as e:
            logger.critical(f"Exception not handled in main loop: {e.__repr__()}\n{''.join(traceback.format_tb(e.__traceback__))}")
