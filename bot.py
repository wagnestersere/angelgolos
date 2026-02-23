import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, LEFT, RESTRICTED

from config import BOT_TOKEN, GROUP_ID, ADMIN_IDS, LOG_CHANNEL_ID
from filters import IsAdminFilter, IsGroupFilter, IsPrivateFilter
from handlers import ModerationHandlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверка конфигурации
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")
if not GROUP_ID:
    raise ValueError("GROUP_ID not found in .env file")
if not ADMIN_IDS:
    logger.warning("ADMIN_IDS is empty - admin commands will not work")

logger.info(f"Bot started with config:")
logger.info(f"GROUP_ID: {GROUP_ID}")
logger.info(f"ADMIN_IDS: {ADMIN_IDS}")
logger.info(f"LOG_CHANNEL_ID: {LOG_CHANNEL_ID if LOG_CHANNEL_ID else 'Not set'}")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация обработчиков
moderation = ModerationHandlers(bot)

# ============== ОБРАБОТЧИКИ КОМАНД ==============

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 **Привет! Я бот для модерации групп.**\n\n"
        "**Доступные команды для администраторов:**\n"
        "`.ban` - заблокировать пользователя (ответом на сообщение)\n"
        "`.unban` - разблокировать пользователя\n"
        "`.mute [минуты]` - замутить пользователя\n"
        "`.unmute` - размутить пользователя\n"
        "`.clear [кол-во]` - очистить сообщения\n"
        "`.warn` - выдать предупреждение\n"
        "`.warns` - показать предупреждения пользователя\n\n"
        "**Для новых пользователей:**\n"
        "При входе в группу вам будет отправлен код подтверждения в личные сообщения.",
        parse_mode="Markdown"
    )

@dp.message(Command("ban", prefix="."))
async def cmd_ban(message: Message):
    """Бан пользователя"""
    if not await IsAdminFilter()(message):
        await message.reply("❌ У вас нет прав для этой команды")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение пользователя, которого хотите забанить")
        return
    
    reason = message.text.replace(".ban", "").strip() or "Нарушение правил"
    await moderation.ban_user(message, reason)

@dp.message(Command("unban", prefix="."))
async def cmd_unban(message: Message):
    """Разбан пользователя"""
    if not await IsAdminFilter()(message):
        await message.reply("❌ У вас нет прав для этой команды")
        return
    
    await moderation.unban_user(message)

@dp.message(Command("mute", prefix="."))
async def cmd_mute(message: Message):
    """Мут пользователя"""
    if not await IsAdminFilter()(message):
        await message.reply("❌ У вас нет прав для этой команды")
        return
    
    # Получаем длительность мута
    parts = message.text.split()
    minutes = 60  # по умолчанию 60 минут
    
    if len(parts) > 1:
        try:
            minutes = int(parts[1])
        except ValueError:
            await message.reply("❌ Укажите число минут (например: .mute 30)")
            return
    
    await moderation.mute_user(message, minutes)

@dp.message(Command("unmute", prefix="."))
async def cmd_unmute(message: Message):
    """Размут пользователя"""
    if not await IsAdminFilter()(message):
        await message.reply("❌ У вас нет прав для этой команды")
        return
    
    await moderation.unmute_user(message)

@dp.message(Command("clear", prefix="."))
async def cmd_clear(message: Message):
    """Очистка сообщений"""
    if not await IsAdminFilter()(message):
        await message.reply("❌ У вас нет прав для этой команды")
        return
    
    # Получаем количество сообщений для удаления
    parts = message.text.split()
    count = 10  # по умолчанию
    
    if len(parts) > 1:
        try:
            count = int(parts[1])
            if count > 100:
                count = 100
                await message.reply("⚠️ Максимальное количество для удаления - 100")
        except ValueError:
            await message.reply("❌ Укажите число сообщений (например: .clear 20)")
            return
    
    await moderation.clear_messages(message, count)

@dp.message(Command("warn", prefix="."))
async def cmd_warn(message: Message):
    """Выдача предупреждения"""
    if not await IsAdminFilter()(message):
        await message.reply("❌ У вас нет прав для этой команды")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение пользователя")
        return
    
    reason = message.text.replace(".warn", "").strip() or "Нарушение правил"
    await moderation.warn_user(message.reply_to_message, reason)

@dp.message(Command("warns", prefix="."))
async def cmd_warns(message: Message):
    """Просмотр предупреждений пользователя"""
    if not await IsAdminFilter()(message):
        await message.reply("❌ У вас нет прав для этой команды")
        return
    
    if not message.reply_to_message:
        user_id = message.from_user.id
        user = message.from_user
    else:
        user_id = message.reply_to_message.from_user.id
        user = message.reply_to_message.from_user
    
    warnings = moderation.user_warnings.get(user_id, [])
    
    if not warnings:
        await message.reply(f"✅ У пользователя {user.full_name} нет предупреждений")
        return
    
    text = f"⚠️ **Предупреждения пользователя {user.full_name}:**\n\n"
    for i, warn in enumerate(warnings, 1):
        text += f"{i}. {warn['reason']} ({warn['date'].strftime('%d.%m.%Y %H:%M')})\n"
    
    await message.reply(text, parse_mode="Markdown")

# ============== ОБРАБОТЧИКИ СОБЫТИЙ ==============

@dp.message(IsGroupFilter())
async def handle_group_messages(message: Message):
    """Обработка всех сообщений в группе"""
    # Пропускаем сообщения от ботов
    if message.from_user.is_bot:
        return
    
    # Проверка на запрещенные слова
    if await moderation.check_bad_words(message):
        await moderation.warn_user(message, "Использование запрещенных слов")
        return
    
    # Здесь можно добавить другие проверки

@dp.message(IsPrivateFilter())
async def handle_private_messages(message: Message):
    """Обработка личных сообщений (для капчи)"""
    # Пропускаем сообщения от ботов
    if message.from_user.is_bot:
        return
    
    # Проверяем, является ли это ответом на капчу
    await moderation.check_captcha(message)

@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=LEFT))
async def user_left(event: ChatMemberUpdated):
    """Пользователь покинул группу"""
    user = event.from_user
    logger.info(f"User {user.id} left the chat")
    
    # Очищаем данные пользователя
    if user.id in moderation.user_warnings:
        del moderation.user_warnings[user.id]
    if user.id in moderation.captcha_codes:
        del moderation.captcha_codes[user.id]

@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def user_joined(event: ChatMemberUpdated):
    """Новый пользователь в группе"""
    # Проверяем, что это действительно новый участник, а не обновление статуса
    if event.new_chat_member.user.id == event.from_user.id:
        logger.info(f"New user joined: {event.new_chat_member.user.full_name}")
        await moderation.generate_captcha(event)

# ============== ЗАПУСК БОТА ==============

async def main():
    """Главная функция запуска бота"""
    logger.info("Starting bot...")
    
    # Установка команд бота
    commands = [
        types.BotCommand(command="start", description="Запустить бота"),
    ]
    await bot.set_my_commands(commands)
    
    # Запуск поллинга
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())