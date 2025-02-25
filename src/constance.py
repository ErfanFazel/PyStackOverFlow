from types import SimpleNamespace
from telebot import types
import emoji 
def create_keyboard(*keys,row_width=2,resize_keyboard=True):
    markup = types.ReplyKeyboardMarkup(
        row_width=row_width,
        resize_keyboard=resize_keyboard,
    )
    keys = map(emoji.emojize,keys)
    buttons = map(types.KeyboardButton,keys)
    markup.add(*buttons)
    return markup
keys = SimpleNamespace(
    random_connect=":bust_in_silhouette: Random Connect",
    settings=":gear: Settings",
)



keyboards = SimpleNamespace(
    main=create_keyboard(keys.random_connect,keys.settings)
)