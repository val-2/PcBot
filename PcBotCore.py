import logging

import telegram.ext
import queue
import threading
import time


class Command:
    def name(self):
        raise NotImplementedError

    def description(self):
        raise NotImplementedError

    def requirements(self):
        return []

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        raise NotImplementedError


class DynamicCommand:
    def name(self):
        raise NotImplementedError

    def description(self):
        raise NotImplementedError

    def requirements(self):
        return []

    def can_be_executed(self):
        return True

    def execute(self, update: telegram.Update, context: telegram.ext.CallbackContext):
        raise NotImplementedError


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
    return " ".join(update.message["text"].split(" ")[1:])


def send_message(update: telegram.Update or str, text, log_level=logging.INFO, parse_mode=None, disable_web_page_preview=None, disable_notification=False, reply_to_message_id=None, reply_markup=None, timeout=None, **kwargs):
    chat_id = update if isinstance(update, str) else update.message.chat_id
    bot = t_bot if isinstance(update, str) else update.message.bot
    while True:
        try:
            sent = bot.send_message(chat_id, text, parse_mode, disable_web_page_preview, disable_notification, reply_to_message_id, reply_markup, timeout, **kwargs)
            log_msg = f'Message to {chat_id}: "{text}"'
            logger.log(log_level, log_msg)
            return sent
        except telegram.error.NetworkError as e:
            if str(e) == "urllib3 HTTPError [SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC] decryption failed or bad record mac (_ssl.c:2508)":
                bot.send_message(f'Network error while sending message "{text}" to {chat_id}. Retrying...')
                logger.warning(f'Network error while sending message "{text}" to {chat_id}. Retrying...')
            else:
                raise


msg_queue = MessageQueue()
t_bot: telegram.Bot = None
home: str = None
media: str = None
logger = logging.getLogger(__name__)
