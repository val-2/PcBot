#!/home/valerio/venv/bin/python

import datetime
import getpass
import logging
import os.path
import socket
import sys
from importlib import reload
from io import StringIO, BytesIO
from time import sleep

import telegram
import urllib3
from async_streamer import *
from interceptor import *
from telegram.ext import Updater, Filters, CommandHandler, MessageHandler

import PcBotCore as Core
import commands
import config

try:
    import dynamiccommands
except ModuleNotFoundError:
    pass


def name_to_command(c):
    d = {}
    for i in c:
        d[i.name()] = i
    return d


def block_until_connected():
    logged = False
    while True:
        try:
            socket.setdefaulttimeout(10)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
            break
        except socket.error:
            if not logged:
                logging.warning("Connection lost")
                logged = True
            sleep(3)
    logging.info("Connection established")


# def command_std(update, args, shell=False, confirmation='🆗\n'):
#     output = check_output(args, shell, stderr=STDOUT, text=True)
#     logging.debug(f"Bash command executed: {args if shell else ' '.join(args)}")
#     logging.debug(f"Output: {output}")
#     output += confirmation
#     if output:
#         core.send_message(update, output)
#     return output


# def restart(update: telegram.Update, context: telegram.ext.CallbackContext):
#     _restart()
#     updater.stop()
#
#
# @run_async
# def _restart():
#     Popen([sys.executable] + sys.argv).wait()


class Start(Core.Command):
    def name(self):
        return 'start'

    def description(self):
        return 'Send initial message'

    @Core.run_async
    def execute(self, update=None, context=None, chat_id=None):
        oses = {'linux': 'Linux', 'win32': 'Windows', 'darwin': 'MacOS'}
        op_sys = oses.get(sys.platform, 'unknown OS')
        Core.t_bot.send_message(chat_id=update.message.chat_id if update else chat_id, text=f"{getpass.getuser()} started pc on {op_sys}", disable_notification=True)


class Status(Core.Command):
    def name(self):
        return 'status'

    def description(self):
        return 'Send bot status'

    @Core.run_async
    def execute(self, update, context):
        Core.send_message(update, f"Bot started\nplatform={sys.platform}\nuser={getpass.getuser()}")


class Commands(Core.Command):
    def name(self):
        return 'commands'

    def description(self):
        return 'Get all commands and respective descriptions for BotFather'

    @Core.run_async
    def execute(self, update, context):
        commands_list = [f'{i.name()} - {i.description()}' for i in cmds.values()]
        Core.send_message(update, "\n".join(commands_list))


class Logs(Core.Command):
    def name(self):
        return 'logs'

    def description(self):
        return 'Get stout and stderr'

    @Core.run_async
    def execute(self, update, context):
        Core.t_bot.send_document(update.message.chat_id, document=BytesIO(sys.stdout.get_std(1).getvalue().encode()), filename='logs.txt')


class Reload(Core.Command):
    def name(self):
        return 'reload'

    def description(self):
        return 'Reload all commands'

    @Core.run_async
    def execute(self, update, context):
        reload(commands)
        reload(dynamiccommands)
        Core.send_message(update, "Commands reloaded")


class Stop(Core.Command):
    def name(self):
        return 'stop'

    def description(self):
        return 'Stop bot execution'

    @Core.run_async
    def execute(self, update, context):
        logging.info('Stopping bot by user command')
        Core.send_message(update, 'Stopping bot...')
        os._exit(1)


class DynamicCommands(Core.Command):
    def name(self):
        return 'dynamiccommands'

    def description(self):
        return 'Get all dynamic commands and respective descriptions'

    @Core.run_async
    def execute(self, update, context):
        try:
            Core.send_message(update, '\n'.join([f'/{i.name()} - {i.description()}' for i in dynamiccmds.values() if i.can_showup()]))
        except telegram.error.BadRequest:
            Core.send_message(update, 'No dynamic command available')


# Handles

def handle_commands(update: telegram.Update, context: telegram.ext.CallbackContext):
    message = update.message.text
    chat_id = update.message.chat_id
    if chat_id == config.chat_id:
        logging.info(f"Command received: {message}")
        command_str = message.split(" ")[0].lstrip("/")
        try:
            if command_str in cmds:
                cmds[command_str].execute(update, context)
            else:
                logging.warning(f"Command {message} doesn't exist")
                Core.send_message(update, f"Command {message} doesn't exist")
        except Exception as e:
            if not debug:
                logging.error(f"Calling {command_str} threw {e}")
                Core.send_message(update, f"Calling {command_str} threw {e}")
            else:
                raise
    else:
        logging.critical(update)
        Core.send_message(update, "SOS\n" + str(update))


