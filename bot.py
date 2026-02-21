import asyncio
from concurrent.futures import Executor
import logging
from pickle import TRUE
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from decorator import config

from filter import IsAdminFilter

#active filter

dp.filter_factory.bind(IsAdminFilter)

logging.basicConfig(level=logging.INFO)

# Получение токена из .env файла
API_TOKEN = config("BOT_TOKEN")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот на aiogram 3.")

# Обработчик любых текстовых сообщений
@dp.message()
async def echo_message(message: types.Message):
    await message.answer(f"Вы написали: {message.text}")

# Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)
    
#delete messages
@dp.message_handler()
async def filter_messages(message: types.Message ):
    if "Шлюха" in message.text:
        await message.delete()
    
#ban (admins)
@dp.message_handler(is_admin=true, commands=["ban"], commands_prefix=".")
async def cmd_ban(message: types.Message):
    if not message.reply_to_message:
        await message.reply("Ответте на сообщение чтоб отправить администратора бота в бан-на банановые острова")
        return
    
    await message.bot.delete_business_messages(chat_id=config.GROUP_ID, user_id=message.message_id)
    await message.bot.kick_chat_member(chat_id=config.GROUP_ID, user_id=message.reply_to_message.from_user.id)
    
    await message.reply_to_message.reply("администратор бота забанен/n На банановых островах")
#run long-polling
if __name__ == "_main_":
    Executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())


