 import os
import asyncio
import time
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import InputPeerChannel, InputReportReasonSpam, InputReportReasonViolence, InputReportReasonPornography, InputReportReasonChildAbuse, InputReportReasonIllegalDrugs, InputReportReasonPersonalDetails, InputReportReasonOther
from datetime import datetime, timedelta
from telethon.errors import SessionPasswordNeededError, AuthKeyUnregisteredError, AuthKeyDuplicatedError
import random

API_ID = 22145591
API_HASH = 'a158695b95d3c634ee71b0c54f93bb5c'
BOT_TOKEN = '7981123509:AAHJpebJb0FIc5K3ZUAD7xA0emjBfzKF7D0'
ADMIN_ID = 263834296
DB_PATH = 'subscriptions.db'
LOG_CHAT_ID = -1002344459923

reasons = {
    'spam': InputReportReasonSpam(),
    'violence': InputReportReasonViolence(),
    'pornography': InputReportReasonPornography(),
    'child_abuse': InputReportReasonChildAbuse(),
    'illegal_drugs': InputReportReasonIllegalDrugs(),
    'personal_details': InputReportReasonPersonalDetails(),
    'other': InputReportReasonOther()
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

reporting_time = {}
reporting = {}

def log_to_console_and_file(message: str):
    print(message)
    with open('attack_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"{datetime.utcnow()} - {message}\n")

async def check_subscription(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT expiration_date FROM subscriptions WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        if row:
            expiration_date = datetime.fromisoformat(row[0])
            return expiration_date > datetime.utcnow()
    return False

async def add_subscription(user_id: int, days: int):
    expiration_date = datetime.utcnow() + timedelta(days=days)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM subscriptions WHERE user_id = ?', (user_id,))
        existing = await cursor.fetchone()
        if existing:
            await db.execute('UPDATE subscriptions SET expiration_date = ? WHERE user_id = ?',
                             (expiration_date.isoformat(), user_id))
        else:
            await db.execute('INSERT INTO subscriptions (user_id, expiration_date) VALUES (?, ?)',
                             (user_id, expiration_date.isoformat()))
        await db.commit()

async def init_db():
    if not os.path.exists(DB_PATH):
        log_to_console_and_file("База данных не найдена. Создаю базу данных...")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
                                user_id INTEGER PRIMARY KEY,
                                expiration_date TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
                                user_id INTEGER PRIMARY KEY,
                                last_report_time TEXT)''')
        await db.commit()

async def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("🚨 Репорт"))
    keyboard.add(KeyboardButton("👤 Профиль"))
    keyboard.add(KeyboardButton("ℹ️ Информация"))
    return keyboard

async def report_message(client, peer, msg_id, reason, desc):
    try:
        start_time = time.time()
        await client(ReportRequest(peer, id=[msg_id], reason=reason, message=desc))
        end_time = time.time()
        log_to_console_and_file(f"Жалоба отправлена для сообщения ID {msg_id}. Время: {end_time - start_time:.2f} сек.")
    except Exception as e:
        log_to_console_and_file(f'Не удалось отправить жалобу: {e}')

async def process_message_link(client, message_link, reason, desc):
    try:
        message_link_parts = message_link.split('/')
        channel_username = message_link_parts[3]
        message_id = int(message_link_parts[-1])

        channel = await client.get_entity(channel_username)
        message = await client.get_messages(channel, ids=message_id)

        report_message_text = f"Начал атаку\nТаргет - {message_link}"

        peer = InputPeerChannel(channel.id, channel.access_hash)
        await report_message(client, peer, message_id, reason, report_message_text)

    except Exception as e:
        log_to_console_and_file(f"Ошибка при обработке ссылки: {e}")

def load_report_descriptions(reason: str) -> list:
    try:
        with open('text.txt', 'r', encoding='utf-8') as file:
            lines = file.readlines()
            descriptions = [line.strip().split(' - ', 1)[1] for line in lines if line.lower().startswith(reason.lower())]
            return descriptions
    except Exception as e:
        log_to_console_and_file(f"Ошибка при загрузке описаний из файла: {e}")
        return []

def get_random_report_description(reason: str) -> str:
    descriptions = load_report_descriptions(reason)
    if descriptions:
        return random.choice(descriptions)
    else:
        return "Не удалось найти описание для этой причины."

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Добро пожаловать. Меню приложено ниже", reply_markup=await get_main_keyboard())

@dp.message_handler(lambda message: message.text == "🚨 Репорт")
async def report(message: types.Message):
    await message.reply(
        "Используйте команду /report <ссылка на сообщение> <причина (spam, violence, etc.)>\n\n"
        "Пример: /report https://t.me/DoxChat/123 spam",
        reply_markup=await get_main_keyboard()
    )

@dp.message_handler(lambda message: message.text == "👤 Профиль")
async def profile(message: types.Message):
    user_id = message.from_user.id
    if await check_subscription(user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute('SELECT expiration_date FROM subscriptions WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            expiration_date = datetime.fromisoformat(row[0])
            remaining_days = (expiration_date - datetime.utcnow()).days
            if remaining_days > 0:
                await message.reply(f"Ваш ID: {user_id}\nОсталось дней подписки: {remaining_days} дней", reply_markup=await get_main_keyboard())
            else:
                await message.reply(f"Ваш ID: {user_id}\nВаша подписка истекла.", reply_markup=await get_main_keyboard())
    else:
        await message.reply("У вас нет активной подписки.", reply_markup=await get_main_keyboard())

@dp.message_handler(lambda message: message.text == "ℹ️ Информация")
async def information(message: types.Message):
    await message.reply(
        "Цены на подписку:\n"
        "1 день - 2$\n"
        "7 дней - 5$\n"
        "31 день - 10$\n"
        "1 год - 100$\n\n"
        "@watru\n\n"
        "@BotRepWork - Работы бота",
        reply_markup=await get_main_keyboard()
    )

@dp.message_handler(commands=['givesub'])
async def give_subscription(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выдачи подписки.")
        return

    args = message.get_args().split()
    if len(args) != 2:
        await message.reply("Используйте: /givesub <user_id> <days>")
        return

    try:
        user_id = int(args[0])
        days = int(args[1])
        await add_subscription(user_id, days)
        await message.reply(f"Подписка на {days} дней выдана пользователю {user_id}.")
    except ValueError:
        await message.reply("Пожалуйста, укажите правильные значения для user_id и days.")

@dp.message_handler(commands=['report'])
async def report_command(message: types.Message):
    user_id = message.from_user.id
    now = datetime.utcnow()

    if user_id in reporting_time:
        last_report_time = reporting_time[user_id]
        cooldown = timedelta(minutes=8)
        if now - last_report_time < cooldown:
            remaining_time = cooldown - (now - last_report_time)
            await message.reply(f"Пожалуйста, подождите {remaining_time.seconds // 60} минут и {remaining_time.seconds % 60} секунд до следующей жалобы.")
            return

    if not await check_subscription(user_id):
        await message.reply("❌")
        return

    args = message.get_args().split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Используй: /report <ссылка на сообщение> <причина (spam, violence, etc.)>")
        return

    message_link = args[0]
    reason_str = args[1].lower()

    if reason_str not in reasons:
        await message.reply("Некорректная причина. Доступные причины: spam, violence, pornography, child_abuse, illegal_drugs, personal_details, other.")
        return

    if message_link.startswith("https://t.me/c/"):
        await message.reply("Снос невозможен. Чат приватный")
        return

    reason = reasons[reason_str]
    desc = get_random_report_description(reason_str)  

    status_message = f"<b>🧨 Запущена атака!</b>\n<b>Таргет:</b> <a href='{message_link}'>Ссылка на сообщение</a>"
    proc_del = await bot.send_message(chat_id=user_id, text="⚙️")

    successful_reports = 0
    reporting[user_id] = True
    method_used = reason_str.capitalize()

    log_to_console_and_file("Ищем сессии в папке 'sessions/'...")

    session_files = os.listdir('sessions/')
    log_to_console_and_file(f"Найдено сессий: {len(session_files)}")

    for account in session_files:
        if not account.endswith('.session'):
            continue

        log_to_console_and_file(f"Отправка жалобы с аккаунта {account}...")

        client = TelegramClient(f"sessions/{account}", API_ID, API_HASH, auto_reconnect=True)
        try:
            await client.connect()
            log_to_console_and_file(f"Успешно подключились с аккаунта {account}")

            for _ in range(5):
                if not reporting.get(user_id, False):
                    await message.reply("Отправка жалоб остановлена.")
                    return

                try:
                    start_time = time.time()
                    await process_message_link(client, message_link.strip(), reason, desc)  # Функция отправки жалобы
                    end_time = time.time()
                    log_to_console_and_file(f"Жалоба отправлена с аккаунта {account}. Время ожидания: {end_time - start_time:.2f} сек.")
                    successful_reports += 1

                except (AuthKeyUnregisteredError, AuthKeyDuplicatedError) as e:
                    log_to_console_and_file(f"Сессия невалидна или используется с другого IP-адреса: {e}. Пропускаем этот аккаунт.")
                    break

                except Exception as e:
                    log_to_console_and_file(f"Ошибка при обработке сообщения с аккаунта {account}: {e}")

        except Exception as e:
            log_to_console_and_file(f'Ошибка с аккаунтом {account}: {e}')
        finally:
            await client.disconnect()

    reporting_time[user_id] = datetime.utcnow()
    await proc_del.delete()

    response_message = f"""
    <b>Жалобы отправлены!</b>\n
    <b>Таргет:</b> <a href='{message_link}'>Ссылка на сообщение</a>\n
    <b>Метод:</b> <code>{method_used}</code>\n
    <b>Отправлено жалоб:</b> <code>{successful_reports}</code>
    """
    await bot.send_message(chat_id=user_id, text="✅")
    await bot.send_message(chat_id=user_id, text=response_message, parse_mode='HTML')

    reporting[user_id] = False

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    executor.start_polling(dp, skip_updates=True)
