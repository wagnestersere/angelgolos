from aiogram.filters import BaseFilter
from aiogram.types import Message
from config import ADMIN_IDS, GROUP_ID

class IsAdminFilter(BaseFilter):
    """Фильтр для проверки, является ли пользователь администратором"""
    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        
        # Проверка по списку ADMIN_IDS
        if message.from_user.id in ADMIN_IDS:
            return True
        
        # Проверка через API Telegram (админ ли в группе)
        if message.chat.id == GROUP_ID:
            try:
                chat_member = await message.bot.get_chat_member(
                    GROUP_ID, 
                    message.from_user.id
                )
                return chat_member.status in ['administrator', 'creator']
            except:
                return False
        return False

class IsGroupFilter(BaseFilter):
    """Фильтр для проверки, что сообщение из группы"""
    async def __call__(self, message: Message) -> bool:
        return message.chat.type in ['group', 'supergroup']

class IsPrivateFilter(BaseFilter):
    """Фильтр для проверки, что сообщение из лички"""
    async def __call__(self, message: Message) -> bool:
        return message.chat.type == 'private'