import json
from datetime import datetime
from web3 import Web3

# Ustawienia
TOKEN_A = "0x521e58970fBa0AEAF6DC9C2e994ec9e9CD71A070"  # KRS
TOKEN_BS = {
    "WETH": ("0x82af49447d8a07e3bd95bd0d56f35241523fbab1", False),
    "USDC": ("0xaf88d065e77c8cC2239327C5EDb3A432268e5831", True)
}
FEE = 3000
RPC_URL = "https://arb-mainnet.g.alchemy.com/v2/Nj4G5fjazRLiSREiRTES8oG5b3HMznyx"
FACTORY_V3 = "0x1F98431c8aD98523631AE4a59f267346ea31F984"

# ABI
FACTORY_ABI = [{
    "inputs": [
        {"internalType": "address", "name": "tokenA", "type": "address"},
        {"internalType": "address", "name": "tokenB", "type": "address"},
        {"internalType": "uint24", "name": "fee", "type": "uint24"}
    ],
    "name": "getPool",
    "outputs": [
        {"internalType": "address", "name": "pool", "type": "address"}
    ],
    "stateMutability": "view",
    "type": "function"
}]

POOL_ABI = [{
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


def get_pool(tokenA, tokenB):
    factory = w3.eth.contract(address=Web3.to_checksum_address(FACTORY_V3), abi=FACTORY_ABI)
    try:
        pool = factory.functions.getPool(
            Web3.to_checksum_address(tokenA),
            Web3.to_checksum_address(tokenB),
            FEE
        ).call()
        return pool if int(pool, 16) != 0 else None
    except Exception as e:
        print(f"Błąd pobierania adresu puli: {e}")
        return None


def invert(price):
    return 1 / price if price != 0 else 0


def read_slot0(pool_address, invert_result=False):
    try:
        pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)
        slot0 = pool.functions.slot0().call()
        sqrt_price = slot0[0]
        raw_price = (sqrt_price ** 2) / (2 ** 192)
        corrected = invert(raw_price) if invert_result else raw_price
        return corrected, sqrt_price
    except Exception as e:
        print(f"Błąd odczytu slot0: {e}")
        return 0, 0

output = {}

print("\n🔍 Trwa pobieranie kursów KRS...")

for name, (tokenB, should_invert) in TOKEN_BS.items():
    print(f"\n🔍 Szukam puli KRS / {name}...")
    pool_address = get_pool(TOKEN_A, tokenB)
    if pool_address:
        print(f"✅ Adres puli KRS / {name}: {pool_address}")
        price, sqrt_price = read_slot0(pool_address, invert_result=should_invert)
        raw_price = (sqrt_price ** 2) / (2 ** 192) if sqrt_price != 0 else 0
        print(f"↪ sqrtPriceX96 = {sqrt_price}")
        print(f"↪ obliczony kurs ≈ {price:.8f}")
        print(f"↪ kurs RAW = {raw_price}")
        print(f"↪ odwrócony kurs = {invert(price)}")
        output[name] = round(price, 4)
    else:
        print(f"❌ Nie znaleziono puli dla {name}.")
        output[name] = 0

# Zapis do pliku JSON
with open("kursy.json", "w") as f:
    json.dump(output, f, indent=2)

# Zapis do kursy_doba.json z timestampem
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
try:
    with open("kursy_doba.json", "r") as f:
        log = json.load(f)
except:
    log = []

log.append({"timestamp": now, **output})
log = log[-144:]

with open("kursy_doba.json", "w") as f:
    json.dump(log, f, indent=2)

print("\n📊 Kursy końcowe:")
for name, val in output.items():
    print(f"{name}: {val} PLN")
