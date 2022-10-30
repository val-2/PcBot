import abc
import logging
import pathlib
import queue
import threading
import time

import telegram.ext

try:
    import pystray
    GRAPHICAL_SESSION_SET = True
except ValueError:
    GRAPHICAL_SESSION_SET = False


class Command(abc.ABC):
    def __init__(self, pcbot_instance):
        self.pcbot = pcbot_instance

    @abc.abstractmethod
    def name(self):
        raise NotImplementedError

    @abc.abstractmethod
    def description(self):
        raise NotImplementedError

    def requirements(self):
        return ()

    @abc.abstractmethod
    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        raise NotImplementedError

    @staticmethod
    def can_be_used():
        return True


class DynamicCommand(abc.ABC):
    def __init__(self, pcbot_instance):
        self.pcbot = pcbot_instance

    @abc.abstractmethod
    def name(self):
        raise NotImplementedError

    @abc.abstractmethod
    def description(self):
        raise NotImplementedError

    def requirements(self):
        return ()

    @abc.abstractmethod
    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        raise NotImplementedError

    def can_be_executed(self):
        return True


class MessageQueue(queue.Queue):
    def __init__(self):
        super().__init__()
        self._items = []
        self.lock = threading.Lock()

    def get(self, timeout=None, reset_before_start=False, reset_after_return=True):  # if timeout is None, blocks
        if reset_before_start:
            self._items = []

        start = time.time()

        while True:
            try:
                self._items.append(super().get(block=len(self._items) == 0, timeout=self._get_timeout(timeout, start)))
                if timeout is None:
                    raise queue.Empty
            except queue.Empty:
                tmp_items = tuple(self._items)
                if reset_after_return:
                    self._items = []
                return tmp_items

    @staticmethod
    def _get_timeout(timeout, start):
        if not timeout:
            return timeout
        else:
            remaining = start + timeout - time.time()
            if remaining <= 0.0:
                raise queue.Empty
            return remaining


def join_args(update):
    return " ".join(update.message.text.split(" ")[1:])


def send_message(update: telegram.Update, text, log_level=logging.INFO, **kwargs):
    chat_id = update.message.chat_id
    sent = update.message.bot.send_message(chat_id, text, **kwargs)
    log_msg = f'Message to {chat_id}: "{text}"'
    logger.log(log_level, log_msg)
    return sent


def send_message_chat_id(chat_id, text, bot, log_level=logging.INFO, **kwargs):
    sent = bot.send_message(chat_id, text, **kwargs)
    log_msg = f'Message to {chat_id}: "{text}"'
    logger.log(log_level, log_msg)
    return sent


msg_queue = MessageQueue()
home: pathlib.Path = None
media: pathlib.Path = None
logger = logging.getLogger(__name__)
