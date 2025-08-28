import json
from datetime import datetime
from web3 import Web3
import requests

DEBUG = False

# --- Konfiguracja ---
TOKEN_KRS = "0x521e58970fBa0AEAF6DC9C2e994ec9e9CD71A070"
TOKEN_WETH = "0x82af49447d8a07e3bd95bd0d56f35241523fbab1"
TOKEN_USDC = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # natywny USDC (6 dec)

FEE = 3000
RPC_URL = "https://arb-mainnet.g.alchemy.com/v2/Nj4G5fjazRLiSREiRTES8oG5b3HMznyx"
FACTORY_V3 = "0x1F98431c8aD98523631AE4a59f267346ea31F984"

# --- ABI ---
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
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}
]

# --- Web3 ---
w3 = Web3(Web3.HTTPProvider(RPC_URL))

def to_cs(addr: str) -> str:
    return Web3.to_checksum_address(addr)

def sort_tokens(a: str, b: str):
    """Zwróć (token0, token1) posortowane jak w Uniswap V3 (po adresie)."""
    ai = int(a, 16); bi = int(b, 16)
    return (a, b) if ai < bi else (b, a)

def get_pool_addr(tokenA: str, tokenB: str):
    """factory.getPool(token0, token1, fee) – UWAGA: trzeba podać posortowane adresy."""
    token0, token1 = sort_tokens(to_cs(tokenA), to_cs(tokenB))
    factory = w3.eth.contract(address=to_cs(FACTORY_V3), abi=FACTORY_ABI)
    return factory.functions.getPool(token0, token1, FEE).call()

def read_slot0_price_token1_per_token0(pool_addr: str):
    """
    Zwraca P = price(token1 in token0) = (sqrtPriceX96^2)/2^192 jako float.
    Bez korekty na decimals – to robimy wyżej przy liczeniu ceny.
    """
    if not pool_addr or int(pool_addr, 16) == 0:
        return None
    try:
        pool = w3.eth.contract(address=to_cs(pool_addr), abi=POOL_ABI)
        sqrt_price_x96 = pool.functions.slot0().call()[0]
        P = (sqrt_price_x96 ** 2) / (2 ** 192)
        return float(P)
    except Exception:
        return None

_decimals_cache = {}
def get_decimals(token_addr: str) -> int:
    token_addr = to_cs(token_addr)
    if token_addr in _decimals_cache:
        return _decimals_cache[token_addr]
    c = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    d = c.functions.decimals().call()
    _decimals_cache[token_addr] = d
    return d

def get_token_balance(token_addr: str, holder: str) -> float:
    """Saldo tokena u danego holdera, w jednostkach 'ludzkich' (uwzględnia decimals)."""
    if not holder or int(holder, 16) == 0:
        return 0.0
    try:
        c = w3.eth.contract(address=to_cs(token_addr), abi=ERC20_ABI)
        d = get_decimals(token_addr)
        raw = c.functions.balanceOf(to_cs(holder)).call()
        return raw / (10 ** d)
    except Exception:
        return 0.0

def price_quote_per_base_v3(base: str, quote: str) -> float:
    """
    Cena: ile QUOTE za 1 BASE (np. USDC/KRS albo ETH/KRS) z puli V3.
    Uwzględnia odpowiednie odwrócenie i różnicę decimals.
    """
    pool = get_pool_addr(base, quote)
    P = read_slot0_price_token1_per_token0(pool)
    if P is None:
        return None

    base = to_cs(base); quote = to_cs(quote)
    token0, token1 = sort_tokens(base, quote)
    dec_base = get_decimals(base)
    dec_quote = get_decimals(quote)

    # P = token1/token0 (bez decimals). Cena QUOTE/BASE:
    # jeśli base=token0, quote=token1 => QUOTE/BASE = P * 10^(dec_quote - dec_base)
    # jeśli base=token1, quote=token0 => QUOTE/BASE = (1/P) * 10^(dec_quote - dec_base)
    scale = 10 ** (dec_quote - dec_base)
    if base == token0 and quote == token1:
        return float(P * scale)
    elif base == token1 and quote == token0:
        if P == 0:
            return None
        return float((1.0 / P) * scale)
    else:
        return None  # nie powinno się zdarzyć

def get_eth_pln():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=pln", timeout=15)
        return float(r.json()["ethereum"]["pln"])
    except Exception:
        return 0.0

