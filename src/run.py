
from loguru import logger 
from src.constance import keyboards
from src.filter import IsAdmin
from src.bot import bot 
import emoji
class Bot:
    """
    Telegram template  bot
    """
    def __init__(self,telebot):
        self.bot = telebot
        #add mustom filters
        self.bot.add_custom_filter(IsAdmin())
        # register handelers
        self.handlers()
        #run bot 
        logger.info('Bot is running')
        self.bot.infinity_polling()
    def handlers(self):
        @self.bot.message_handler(is_admin=True) 
        def admin_of_group(message):
            self.bot.send_message(message.chat_id,"You are the admin of this group")
        @self.bot.message_handler(func=lambda : True)
        def echo_all(self,message):
            #print(emoji.demojize(message.text))
            self.send_message(
                    message.chat.id, 
                    message.text,
                    reply_markup=keyboards.main,
                )
    def send_message(self,chat_id,text,reply_markup=None,emojize=True):
        """
        Send message to telegram bot.
        """
        if emojize:
            text = emoji.emojize(text,use_aliases=True)
        self.bot.send_message(chat_id,text,reply_markup=reply_markup)
if __name__ == '__main__':
	logger.info("Bot started")
	bot = Bot(telebot=bot)
	bot.run()