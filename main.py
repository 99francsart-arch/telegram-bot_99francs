import os
import asyncio
import hashlib
import time
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL") 

# === НАЛАШТУВАННЯ META CAPI ===
PIXEL_ID = os.getenv("META_PIXEL_ID", "1397593445686318")
CAPI_ACCESS_TOKEN = os.getenv("META_CAPI_TOKEN", "")  # Вставте ваш токен сюди або додайте в Environment Variables на Render

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def send_meta_capi_lead(user_id: int):
    """Асинхронна відправка події Lead у Meta Conversions API (CAPI)"""
    if not CAPI_ACCESS_TOKEN:
        print("⚠️ META_CAPI_TOKEN не вказано! Подія Lead не була відправлена.")
        return

    url = f"https://graph.facebook.com/v19.0/{PIXEL_ID}/events"
    hashed_user_id = hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()

    payload = {
        "data": [
            {
                "event_name": "Lead",
                "event_time": int(time.time()),
                "action_source": "system_generated",
                "user_data": {
                    "external_id": [hashed_user_id]
                },
                "custom_data": {
                    "channel_name": "TWOONE",
                    "event_source": "telegram_bot"
                }
            }
        ],
        "access_token": CAPI_ACCESS_TOKEN
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=5) as response:
                result = await response.json()
                print(f"📊 CAPI Статус для {user_id}: {response.status} | Відповідь: {result}")
    except Exception as e:
        print(f"❌ Помилка відправки в Meta CAPI: {e}")


@dp.chat_join_request()
async def approve_request(update: types.ChatJoinRequest):
    user_id = update.from_user.id
    user_name = update.from_user.first_name
    chat_name = update.chat.title
    print(f"🔗 Отримано заявку від {user_name} (ID: {user_id}) у канал '{chat_name}'")
    
    try:
        # 1. Схвалюємо заявку в каналі
        await update.approve()
        print(f"✅ Заявку {user_name} успішно схвалено!")

        # 2. Відправляємо подію Lead у Meta CAPI (запускається у фоні, щоб не гальмувати відповідь бота)
        asyncio.create_task(send_meta_capi_lead(user_id=user_id))

    except Exception as e:
        print(f"❌ Помилка при схванні заявки: {e}")


async def handle_webhook(request):
    url = str(request.url)
    if not url.endswith('/webhook'):
        return web.Response(text="Бот працює через Webhook!")
        
    try:
        json_data = await request.json()
        update = Update(**json_data)
        await dp.feed_update(bot=bot, update=update)
        return web.Response(status=200)
    except Exception as e:
        print(f"Помилка вебхуку: {e}")
        return web.Response(status=500)


async def start_async_app():
    # 1. Примусово ставимо вебхук у Telegram
    webhook_url = f"{BASE_URL}/webhook"
    print(f"⏳ Спроба встановити Webhook на: {webhook_url}...")
    try:
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        print(f"🌐 Webhook УСПІШНО встановлено в Telegram!")
    except Exception as e:
        print(f"❌ Критична помилка встановлення вебхуку: {e}")

    # 2. Налаштовуємо та запускаємо вебсервер
    app = web.Application()
    app.router.add_post('/webhook', handle_webhook)
    app.router.add_get('/', handle_webhook)
    
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Запуск веб-сервера на порту {port}...")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    
    # Тримаємо сервер запущеним безкінечно
    await asyncio.Event().wait()


def main():
    # Сучасний та безпечний запуск для нових версій Python
    asyncio.run(start_async_app())


if __name__ == "__main__":
    main()
