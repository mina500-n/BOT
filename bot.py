import os
import time
import re
from dotenv import load_dotenv
from telethon import TelegramClient, events, errors
from send_whatsapp import WhatsAppSender
import asyncio

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
TELEGRAM_CHANNEL_USERNAME = os.getenv('TELEGRAM_CHANNEL_USERNAME')
LOG_FILE = os.getenv('LOG_FILE', 'bot.log')
CUSTOM_AFFILIATE_TAG = os.getenv('CUSTOM_AFFILIATE_TAG')

wa_sender = None

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def replace_amazon_tag(text):
    if not CUSTOM_AFFILIATE_TAG:
        return text

    def replace_tag(match):
        url = match.group(0)
        if "tag=" in url:
            return re.sub(r'tag=[^&]+', f'tag={CUSTOM_AFFILIATE_TAG}', url)
        else:
            separator = '&' if '?' in url else '?'
            return f"{url}{separator}tag={CUSTOM_AFFILIATE_TAG}"

    return re.sub(r'https://www\.amazon\.[a-z\.]+/[^\s\n]+', replace_tag, text)

async def main():
    global wa_sender
    wa_sender = WhatsAppSender()
    logged = wa_sender.ensure_logged_in(timeout=120)
    if not logged:
        log("لم يتم تسجيل الدخول في WhatsApp Web. قم بعمل QR scan ثم أعد تشغيل البرنامج.")
        return

    client = TelegramClient('tg_session', API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        phone = input("Please enter your phone number: ")
        try:
            phone_code = await client.send_code_request(phone)
            code = input("Please enter the code you received: ")
            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code.phone_code_hash)
            except errors.SessionPasswordNeededError:
                password = input("Two-step verification enabled. Please enter your password: ")
                await client.sign_in(password=password)
        except Exception as e:
            log(f"error during login: {e}")
            return

    log(f"telegram bot is running. Listening to Telegram channel: {TELEGRAM_CHANNEL_USERNAME}")

    @client.on(events.NewMessage(chats=TELEGRAM_CHANNEL_USERNAME))
    async def handler(event):
        try:
            text = event.message.message or event.raw_text or "<رسالة لا تحتوي نص>"
            log(f"new message in Telegram: {text[:200]}")
            text = replace_amazon_tag(text)
            ok = wa_sender.send_message_to_channel(text)
            if ok:
                log("sent message to WhatsApp successfully.")
            else:
                log("failed to send message to WhatsApp.")
        except Exception as e:
            log("error processing message: " + str(e))

    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('logging out...')
    finally:
        if wa_sender:
            wa_sender.close()
