import re
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# إعداد من .env
CHROME_HEADLESS = os.getenv("CHROME_HEADLESS", "false").lower() == "true"
WHATSAPP_CHANNEL_NAME = os.getenv("WHATSAPP_CHANNEL_NAME", "Angebote")

def remove_non_bmp_chars(text):
    return ''.join(c for c in text if ord(c) <= 0xFFFF)

def prepare_message_for_whatsapp(message: str) -> str:
    # يفصل الرابط بسطر جديد إذا جاء بعد نص مباشرة
    def add_line_before_link(match):
        preceding_text = match.group(1)
        link = match.group(2)
        if preceding_text and not preceding_text.endswith('\n\n'):
            return preceding_text + '\n\n' + link
        return preceding_text + link

    pattern = re.compile(r'(?s)(.*?)(https?://[^\s\n]+)')
    new_message = ""
    last_end = 0
    for m in pattern.finditer(message):
        start, end = m.span()
        before = message[last_end:start]
        new_message += before
        new_message += add_line_before_link(m)
        last_end = end
    new_message += message[last_end:]
    return new_message

class WhatsAppSender:
    def __init__(self):
        options = webdriver.ChromeOptions()
        profile_path = os.path.join(os.getcwd(), "chrome_profile")

        # نحفظ الجلسة حتى لا تحتاج QR كل مرة
        options.add_argument(f"--user-data-dir={profile_path}")

        # Headless mode لتشغيل بدون واجهة
        if CHROME_HEADLESS:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")

        # إعدادات مهمة لتجنب مشاكل السيرفرات
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--window-size=1920,1080")

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        self.driver.get("https://web.whatsapp.com")
        print("[WA] فتح WhatsApp Web ... انتظر حتى يظهر QR أو الصفحة الرئيسية")
        time.sleep(10)

    def ensure_logged_in(self, timeout=120):
        """يتأكد من أن الجلسة مفتوحة، أو يعطي فرصة لمسح QR"""
        t0 = time.time()
        while True:
            try:
                # إذا وجد مربع الرسائل، فمعناه تسجيل الدخول تم
                self.driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab]')
                print("[WA] ✅ تم تسجيل الدخول في WhatsApp Web.")
                return True
            except Exception:
                if time.time() - t0 > timeout:
                    print("[WA] ❌ لم يتم تسجيل الدخول خلال الوقت المخصص.")
                    return False
                time.sleep(2)

    def send_message_to_channel(self, message, tries=2):
        """إرسال الرسالة إلى قناة أو مجموعة محددة باسمها"""
        try:
            prepared_message = prepare_message_for_whatsapp(message)

            # البحث عن القناة
            search_box = None
            xpaths = [
                '//div[@contenteditable="true"][@data-tab="3"]',
                '//div[@contenteditable="true"][@data-tab="9"]',
                '//div[@contenteditable="true"][@data-tab="0"]'
            ]
            for xp in xpaths:
                try:
                    search_box = self.driver.find_element(By.XPATH, xp)
                    break
                except:
                    continue
            if not search_box:
                raise Exception("❌ لم أجد صندوق البحث في واتساب.")

            search_box.click()
            time.sleep(0.5)
            search_box.clear()
            search_box.send_keys(WHATSAPP_CHANNEL_NAME)
            time.sleep(2)
            search_box.send_keys(Keys.ENTER)
            time.sleep(3)

            # صندوق الرسائل
            msg_box = None
            msg_xpaths = [
                '//div[@contenteditable="true"][@data-tab="10"]',
                '//div[@contenteditable="true"][@data-tab="6"]',
                '//div[@contenteditable="true"][@data-tab="1"]'
            ]
            for xp in msg_xpaths:
                try:
                    msg_box = self.driver.find_element(By.XPATH, xp)
                    break
                except:
                    continue
            if not msg_box:
                raise Exception("❌ لم أجد صندوق الرسائل.")

            msg_box.click()
            safe_message = remove_non_bmp_chars(prepared_message)

            # كتابة الرسالة (مع احترام الأسطر)
            for line in safe_message.splitlines():
                msg_box.send_keys(line)
                msg_box.send_keys(Keys.SHIFT, Keys.ENTER)
            time.sleep(1)
            msg_box.send_keys(Keys.ENTER)
            print(f"[WA] ✅ تم إرسال الرسالة إلى القناة: {WHATSAPP_CHANNEL_NAME}")
            return True

        except Exception as e:
            print("[WA] ⚠️ خطأ أثناء الإرسال:", e)
            if tries > 0:
                time.sleep(3)
                return self.send_message_to_channel(message, tries - 1)
            return False

    def close(self):
        try:
            self.driver.quit()
        except:
            pass
