import requests
import json
from datetime import datetime, timedelta
from web3 import Web3
from config import RPC_URL, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

KRS_ETH_POOL = "0x4F4F6a4f5A28420B57A49Fe5cc935b441BB52456"
KRS_USDC_POOL = "0xca71156bFe3bBecb281B78BF8bd9C083D1db222b"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

SLOT0_ABI = [{
    "inputs": [],
    "name": "slot0",
    "outputs": [{"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"}],
    "stateMutability": "view",
    "type": "function"
}]

def send_telegram_alert(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        print("Błąd wysyłania telegrama:", e)

def get_price_from_slot0(pool_address):
    try:
        pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=SLOT0_ABI)
        sqrt_price = pool.functions.slot0().call()[0]
        return (sqrt_price ** 2) / (2 ** 192)
    except:
        return 0.0

def monitor():
    price_eth = get_price_from_slot0(KRS_ETH_POOL)
    price_usdc = get_price_from_slot0(KRS_USDC_POOL)
################ DEBUG
    print(f"DEBUG: price_eth={price_eth}, price_usdc={price_usdc}")
##################
    eth_usd = 2500  # zakładany kurs
    usd_pln = 4

    price_eth_pln = round(price_eth * eth_usd * usd_pln, 4)
    price_usdc_pln = round(price_usdc * usd_pln, 4)

    alerts = []

    if price_eth_pln == 0 or price_usdc_pln == 0:
        alerts.append("⚠️ Nieprawidłowe dane: jedna z cen wynosi 0")
    elif abs(price_eth_pln - price_usdc_pln) > 0.2:
        alerts.append(f"⚠️ Rozjazd kursów: ETH {price_eth_pln:.2f} PLN vs USDC {price_usdc_pln:.2f} PLN")

    if alerts:
        send_telegram_alert("\\n".join(alerts))

    # Zapis do kursy.json
    now = datetime.utcnow()
    out = {
        "timestamp": now.isoformat(),
        "krs_eth_pln": price_eth_pln,
        "krs_usdc_pln": price_usdc_pln,
        "eth_pln": eth_usd * usd_pln
    }
    with open("kursy.json", "w") as f:
        json.dump(out, f, indent=2)

    # Zapis do kursy_doba.json (maks. 24h)
    try:
        with open("kursy_doba.json", "r") as f:
            history = json.load(f)
    except:
        history = []

    history.append(out)
    history = [d for d in history if datetime.fromisoformat(d["timestamp"]) > now - timedelta(days=1)]

    with open("kursy_doba.json", "w") as f:
        json.dump(history, f, indent=2)

    print("✔️ Monitoring zakończony.")

if __name__ == "__main__":
    monitor()