def handle_text_dynamiccmds(update: telegram.Update, context: telegram.ext.CallbackContext):
    message = update.message.text
    chat_id = update.message.chat_id
    if chat_id == config.chat_id:
        if (command_str := message.split(" ")[0].lstrip("/")) in dynamiccmds:
            logging.info(f"Dynamic command received: {message}")
            if not dynamiccmds[command_str].can_showup():
                Core.send_message(update, f"The dynamic command {command_str} cannot be executed")
            else:
                try:
                    dynamiccmds[command_str].execute(update, context)
                except Exception as e:
                    if not debug:
                        logging.error(update, f"Calling {command_str} threw {e}")
                        Core.send_message(update, f"Calling {command_str} threw {e}")
                    else:
                        raise
        else:
            logging.info(f"Message received: {message}")
            Core.queue.put(message)
    else:
        logging.critical(update)
        Core.send_message(update, "SOS\n" + str(update))


def handle_photo(update: telegram.Update, context: telegram.ext.CallbackContext):
    file = update.message.effective_attachment[2]
    logging.info("Photo received")
    file.get_file().download(os.path.join(Core.downloads_directory, f"Photo_{str(datetime.datetime.now())}"))


def handle_file(update: telegram.Update, context: telegram.ext.CallbackContext):
    file = update.message.effective_attachment
    filename = file.file_name
    logging.info(f"File received: {filename}")
    file.get_file().download(os.path.join(Core.downloads_directory, f"{filename}_{str(datetime.datetime.now())}"))


def unknown(update: telegram.Update, context: telegram.ext.CallbackContext):
    logging.critical(f"Unknown message received: {update.message}")
    Core.send_message(update, "Unknown message")


def handle_errors(update: telegram.Update, context: telegram.ext.CallbackContext):
    try:
        raise context.error
    except telegram.error.Conflict as e:
        logging.critical(f'Stopping bot. Other bot instance detected. Exception:\n{e}')
        os._exit(1)
    except telegram.error.NetworkError:
        pass


if __name__ == '__main__':
    logs_exception = ''
    try:
        with open('logs.txt', 'r') as f:
            lines = f.readlines()[-1000:]
        with open('logs.txt', 'w') as f:
            f.writelines(lines)
    except FileNotFoundError:
        pass
    except Exception as e:
        logs_exception = e

    stds = StringIO()
    sys.stdout = Interceptor([sys.stdout, stds, open('logs.txt', 'a', encoding='UTF-8')])
    sys.stderr = Interceptor([sys.stderr, stds, open('logs.txt', 'a', encoding='UTF-8')])

    log_date_format = '%Y-%m-%d %H:%M:%S'
    log_format = f'%(asctime)s {sys.platform} {getpass.getuser()} %(levelname)s %(message)s'
    logging.basicConfig(level=logging.INFO, datefmt=log_date_format, format=log_format, stream=sys.stdout)
    # coloredlogs.install(stream=sys.stdout, level=logging.INFO, datefmt=log_date_format, fmt=log_format)    handlers=[logging.FileHandler('logs.txt', 'a', 'UTF-8'), logging.StreamHandler(sys.stdout)]

    debug = False

    cmds = name_to_command([Status(), DynamicCommands(), *commands.commands, Start(), Commands(), Logs(), Reload()])

    try:
        dynamiccmds = name_to_command(dynamiccommands.dynamiccmds)
    except NameError:
        dynamiccmds = {}

    if sys.platform == "win32":
        import winreg
        sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        downloads_guid = '{374DE290-123F-4565-9164-39C4925E467B}'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
            Core.downloads_directory = winreg.QueryValueEx(key, downloads_guid)[0]
    elif sys.platform == "linux":
        from gi.repository import GLib
        Core.downloads_directory = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
    else:
        raise NotImplementedError

    updater = Updater(token=config.bot_token, use_context=True,)
    dispatcher = updater.dispatcher
    Core.t_bot = telegram.Bot(token=config.bot_token)

    Core.queue = AsyncWriter()

    dispatcher.add_handler(CommandHandler(cmds, handle_commands))

    dispatcher.add_handler(MessageHandler(Filters.text, handle_text_dynamiccmds))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo))
    dispatcher.add_handler(MessageHandler(Filters.document, handle_file))
    dispatcher.add_handler(MessageHandler(Filters.entity(telegram.MessageEntity.BOT_COMMAND), handle_commands))
    dispatcher.add_handler(MessageHandler(Filters.all, unknown))
    dispatcher.add_error_handler(handle_errors)

    while True:
        try:
            updater.start_polling()
            break
        except telegram.error.NetworkError:
            block_until_connected()

    if logs_exception:
        Core.t_bot.send_message(chat_id=config.chat_id, text=f"Exception while handling logs:\n{logs_exception}")

    Start().execute(chat_id=config.chat_id)
    logging.info("Bot started")

    while True:
        try:
            sleep(4)
            Core.t_bot.send_chat_action(chat_id=config.chat_id, action=telegram.ChatAction.TYPING)
        except telegram.error.TimedOut:
            pass
        except KeyboardInterrupt:
            os._exit(1)
        except (urllib3.exceptions.HTTPError, telegram.error.NetworkError):
            block_until_connected()
        except Exception as e:
            logging.error(f'Exception not handled:\n')
            raise e
