
import time
from datetime import datetime, timedelta
import requests
import os
from seleniumbase import Driver
from dotenv import load_dotenv
import socket
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json

# Load environment variables
load_dotenv()

# ========== CONFIG ==========

LICENSE_EXPIRY = (datetime.today().date() + timedelta(days=365)).strftime("%Y-%m-%d")
ALLOWED_HOSTNAME = "Paradox"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "")

# ========== LICENSE VALIDATION ==========

def validate_license():
    current_host = socket.gethostname()
    today = datetime.today().date()

    print("🔐 LICENSE_EXPIRY =", LICENSE_EXPIRY)
    print("🖥️ Current Hostname =", current_host)

    if current_host != ALLOWED_HOSTNAME:
        print("❌ Unauthorized host.")
        exit()

    try:
        expiry_date = datetime.strptime(LICENSE_EXPIRY, "%Y-%m-%d").date()
        if today > expiry_date:
            print("❌ License expired.")
            exit()
    except Exception as e:
        print("❌ License expiry date invalid.", e)
        exit()

validate_license()

# ========== TELEGRAM ALERT ==========

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payloads = [
        {"chat_id": TELEGRAM_CHAT_ID, "text": message},
        {"chat_id": TELEGRAM_GROUP_ID, "text": message}
    ]
    for payload in payloads:
        try:
            requests.post(url, json=payload, timeout=10)
        except requests.exceptions.Timeout:
            print("Telegram error: Request timed out.")
        except Exception as e:
            print("Telegram error:", e)

# ========== LOG TO TXT ==========

def log_signal_to_txt(timestamp, pair, direction, price):
    file_path = "signals.txt"
    log_line = f"{timestamp} - {pair} - {direction}\n"

    with open(file_path, "a") as f:
        f.write(log_line)

# ========== LOG TO JSON ==========
        
def save_signal_to_json(data, file="signals.json"):
    try:
        signals = []
        if os.path.exists(file):
            with open(file, "r") as f:
                signals = json.load(f)
        signals.append(data)
        with open(file, "w") as f:
            json.dump(signals[-100:], f, indent=2)  # Keep only last 100 signals
    except Exception as e:
        print("Error saving signal to JSON:", e)

# ========== NEW INDICATOR ==========

def calculate_channel_breakout(price_series, length=20, swing_sensitivity=1.0):
    if len(price_series) < length + 2:
        return None

    recent_prices = price_series[-length:]
    highest_high = max(recent_prices)
    lowest_low = min(recent_prices)
    current_price = price_series[-1]
    previous_price = price_series[-2]

    buffer = (highest_high - lowest_low) * swing_sensitivity * 0.1

    if previous_price < highest_high - buffer and current_price >= highest_high - buffer:
        return "BUY"
    elif previous_price > lowest_low + buffer and current_price <= lowest_low + buffer:
        return "SELL"
    return None

# ========== MAIN BOT ==========

class QuotexSignalBot:
    def __init__(self, headless=False):
        self.driver = Driver(uc=True, headless=headless)
        self.signal_data = None
        self.last_signal_time = None

    def wait_for_modal(self):
        print("🔓 Please open the pair information modal manually within the next 30 seconds...")
        try:
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.modal-pair-information__body-value")))
            print("✅ Modal detected. Bot is ready.")
        except Exception as e:
            print("❌ Modal not detected. Please open it and restart the bot.")
            self.driver.save_screenshot("modal_error.png")
            self.driver.quit()
            exit()

    def fetch_price_and_pair(self):
        try:
            wait = WebDriverWait(self.driver, 10)
            price_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-pair-information__body-value")))
            pair_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-pair-information__header-label")))

            price = float(price_elem.text.strip())
            pair = pair_elem.text.strip()
            return price, pair
        except Exception as e:
            print(f"⚠ Error fetching price/pair: {e}")
            self.driver.save_screenshot("error_screenshot.png")
            return None, None

    def run_bot(self):
        self.driver.get("https://quotex.com/en")
        print("⏳ Please log in manually. Bot will continue in 60 seconds...")
        time.sleep(60)
        print("✅ Logged in.")

        self.wait_for_modal()

        price_history = []

        try:
            while True:
                now = datetime.now()
                seconds = now.second

                price, pair = self.fetch_price_and_pair()
                if price is None:
                    time.sleep(2)
                    continue

                price_history.append(price)
                if len(price_history) > 100:
                    price_history.pop(0)

                if (self.last_signal_time is None or
                    now >= self.last_signal_time + timedelta(minutes=2)) and seconds < 53:

                    signal = calculate_channel_breakout(price_history)
                    if signal:
                        self.signal_data = {
                            "time": now.strftime("%H:%M:%S"),
                            "signal": signal,
                            "pair": pair,
                            "price": price
                        }
                        self.last_signal_time = now
                        print(f"📌 Signal prepared for next candle: {self.signal_data}")

                if seconds == 53 and self.signal_data:
                    signal = self.signal_data['signal']
                    direction = "UP" if signal == "BUY" else "DOWN"
                    message = f"{datetime.now().strftime('%H:%M:%S')} - {self.signal_data['pair']} - {direction} (Next Candle)"
                    # save it to json
                    save_signal_to_json(self.signal_data)
                    # send it to telegram
                    send_telegram_alert(message)
                    log_signal_to_txt(
                        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        pair=self.signal_data['pair'],
                        direction=direction,
                        price=self.signal_data['price']
                    )

                    print(f"✅ Signal for next candle sent and logged: {message}")
                    self.signal_data = None

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n🚩 Bot manually stopped.")
            self.driver.quit()

#   --------- clear json ---------
if os.path.exists("signals.json"):
    with open("signals.json", "w") as f:
        json.dump([], f)
# ========== RUN ==========

if __name__ == "__main__":
    validate_license()
    bot = QuotexSignalBot(headless=False)
    bot.run_bot()
