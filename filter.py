from aiogram import types
from aiogram.dispatcher.filters import BoindFilter

class IsAdminFilter (BoindFilter):
    key = "is_admin"
    
    def _init_(self, is_admin):
        self.is_admin = is_admin
        
    async def check(self, messega: types.Message):
        member = await message.bot.get._chat_member(message.chat.id, message.from_user.id)
        return member.is_chat_admin()