def get_eth_usd():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=15)
        return float(r.json()["ethereum"]["usd"])
    except Exception:
        return 0.0

# --- Zbieranie danych ---
output = {}
pools = {}

# Adresy pul
pools["USDC"] = get_pool_addr(TOKEN_KRS, TOKEN_USDC)
pools["WETH"] = get_pool_addr(TOKEN_KRS, TOKEN_WETH)

# Ceny bezpośrednio z V3
price_usdc_per_krs = price_quote_per_base_v3(TOKEN_KRS, TOKEN_USDC)   # USDC za 1 KRS
price_eth_per_krs_direct = price_quote_per_base_v3(TOKEN_KRS, TOKEN_WETH)  # ETH za 1 KRS (direct)

# Kursy rynkowe ETH
eth_pln = get_eth_pln()
eth_usd = get_eth_usd()

# Cena ETH/KRS via USDC (pośrednio)
price_eth_per_krs_via_usdc = None
if price_usdc_per_krs and eth_usd:
    price_eth_per_krs_via_usdc = price_usdc_per_krs / eth_usd

# Wypełnij stare pola dla kompatybilności + dodatkowe
output["USDC"] = round(price_usdc_per_krs, 8) if price_usdc_per_krs else 0.0
output["WETH"] = round(price_eth_per_krs_direct, 12) if price_eth_per_krs_direct else 0.0  # ETH za 1 KRS (direct)
output["WETH_viaUSDC"] = round(price_eth_per_krs_via_usdc, 12) if price_eth_per_krs_via_usdc else 0.0

# Różnica między direct a viaUSDC (do alertów)
diff_pct = 0.0
if price_eth_per_krs_direct and price_eth_per_krs_via_usdc:
    mid = (price_eth_per_krs_direct + price_eth_per_krs_via_usdc) / 2.0
    if mid > 0:
        diff_pct = abs(price_eth_per_krs_direct - price_eth_per_krs_via_usdc) / mid
output["diff_pct"] = round(diff_pct, 6)
output["prefer"] = "viaUSDC"  # sugerowana ścieżka do UX/kupna

# Tokeny w pulach
output["pool"] = {
    "address_usdc": pools["USDC"],
    "address_weth": pools["WETH"],
    "krs_usdc": get_token_balance(TOKEN_KRS, pools["USDC"]),
    "usdc": get_token_balance(TOKEN_USDC, pools["USDC"]),
    "krs_weth": get_token_balance(TOKEN_KRS, pools["WETH"]),
    "weth": get_token_balance(TOKEN_WETH, pools["WETH"])
}

# Kursy ETH
output["ETHPLN"] = eth_pln
output["ETHUSD"] = eth_usd

# --- Wartości puli (spójnie w USD/ETH/PLN) ---
# KRS wyceniamy po USDC/KRS gdy jest dostępny, inaczej po (WETH_direct * ETHUSD)
krs_usd_price = 0.0
if price_usdc_per_krs:
    krs_usd_price = price_usdc_per_krs
elif price_eth_per_krs_direct and eth_usd:
    krs_usd_price = price_eth_per_krs_direct * eth_usd

krs_usdc_val_usd = output["pool"]["krs_usdc"] * krs_usd_price
usdc_val_usd = output["pool"]["usdc"]  # USDC to ~1 USD
krs_weth_val_usd = output["pool"]["krs_weth"] * krs_usd_price
weth_val_usd = output["pool"]["weth"] * eth_usd

pool_usd = krs_usdc_val_usd + usdc_val_usd + krs_weth_val_usd + weth_val_usd
pool_eth = pool_usd / eth_usd if eth_usd else 0.0
pool_pln = pool_eth * eth_pln

output["pool"]["value_usd"] = round(pool_usd, 2)
output["pool"]["value_eth"] = round(pool_eth, 6)
output["pool"]["value_pln"] = round(pool_pln, 2)

# --- Zapis do kursy.json ---
with open("kursy.json", "w") as f:
    json.dump(output, f, indent=2)

# --- Log doby ---
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
try:
    with open("kursy_doba.json", "r") as f:
        log = json.load(f)
except Exception:
    log = []

log.append({"timestamp": now, **output})
log = log[-144:]
with open("kursy_doba.json", "w") as f:
    json.dump(log, f, indent=2)

if DEBUG:
    print(json.dumps(output, indent=2))
