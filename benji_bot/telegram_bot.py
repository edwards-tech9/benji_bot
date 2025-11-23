import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv

load_dotenv()

async def send_alert(chat_id, message):
    if not chat_id or not os.getenv('TELEGRAM_BOT_TOKEN'):
        return
    try:
        bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        await bot.send_message(chat_id=chat_id, text=message)
    except:
        pass

def send_telegram(chat_id, message):
    asyncio.run(send_alert(chat_id, message))
