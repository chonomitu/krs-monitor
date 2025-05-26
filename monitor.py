import json
from datetime import datetime
from web3 import Web3

DEBUG = False

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
    "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
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

ERC20_ABI = [{
    "constant": True,
    "inputs": [{"name": "owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "type": "function"
}, {
    "constant": True,
    "inputs": [],
    "name": "decimals",
    "outputs": [{"name": "", "type": "uint8"}],
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

def read_slot0(pool_address):
    try:
        pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)
        slot0 = pool.functions.slot0().call()
        sqrt_price = slot0[0]
        raw_price = (sqrt_price ** 2) / (2 ** 192)
        return raw_price, sqrt_price
    except Exception as e:
        print(f"Błąd odczytu slot0: {e}")
        return 0, 0

def get_token_balance(token_address, pool_address):
    try:
        token = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        raw = token.functions.balanceOf(Web3.to_checksum_address(pool_address)).call()
        decimals = token.functions.decimals().call()
        return raw / (10 ** decimals)
    except Exception as e:
        print(f"Błąd odczytu salda tokenu {token_address} w puli {pool_address}: {e}")
        return 0

output = {}

if DEBUG:
    print("\n🔍 Trwa pobieranie kursów KRS...")

pools = {}

for name, (tokenB, should_invert) in TOKEN_BS.items():
    if DEBUG:
        print(f"\n🔍 Szukam puli KRS / {name}...")

    pool_address = get_pool(TOKEN_A, tokenB)
    if pool_address:
        pools[name] = pool_address
        if DEBUG:
            print(f"✅ Adres puli: {pool_address}")
        price, sqrt_price = read_slot0(pool_address)
        raw_price = (sqrt_price ** 2) / (2 ** 192) if sqrt_price != 0 else 0

        if DEBUG:
            print(f"↪ sqrtPriceX96 = {sqrt_price}")
            print(f"↪ kurs RAW = {raw_price}")

        if name == "WETH":
            output[name] = round(invert(raw_price) * 10**-8, 8)
        elif name == "USDC":
            output[name] = round(raw_price * 10**12, 8)
    else:
        output[name] = 0

# Dodaj saldo tokenów w pulach
output["pool"] = {
    "krs_usdc": get_token_balance(TOKEN_A, pools.get("USDC", "")),
    "usdc": get_token_balance(TOKEN_BS["USDC"][0], pools.get("USDC", "")),
    "krs_weth": get_token_balance(TOKEN_A, pools.get("WETH", "")),
    "weth": get_token_balance(TOKEN_BS["WETH"][0], pools.get("WETH", ""))
}

if DEBUG:
    print("\n📊 Kursy końcowe:")
    for k, v in output.items():
        if k == "pool": continue
        print(f"{k}: {v}")
    print("\n🧪 Pula tokenów:")
    for k, v in output["pool"].items():
        print(f"{k}: {v}")

# Zapis do kursy.json
with open("kursy.json", "w") as f:
    json.dump(output, f, indent=2)

# Logowanie do kursy_doba.json
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
