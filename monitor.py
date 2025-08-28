import json
from datetime import datetime
from web3 import Web3
import requests

# === KONFIG ===
RPC_URL = "https://arb-mainnet.g.alchemy.com/v2/Nj4G5fjazRLiSREiRTES8oG5b3HMznyx" # <-- twój RPC
KRS_ADDRESS   = "0x521e58970fBa0AEAF6DC9C2e994ec9e9CD71A070"
USDC_ADDRESS  = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # <-- ADRES USDC z Twojej puli (albo 0xff97…)
FEE_TIER      = 3000                                          # <-- 500 / 3000 / 10000 zgodnie z pulą
FACTORY_V3    = "0x1F98431c8aD98523631AE4a59f267346ea31F984"

FACTORY_ABI = [{
    "inputs":[{"name":"tokenA","type":"address"},{"name":"tokenB","type":"address"},{"name":"fee","type":"uint24"}],
    "name":"getPool","outputs":[{"name":"pool","type":"address"}],"stateMutability":"view","type":"function"
}]
POOL_ABI = [
    {"name":"slot0","inputs":[],"outputs":[
        {"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"},
        {"name":"observationIndex","type":"uint16"},{"name":"observationCardinality","type":"uint16"},
        {"name":"observationCardinalityNext","type":"uint16"},{"name":"feeProtocol","type":"uint8"},
        {"name":"unlocked","type":"bool"}], "stateMutability":"view","type":"function"},
    {"name":"token0","inputs":[],"outputs":[{"type":"address"}],"stateMutability":"view","type":"function"},
    {"name":"token1","inputs":[],"outputs":[{"type":"address"}],"stateMutability":"view","type":"function"},
]
ERC20_ABI = [
    {"constant":True,"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
    {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))

to_checksum = Web3.to_checksum_address
KRS  = to_checksum(KRS_ADDRESS)
USDC = to_checksum(USDC_ADDRESS)
FACT = w3.eth.contract(address=to_checksum(FACTORY_V3), abi=FACTORY_ABI)

def get_pool(a, b, fee):
    return FACT.functions.getPool(to_checksum(a), to_checksum(b), fee).call()

def get_decimals(addr):
    c = w3.eth.contract(address=to_checksum(addr), abi=ERC20_ABI)
    return c.functions.decimals().call()

def token_balance(token, pool):
    c = w3.eth.contract(address=to_checksum(token), abi=ERC20_ABI)
    dec = c.functions.decimals().call()
    raw = c.functions.balanceOf(to_checksum(pool)).call()
    return raw / (10 ** dec)

def eth_usd():
    return requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd").json()["ethereum"]["usd"]

def eth_pln():
    return requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=pln").json()["ethereum"]["pln"]

def usdc_per_krs_from_pool(pool):
    pc = w3.eth.contract(address=to_checksum(pool), abi=POOL_ABI)
    t0, t1 = pc.functions.token0().call(), pc.functions.token1().call()
    sqrtP   = pc.functions.slot0().call()[0]
    if sqrtP == 0: return 0.0

    d0, d1 = get_decimals(t0), get_decimals(t1)
    # cena token1 za 1 token0
    price1per0 = (sqrtP * sqrtP) / (1 << 192) * (10 ** (d0 - d1))

    # chcemy USDC za 1 KRS
    if t0.lower() == KRS.lower() and t1.lower() == USDC.lower():
        return price1per0
    elif t1.lower() == KRS.lower() and t0.lower() == USDC.lower():
        return 1.0 / price1per0
    else:
        return 0.0

# --- znajdź pulę i policz cenę ---
pool_usdc = get_pool(KRS, USDC, FEE_TIER)
if int(pool_usdc, 16) == 0:
    raise SystemExit("❌ Nie znaleziono puli KRS/USDC dla fee %s. Sprawdź adres USDC i fee." % FEE_TIER)

krs_usdc = usdc_per_krs_from_pool(pool_usdc)     # USDC za 1 KRS
if krs_usdc <= 0:
    raise SystemExit("❌ slot0 zwrócił 0 – sprawdź czy adresy i fee są poprawne.")

# --- ceny ETH ---
EUSD = eth_usd()
EPLN = eth_pln()

# KRS/ETH wyliczamy via USDC (brak puli WETH)
krs_eth = krs_usdc / EUSD

# --- stany puli ---
krs_in_pool  = token_balance(KRS,  pool_usdc)
usdc_in_pool = token_balance(USDC, pool_usdc)

# wartości puli
pool_value_usd = usdc_in_pool + krs_in_pool * krs_usdc
pool_value_eth = pool_value_usd / EUSD
pool_value_pln = pool_value_eth * EPLN

out = {
    "WETH": round(krs_eth, 8),          # ETH za 1 KRS (via USDC)
    "USDC": round(krs_usdc, 6),         # USDC za 1 KRS
    "ETHPLN": EPLN,
    "ETHUSD": EUSD,
    "pool": {
        "krs_usdc": round(krs_in_pool, 2),
        "usdc": round(usdc_in_pool, 2),
        "krs_weth": 0.0,
        "weth": 0.0,
        "value_usd": round(pool_value_usd, 2),
        "value_eth": round(pool_value_eth, 6),
        "value_pln": round(pool_value_pln, 2),
    }
}

with open("kursy.json","w") as f:
    json.dump(out, f, indent=2)

# log z doby (max 144 wpisy co 10 min)
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
try:
    log = json.load(open("kursy_doba.json"))
except:
    log = []
log.append({"timestamp": now, **out})
log = log[-144:]
json.dump(log, open("kursy_doba.json","w"), indent=2)

print("✅ zapisano kursy.json; pool:", pool_usdc)
