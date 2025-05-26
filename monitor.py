import json
from datetime import datetime
from web3 import Web3
import requests

DEBUG = False

# Konfiguracja
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
    "outputs": [{"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"}, {"internalType": "int24", "name": "tick", "type": "int24"},
                {"internalType": "uint16", "name": "observationIndex", "type": "uint16"}, {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
                {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"}, {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
                {"internalType": "bool", "name": "unlocked", "type": "bool"}],
    "stateMutability": "view",
    "type": "function"
}]
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}
]

# Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))

def get_pool(tokenA, tokenB):
    factory = w3.eth.contract(address=Web3.to_checksum_address(FACTORY_V3), abi=FACTORY_ABI)
    return factory.functions.getPool(Web3.to_checksum_address(tokenA), Web3.to_checksum_address(tokenB), FEE).call()

def read_slot0(pool):
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(pool), abi=POOL_ABI)
        sqrt_price = contract.functions.slot0().call()[0]
        return (sqrt_price ** 2) / 2 ** 192
    except:
        return 0

def get_token_balance(token, pool):
    try:
        c = w3.eth.contract(address=Web3.to_checksum_address(token), abi=ERC20_ABI)
        decimals = c.functions.decimals().call()
        raw = c.functions.balanceOf(Web3.to_checksum_address(pool)).call()
        return raw / (10 ** decimals)
    except:
        return 0

def get_eth_pln():
    try:
        return requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=pln").json()["ethereum"]["pln"]
    except:
        return 0

def get_eth_usd():
    try:
        return requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd").json()["ethereum"]["usd"]
    except:
        return 0

# Dane wyjściowe
output = {}
pools = {}

# Kursy KRS do WETH i USDC
for name, (tokenB, _) in TOKEN_BS.items():
    pool = get_pool(TOKEN_A, tokenB)
    pools[name] = pool
    raw = read_slot0(pool)
    if name == "WETH":
        output["WETH"] = round(1 / raw * 1e-8, 8)
    else:
        output["USDC"] = round(raw * 1e12, 8)

# Tokeny w pulach
output["pool"] = {
    "krs_usdc": get_token_balance(TOKEN_A, pools["USDC"]),
    "usdc": get_token_balance(TOKEN_BS["USDC"][0], pools["USDC"]),
    "krs_weth": get_token_balance(TOKEN_A, pools["WETH"]),
    "weth": get_token_balance(TOKEN_BS["WETH"][0], pools["WETH"])
}

# Kursy ETH
output["ETHPLN"] = eth_pln = get_eth_pln()
output["ETHUSD"] = eth_usd = get_eth_usd()

# Wartości puli
krs_usdc_val = output["pool"]["krs_usdc"] * output["USDC"]
usdc_val = output["pool"]["usdc"]
krs_weth_val = output["pool"]["krs_weth"] * output["WETH"]
weth_val = output["pool"]["weth"] * output["WETH"]

pool_usd = krs_usdc_val + usdc_val + krs_weth_val + weth_val
pool_eth = pool_usd / eth_usd
pool_pln = pool_eth * eth_pln

output["pool"]["value_usd"] = round(pool_usd, 2)
output["pool"]["value_eth"] = round(pool_eth, 6)
output["pool"]["value_pln"] = round(pool_pln, 2)

# Zapis do kursy.json
with open("kursy.json", "w") as f:
    json.dump(output, f, indent=2)

# Zapis do kursy_doba.json
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
try:
    with open("kursy_doba.json", "r") as f:
        log = json.load(f)
except:
    log = []

log.append({"timestamp": now, **output})
log = log[-144:]
with open("kursy_doba.json", "w") as f:
    json.dump(log, f, indent=2)

if DEBUG:
    print(json.dumps(output, indent=2))
