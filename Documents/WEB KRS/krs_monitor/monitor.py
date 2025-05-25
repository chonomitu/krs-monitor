
import time
import requests
from web3 import Web3
from config import RPC_URL, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# Adresy pul Uniswap V3
KRS_ETH_POOL = "0x4F4F6a4f5A28420B57A49Fe5cc935b441BB52456"
KRS_USDC_POOL = "0xca71156bFe3bBecb281B78BF8bd9C083D1db222b"

# ABI slot0
SLOT0_ABI = [{
    "inputs": [],
    "name": "slot0",
    "outputs": [
        {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
        {"internalType": "int24", "name": "tick", "type": "int24"},
        {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
        {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
        {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
        {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
        {"internalType": "bool", "name": "unlocked", "type": "bool"}
    ],
    "stateMutability": "view",
    "type": "function"
}]

w3 = Web3(Web3.HTTPProvider(RPC_URL))

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_price_from_slot0(pool_address):
    pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=SLOT0_ABI)
    sqrt_price = pool.functions.slot0().call()[0]
    price = (sqrt_price ** 2) / (2 ** 192)
    return price

def monitor():
    try:
        price_eth = get_price_from_slot0(KRS_ETH_POOL)  # KRS/ETH
        price_usdc = get_price_from_slot0(KRS_USDC_POOL)  # KRS/USDC

        eth_usd = 2500
        usd_pln = 4

        price_eth_pln = price_eth * eth_usd * usd_pln
        price_usdc_pln = price_usdc * usd_pln
        delta = abs(price_eth_pln - price_usdc_pln)

        alerts = []

        if delta > 0.2:
            alerts.append(f"⚠️ Rozjazd kursów: ETH {price_eth_pln:.2f} PLN vs USDC {price_usdc_pln:.2f} PLN")

        if not (0.000089 <= price_eth <= 0.000111):
            alerts.append(f"⚠️ KRS/ETH poza zakresem: {price_eth}")

        if alerts:
            send_telegram_alert("\n".join(alerts))
        else:
            print("✔️ Wszystko OK")

    except Exception as e:
        send_telegram_alert(f"❌ Błąd w monitorze: {e}")
        print(e)

if __name__ == "__main__":
    monitor()

