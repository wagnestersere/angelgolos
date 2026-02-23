import asyncio
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, types
from aiogram.types import Message, ChatPermissions
from aiogram.filters import Command
from config import CAPTCHA_ATTEMPTS, GROUP_ID, ADMIN_IDS, BAD_WORDS, WARN_LIMIT, LOG_CHANNEL_ID

# Хранилище данных (в реальном проекте лучше использовать Redis или БД)
user_warnings = {}
captcha_codes = {}
muted_users = {}

class ModerationHandlers:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.user_warnings = {}
        self.captcha_codes = {}
        self.muted_users = {}
    
    async def log_action(self, action: str, user_id: int, username: str, details: str = ""):
        """Логирование действий модерации"""
        if LOG_CHANNEL_ID:
            log_text = f"""
📝 **Действие:** {action}
👤 **Пользователь:** {username} (ID: {user_id})
🕐 **Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📋 **Детали:** {details}
            """
            await self.bot.send_message(LOG_CHANNEL_ID, log_text)
    
    async def check_bad_words(self, message: Message) -> bool:
        """Проверка сообщения на наличие запрещенных слов"""
        if not message.text:
            return False
        
        text_lower = message.text.lower()
        for word in BAD_WORDS:
            if word in text_lower:
                return True
        return False
    
    async def warn_user(self, message: Message, reason: str):
        """Выдача предупреждения пользователю"""
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        
        if user_id not in self.user_warnings:
            self.user_warnings[user_id] = []
        
        self.user_warnings[user_id].append({
            'reason': reason,
            'date': datetime.now(),
            'message_id': message.message_id
        })
        
        warnings_count = len(self.user_warnings[user_id])
        
        # Удаляем сообщение с нарушением
        await message.delete()
        
        # Отправляем предупреждение
        warn_msg = await message.answer(
            f"⚠️ {username}, ваше сообщение было удалено.\n"
            f"Причина: {reason}\n"
            f"Предупреждение: {warnings_count}/{WARN_LIMIT}"
        )
        
        await self.log_action(
            "Предупреждение",
            user_id,
            username,
            f"Причина: {reason}, предупреждение {warnings_count}/{WARN_LIMIT}"
        )
        
        # Если превышен лимит предупреждений - бан
        if warnings_count >= WARN_LIMIT:
            await self.ban_user(message, "Превышение лимита предупреждений")
        
        # Автоудаление сообщения с предупреждением через 5 секунд
        await asyncio.sleep(5)
        await warn_msg.delete()
    
    async def ban_user(self, message: Message, reason: str = "Нарушение правил"):
        """Бан пользователя"""
        if not message.reply_to_message:
            return
        
        user_to_ban = message.reply_to_message.from_user
        admin = message.from_user
        
        try:
            await message.bot.ban_chat_member(
                GROUP_ID,
                user_to_ban.id
            )
            
            await message.answer(
                f"🔨 Пользователь {user_to_ban.full_name} забанен.\n"
                f"Причина: {reason}\n"
                f"Модератор: {admin.full_name}"
            )
            
            await self.log_action(
                "Бан",
                user_to_ban.id,
                user_to_ban.full_name,
                f"Причина: {reason}, модератор: {admin.full_name}"
            )
            
        except Exception as e:
            await message.answer(f"❌ Ошибка при бане: {e}")
    
    async def unban_user(self, message: Message):
        """Разбан пользователя"""
        if not message.reply_to_message:
            return
        
        user_to_unban = message.reply_to_message.from_user
        admin = message.from_user
        
        try:
            await message.bot.unban_chat_member(
                GROUP_ID,
                user_to_unban.id
            )
            
            await message.answer(
                f"✅ Пользователь {user_to_unban.full_name} разбанен.\n"
                f"Модератор: {admin.full_name}"
            )
            
            await self.log_action(
                "Разбан",
                user_to_unban.id,
                user_to_unban.full_name,
                f"Модератор: {admin.full_name}"
            )
            
        except Exception as e:
            await message.answer(f"❌ Ошибка при разбане: {e}")
    
    async def mute_user(self, message: Message, minutes: int = 60):
        """Мут пользователя (запрет на отправку сообщений)"""
        if not message.reply_to_message:
            return
        
        user_to_mute = message.reply_to_message.from_user
        admin = message.from_user
        
        try:
            # Запрет на отправку сообщений
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            
            await message.bot.restrict_chat_member(
                GROUP_ID,
                user_to_mute.id,
                permissions,
                until_date=datetime.now() + timedelta(minutes=minutes)
            )
            
            self.muted_users[user_to_mute.id] = {
                'until': datetime.now() + timedelta(minutes=minutes),
                'admin': admin.id
            }
            
            await message.answer(
                f"🔇 Пользователь {user_to_mute.full_name} замучен на {minutes} минут.\n"
                f"Модератор: {admin.full_name}"
            )
            
            await self.log_action(
                "Мут",
                user_to_mute.id,
                user_to_mute.full_name,
                f"Длительность: {minutes} мин, модератор: {admin.full_name}"
            )
            
        except Exception as e:
            await message.answer(f"❌ Ошибка при муте: {e}")
    
    async def unmute_user(self, message: Message):
        """Снятие мута с пользователя"""
        if not message.reply_to_message:
            return
        
        user_to_unmute = message.reply_to_message.from_user
        admin = message.from_user
        
        try:
            # Полные права
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            
            await message.bot.restrict_chat_member(
                GROUP_ID,
                user_to_unmute.id,
                permissions
            )
            
            if user_to_unmute.id in self.muted_users:
                del self.muted_users[user_to_unmute.id]
            
            await message.answer(
                f"🔊 Пользователь {user_to_unmute.full_name} размучен.\n"
                f"Модератор: {admin.full_name}"
            )
            
            await self.log_action(
                "Размут",
                user_to_unmute.id,
                user_to_unmute.full_name,
                f"Модератор: {admin.full_name}"
            )
            
        except Exception as e:
            await message.answer(f"❌ Ошибка при размуте: {e}")
    
    async def clear_messages(self, message: Message, count: int = 10):
        """Очистка последних сообщений"""
        if not message.reply_to_message:
            return
        
        admin = message.from_user
        chat_id = message.chat.id
        
        try:
            messages_to_delete = []
            
            # Получаем историю сообщений
            async for msg in message.bot.get_chat_history(chat_id, limit=count):
                messages_to_delete.append(msg.message_id)
            
            # Удаляем сообщения
            await message.bot.delete_messages(chat_id, messages_to_delete)
            
            result_msg = await message.answer(
                f"🧹 Удалено {len(messages_to_delete)} сообщений.\n"
                f"Модератор: {admin.full_name}"
            )
            
            await self.log_action(
                "Очистка",
                admin.id,
                admin.full_name,
                f"Удалено сообщений: {len(messages_to_delete)}"
            )
            
            # Автоудаление сообщения о результате
            await asyncio.sleep(5)
            await result_msg.delete()
            
        except Exception as e:
            await message.answer(f"❌ Ошибка при очистке: {e}")
    
    async def generate_captcha(self, message: Message):
        """Генерация капчи для нового пользователя"""
        user_id = message.from_user.id
        
        # Генерируем случайный код
        captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        self.captcha_codes[user_id] = {
            'code': captcha,
            'attempts': 0,
            'message_id': message.message_id
        }
        
        # Отправляем капчу в личку пользователю
        try:
            await message.bot.send_message(
                user_id,
                f"🔐 Для подтверждения регистрации в группе, введите код:\n"
                f"`{captcha}`\n\n"
                f"У вас {CAPTCHA_ATTEMPTS} попыток.",
                parse_mode="Markdown"
            )
            
            # Удаляем сообщение о входе в группу
            await asyncio.sleep(1)
            await message.delete()
            
        except Exception:
            # Если не можем написать в личку - кикаем
            await message.bot.ban_chat_member(GROUP_ID, user_id)
            await message.bot.unban_chat_member(GROUP_ID, user_id)
    
    async def check_captcha(self, message: Message):
        """Проверка введенной капчи"""
        user_id = message.from_user.id
        
        if user_id not in self.captcha_codes:
            return False
        
        captcha_data = self.captcha_codes[user_id]
        
        if message.text == captcha_data['code']:
            # Капча верная
            del self.captcha_codes[user_id]
            await message.answer("✅ Капча пройдена! Добро пожаловать в группу!")
            return True
        else:
            # Неверная капча
            captcha_data['attempts'] += 1
            
            if captcha_data['attempts'] >= CAPTCHA_ATTEMPTS:
                # Превышено попыток - бан
                await message.answer("❌ Превышено количество попыток. Доступ запрещен.")
                await message.bot.ban_chat_member(GROUP_ID, user_id)
                del self.captcha_codes[user_id]
            else:
                await message.answer(
                    f"❌ Неверный код. Осталось попыток: "
                    f"{CAPTCHA_ATTEMPTS - captcha_data['attempts']}"
                )
            
            return False