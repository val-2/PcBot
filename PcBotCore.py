import logging
from telegram.ext.dispatcher import run_async
import async_streamer
import telegram


class Command:
    def name(self):
        raise NotImplementedError

    def description(self):
        raise NotImplementedError

    def execute(self, update, context):
        raise NotImplementedError


class DynamicCommand:
    def name(self):
        raise NotImplementedError

    def description(self):
        raise NotImplementedError

    @staticmethod
    def can_showup(self):
        return True

    def execute(self, update, context):
        raise NotImplementedError


def join_args(update):
    return " ".join(update.message["text"].split(" ")[1:])


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


t_bot: telegram.Bot = None
msg_queue: async_streamer.AsyncWriter = None
downloads_directory: str = None
