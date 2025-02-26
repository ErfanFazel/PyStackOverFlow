
from loguru import logger 
from src.constance import keyboards,keys,states
from src.filter import IsAdmin
from src.bot import bot
from telebot import custom_filters
import emoji
from src.db import db
class Bot:
    """
    Telegram template  bot
    """
    def __init__(self,telebot,mongodb):
        self.bot = telebot
        self.db = mongodb
        #add mustom filters
        self.bot.add_custom_filter(IsAdmin())
        self.bot.add_custom_filter(custom_filters.TextMatchFilter())
        self.bot.add_custom_filter(custom_filters.TextStartsFilter())

        # register handelers
        self.handlers()
        #run bot 
        logger.info('Bot is running')
        self.bot.infinity_polling()
    def handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start(message):
            """
            /start command handler.
            """
            self.bot.send_message(
                message.chat.id,
                f"Hey <strong>{message.chat.first_name}</strong>!",
                reply_markup=keyboards.main
            )

            self.db.users.update_one(
                {'chat.id': message.chat.id},
                {'$set': message.json},
                upsert=True
            )
            self.update_state(message.chat.id, states.main)

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
    def update_state(self, chat_id, state):
        """
        Update user state.
        """
        self.db.users.update_one(
            {'chat.id': chat_id},
            {'$set': {'state': state}}
        )
    
if __name__ == '__main__':
	logger.info("Bot started")
	bot = Bot(telebot=bot,mongodb=db)