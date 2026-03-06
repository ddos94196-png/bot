import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ChatJoinRequest, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "database.json"
MAIN_CHANNEL_ID = -1003627220056 

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Инициализация БД
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            for v in data["sponsors"].values():
                v["expires"] = datetime.fromisoformat(v["expires"])
            return data
    return {"sponsors": {}, "admins": [8638056962]} # Вставь сюда СВОЙ ID

def save_db(db):
    to_save = {
        "sponsors": {k: {"link": v["link"], "expires": v["expires"].isoformat()} for k, v in db["sponsors"].items()},
        "admins": db["admins"]
    }
    with open(DB_FILE, "w") as f:
        json.dump(to_save, f)

db = load_db()

# --- ЛОГИКА ---
async def remove_expired_sponsors():
    now = datetime.now()
    changed = False
    for ch_id in list(db["sponsors"].keys()):
        if now >= db["sponsors"][ch_id]["expires"]:
            del db["sponsors"][ch_id]
            changed = True
    if changed:
        save_db(db)

@dp.chat_join_request()
async def join_request(request: ChatJoinRequest):
    builder = InlineKeyboardBuilder()
    for ch_id, data in db["sponsors"].items():
        builder.row(InlineKeyboardButton(text="Подписаться на канал", url=data["link"]))
    builder.row(InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check"))
    
    await bot.send_message(
        chat_id=request.from_user.id,
        text="Привет! Чтобы вступить в канал, подпишись на спонсоров ниже:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "check")
async def check_sub(call: types.CallbackQuery):
    for ch_id in db["sponsors"].keys():
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=call.from_user.id)
            if member.status in ['left', 'kicked']:
                return await call.answer("Ты подписался не на все каналы!", show_alert=True)
        except Exception:
            return await call.answer("Ошибка доступа к каналу. Админ, проверь права!", show_alert=True)
    
    await bot.approve_chat_join_request(chat_id=MAIN_CHANNEL_ID, user_id=call.from_user.id)
    await call.message.answer("✅ Заявка одобрена!")

@dp.message(Command("add"))
async def add_sponsor(message: types.Message):
    if message.from_user.id not in db["admins"]: return
    args = message.text.split()
    if len(args) < 4: return await message.answer("Формат: /add <channel_id> <link> <hours>")
    db["sponsors"][args[1]] = {"link": args[2], "expires": datetime.now() + timedelta(hours=int(args[3]))}
    save_db(db)
    await message.answer("✅ Спонсор добавлен.")

@dp.message(Command("add_admin"))
async def add_admin(message: types.Message):
    if message.from_user.id != db["admins"][0]: return # Только главный админ может добавлять других
    if len(message.text.split()) > 1:
        new_id = int(message.text.split()[1])
        db["admins"].append(new_id)
        save_db(db)
        await message.answer(f"✅ Администратор {new_id} добавлен.")

async def main():
    scheduler.add_job(remove_expired_sponsors, 'interval', minutes=1)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
