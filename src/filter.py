import telebot
from src.bot import bot
class IsAdmin(telebot.custom_filters.SimpleCustomFilter):
    # Class will check whether the user is admin or creator in group or not
    key='is_chat_admin'
    @staticmethod
    def check(message: telebot.types.Message):
        return bot.get_chat_member(message.chat.id,message.from_user.id).status in ['administrator','creator']
@bot.message_handler(text=['hi','hello'])
def text_filter(message):
    bot.send_message(message.chat.id, "Hi, {name}!".format(name=message.from_user.first_name))