import asyncio
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.types import Message, ChatPermissions
from config import GROUP_ID, BAD_WORDS, WARN_LIMIT, LOG_CHANNEL_ID, CAPTCHA_ATTEMPTS

class ModerationHandlers:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.user_warnings = {}  # {user_id: [warnings]}
        self.captcha_codes = {}  # {user_id: {'code': str, 'attempts': int, 'chat_id': int}}
        self.muted_users = {}  # {user_id: {'until': datetime, 'admin': int}}
    
    async def log_action(self, action: str, user_id: int, username: str, details: str = ""):
        """Логирование действий модерации"""
        if LOG_CHANNEL_ID:
            log_text = f"""
📝 **Действие:** {action}
👤 **Пользователь:** {username} (ID: {user_id})
🕐 **Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📋 **Детали:** {details}
            """
            try:
                await self.bot.send_message(LOG_CHANNEL_ID, log_text)
            except Exception as e:
                print(f"Error logging action: {e}")
    
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
        try:
            await message.delete()
        except:
            pass
        
        # Отправляем предупреждение
        try:
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
                await self.ban_user_by_id(message.chat.id, user_id, "Превышение лимита предупреждений")
            
            # Автоудаление сообщения с предупреждением через 5 секунд
            await asyncio.sleep(5)
            try:
                await warn_msg.delete()
            except:
                pass
        except Exception as e:
            print(f"Error in warn_user: {e}")
    
    async def ban_user_by_id(self, chat_id: int, user_id: int, reason: str = "Нарушение правил"):
        """Бан пользователя по ID"""
        try:
            await self.bot.ban_chat_member(chat_id, user_id)
            
            # Очищаем данные пользователя
            if user_id in self.user_warnings:
                del self.user_warnings[user_id]
            if user_id in self.captcha_codes:
                del self.captcha_codes[user_id]
            
            return True
        except Exception as e:
            print(f"Error banning user {user_id}: {e}")
            return False
    
    async def ban_user(self, message: Message, reason: str = "Нарушение правил"):
        """Бан пользователя (через ответ на сообщение)"""
        if not message.reply_to_message:
            await message.reply("❌ Ответьте на сообщение пользователя")
            return
        
        user_to_ban = message.reply_to_message.from_user
        admin = message.from_user
        
        try:
            await self.bot.ban_chat_member(message.chat.id, user_to_ban.id)
            
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
            
            # Очищаем данные пользователя
            if user_to_ban.id in self.user_warnings:
                del self.user_warnings[user_to_ban.id]
            if user_to_ban.id in self.captcha_codes:
                del self.captcha_codes[user_to_ban.id]
                
        except Exception as e:
            await message.answer(f"❌ Ошибка при бане: {e}")
    
    async def unban_user(self, message: Message):
        """Разбан пользователя"""
        if not message.reply_to_message:
            await message.reply("❌ Ответьте на сообщение пользователя")
            return
        
        user_to_unban = message.reply_to_message.from_user
        admin = message.from_user
        
        try:
            await self.bot.unban_chat_member(message.chat.id, user_to_unban.id)
            
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
            await message.reply("❌ Ответьте на сообщение пользователя")
            return
        
        user_to_mute = message.reply_to_message.from_user
        admin = message.from_user
        
        try:
            until_date = datetime.now() + timedelta(minutes=minutes)
            
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
            
            await self.bot.restrict_chat_member(
                message.chat.id,
                user_to_mute.id,
                permissions,
                until_date=until_date
            )
            
            self.muted_users[user_to_mute.id] = {
                'until': until_date,
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
            await message.reply("❌ Ответьте на сообщение пользователя")
            return
        
        user_to_unmute = message.reply_to_message.from_user
        admin = message.from_user
        
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True
            )
            
            await self.bot.restrict_chat_member(
                message.chat.id,
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
        admin = message.from_user
        chat_id = message.chat.id
        
        try:
            # Получаем историю сообщений
            messages_to_delete = []
            async for msg in self.bot.get_chat_history(chat_id, limit=min(count, 100)):
                messages_to_delete.append(msg.message_id)
            
            if messages_to_delete:
                # Удаляем сообщения
                await self.bot.delete_messages(chat_id, messages_to_delete)
                
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
                try:
                    await result_msg.delete()
                except:
                    pass
            else:
                await message.answer("❌ Нет сообщений для удаления")
            
        except Exception as e:
            await message.answer(f"❌ Ошибка при очистке: {e}")
    
    async def generate_captcha(self, event):
        """Генерация капчи для нового пользователя"""
        user = event.new_chat_member.user
        chat_id = event.chat.id
        
        # Пропускаем ботов
        if user.is_bot:
            return
        
        # Генерируем случайный код
        captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Сохраняем данные капчи
        self.captcha_codes[user.id] = {
            'code': captcha,
            'attempts': 0,
            'chat_id': chat_id,
            'username': user.full_name
        }
        
        # Пробуем отправить капчу в личные сообщения
        try:
            await self.bot.send_message(
                user.id,
                f"🔐 **Подтверждение регистрации**\n\n"
                f"Вы присоединились к группе. Для подтверждения, что вы не бот, "
                f"введите следующий код:\n\n"
                f"`{captcha}`\n\n"
                f"У вас есть {CAPTCHA_ATTEMPTS} попыток.\n\n"
                f"Если вы не введете код, вы будете заблокированы.",
                parse_mode="Markdown"
            )
            
            # Отправляем сообщение в группу
            temp_msg = await self.bot.send_message(
                chat_id,
                f"👋 {user.full_name}, добро пожаловать!\n"
                f"Я отправил вам код подтверждения в личные сообщения. "
                f"Пожалуйста, проверьте и введите код здесь."
            )
            
            # Удаляем временное сообщение через 10 секунд
            await asyncio.sleep(10)
            try:
                await temp_msg.delete()
            except:
                pass
            
        except Exception as e:
            # Если не можем написать в личку (пользователь заблокировал бота)
            print(f"Cannot send captcha to user {user.id}: {e}")
            
            # Отправляем сообщение в группу и даем 5 минут на написание боту
            warn_msg = await self.bot.send_message(
                chat_id,
                f"⚠️ {user.full_name}, я не могу отправить вам сообщение.\n"
                f"Пожалуйста, напишите мне в личные сообщения (@{self.bot.username}) "
                f"в течение 5 минут, иначе вы будете заблокированы."
            )
            
            # Даем пользователю 5 минут на написание боту
            await asyncio.sleep(300)  # 5 минут
            
            # Проверяем, прошел ли пользователь капчу
            if user.id in self.captcha_codes:
                # Не прошел - блокируем
                await self.ban_user_by_id(chat_id, user.id, "Не прошел капчу")
                try:
                    await warn_msg.delete()
                except:
                    pass
    
    async def check_captcha(self, message: Message):
        """Проверка введенной капчи"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Проверяем, есть ли пользователь в ожидании капчи
        if user_id not in self.captcha_codes:
            # Возможно, пользователь пишет боту в личку, но капча для группы
            # Проверяем, есть ли капча для этого пользователя для какой-либо группы
            found = False
            for uid, data in list(self.captcha_codes.items()):
                if uid == user_id:
                    found = True
                    break
            
            if not found:
                return
        
        captcha_data = self.captcha_codes[user_id]
        
        if message.text.strip() == captcha_data['code']:
            # Капча верная
            await message.answer(
                "✅ **Капча пройдена успешно!**\n"
                "Добро пожаловать в группу!",
                parse_mode="Markdown"
            )
            
            # Отправляем сообщение в группу
            try:
                await self.bot.send_message(
                    captcha_data['chat_id'],
                    f"✅ Пользователь {captcha_data['username']} успешно прошел капчу!"
                )
            except:
                pass
            
            # Удаляем данные капчи
            del self.captcha_codes[user_id]
            
        else:
            # Неверная капча
            captcha_data['attempts'] += 1
            remaining = CAPTCHA_ATTEMPTS - captcha_data['attempts']
            
            if remaining <= 0:
                # Превышено количество попыток
                await message.answer(
                    "❌ **Превышено количество попыток.**\n"
                    "Вы не можете присоединиться к группе.",
                    parse_mode="Markdown"
                )
                
                # Баним пользователя в группе
                await self.ban_user_by_id(
                    captcha_data['chat_id'], 
                    user_id, 
                    "Превышено количество попыток ввода капчи"
                )
                
                # Удаляем данные капчи
                del self.captcha_codes[user_id]
            else:
                await message.answer(
                    f"❌ **Неверный код.**\n"
                    f"Осталось попыток: {remaining}",
                    parse_mode="Markdown"
                )