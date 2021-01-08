import logging
import async_streamer
import telegram.ext


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


t_bot: telegram.Bot = None
msg_queue: async_streamer.AsyncWriter = None
home: str = None
media: str = None
logger = logging.getLogger(__name__)
