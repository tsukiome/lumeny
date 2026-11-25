import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp,
                           Message, WebAppInfo)
from aiohttp import web

from dota import db, dota_router, notifier_loop
from server import make_app

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["BOT_TOKEN"]
BASE_URL = (os.getenv("BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")

main_router = Router()


async def app_keyboard(user_id: int):
    if not BASE_URL:
        return None
    acc = await db.get_account(user_id)
    url = f"{BASE_URL}/app" + (f"?acc={acc}" if acc else "")
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📱 Открыть мини-апп", web_app=WebAppInfo(url=url))]])


@main_router.message(CommandStart())
async def start(m: Message):
    await m.answer(
        "Привет! Я Lumeny — бот для Dota 2: профиль, разбор матчей, уведомления о катках друзей и викторина.\n\n"
        "Начни с привязки аккаунта: /link ВАШ_ID\nВсе команды: /dota",
        reply_markup=await app_keyboard(m.from_user.id),
    )


@main_router.message(Command("app"))
async def app_cmd(m: Message):
    kb = await app_keyboard(m.from_user.id)
    if kb:
        await m.answer("Твой профиль в мини-аппе:", reply_markup=kb)
    else:
        await m.answer("Мини-апп пока не настроен: не задан BASE_URL.")


async def main():
    await db.init()
    bot = Bot(TOKEN)
    dp = Dispatcher()
    dp.include_router(main_router)
    dp.include_router(dota_router)

    runner = web.AppRunner(make_app())
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "8080"))).start()

    if BASE_URL.startswith("https://"):
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
            text="Профиль", web_app=WebAppInfo(url=f"{BASE_URL}/app")))

    notifier = asyncio.create_task(notifier_loop(bot))
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        notifier.cancel()


if __name__ == "__main__":
    asyncio.run(main())
