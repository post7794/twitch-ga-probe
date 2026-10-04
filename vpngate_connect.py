import os
import sys

sys.path.insert(0, "src")
os.environ.setdefault("LOGURU_LEVEL", "INFO")

import vpngate as vg

countries = [c for c in (os.getenv("VN_COUNTRIES") or "JP,KR,TH,TW").split(",") if c.strip()]
try:
    ns = vg.fetch_nodes(100, countries)
    ns = vg.speed_test(ns)
except Exception as e:
    print("fetch/speed failed:", e)
    sys.exit(2)

print("candidates:", len(ns), flush=True)
ok = False
for n in ns[:8]:
    print("try", n.get("country"), n.get("ip"), flush=True)
    try:
        r = vg.connect(n, 60, vg._DEFAULT_BYPASS_HOSTS, False, True)
    except Exception as e:
        r = (False, f"{type(e).__name__}:{e}")
    print("result", r, flush=True)
    if r[0]:
        ok = True
        print("CONNECTED", n.get("ip"), r[1], flush=True)
        break
    vg.disconnect()

print("OK" if ok else "FAILED", flush=True)
