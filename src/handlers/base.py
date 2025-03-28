from abc import ABC, abstractclassmethod

from src.constants import SETTINGS_START_MESSAGE, inline_keys
from src.utils.keyboard import create_keyboard


class BaseHandler(ABC):
    """
    Base class for all telebot handlers.
    """
    def __init__(self, stackbot, db):
        self.stackbot = stackbot
        self.db = db

    @abstractclassmethod
    def register(self):
        """
        Register telebot handlers.
        """

    def get_settings_keyboard(self):
        """
        Returns settings main menu keyboard.
        """
        muted_bot = self.stackbot.user.settings.get('muted_bot')
        if muted_bot:
            keys = [inline_keys.change_identity]
        else:
            keys = [inline_keys.change_identity]

        return create_keyboard(*keys, is_inline=True)

    def get_settings_text(self):
        """
        Returns settings text message.
        """
        text = SETTINGS_START_MESSAGE.format(
            first_name=self.stackbot.user.first_name,
            username=self.stackbot.user.username,
            identity=self.stackbot.user.identity,
            **self.stackbot.user.stats(),
        )
        return text