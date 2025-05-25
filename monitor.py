import json
from datetime import datetime
from get_pul_adress import TOKEN_BS, get_pool, read_slot0, invert

output = {}

print("\n🔍 Trwa pobieranie kursów KRS...")

for name, (tokenB, should_invert) in TOKEN_BS.items():
    print(f"\n🔍 Szukam puli KRS / {name}...")
    pool_address = get_pool("0x521e58970fBa0AEAF6DC9C2e994ec9e9CD71A070", tokenB)
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
log = log[-144:]  # ogranicz do 144 wpisów (co 10 minut = 24h)

with open("kursy_doba.json", "w") as f:
    json.dump(log, f, indent=2)

# Prosty terminalowy log
print("\n📊 Kursy końcowe:")
for name, val in output.items():
    print(f"{name}: {val} PLN")
