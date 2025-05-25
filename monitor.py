
import time
import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

KRS_USDC_POOL = "0xca71156bFe3bBecb281B78BF8bd9C083D1db222b"
KRS_ETH_POOL  = "0x4F4F6a4f5A28420B57A49Fe5cc935b441BB52456"

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

def monitor():
    # TODO: Implementacja odczytu slot0, obliczenia kursów KRS/ETH i KRS/USDC
    # oraz wykrycie "out of range", rozjazdów i alertów.
    print("Monitoring aktywny...")  # Zastępcze
    send_telegram_alert("Test: KRS monitor działa poprawnie!")

if __name__ == "__main__":
    monitor()

