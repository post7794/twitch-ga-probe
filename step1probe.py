import asyncio
import json
import uuid

from playwright.async_api import async_playwright

CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

FETCH_JS = """
async (payload) => {
    const r = await fetch('https://passport.twitch.tv/protected_register', {
        method: 'POST',
        headers: {'Content-Type': 'text/plain;charset=UTF-8'},
        credentials: 'include',
        body: JSON.stringify(payload),
    });
    const text = await r.text();
    let body = null; try { body = JSON.parse(text); } catch(e) {}
    return {status: r.status, body, text: text.slice(0, 220)};
}
"""


async def attempt(proxy, label):
    out = {"label": label, "v": None, "ct": None, "cd": None, "reqs": []}
    async with async_playwright() as p:
        kw = {"channel": "chrome", "headless": True,
              "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            kw["proxy"] = {"server": proxy}
        b = await p.chromium.launch(**kw)
        ctx = await b.new_context()
        page = await ctx.new_page()
        cap = {"ct": "", "cd": ""}

        def on_req(r):
            try:
                v = r.headers.get("x-kpsdk-v")
                if v:
                    out["v"] = v
                c = r.headers.get("x-kpsdk-cd")
                if c:
                    cap["cd"] = c
            except Exception:
                pass

        async def on_resp(r):
            try:
                if "twitchcdn.net" in r.url:
                    st = r.status
                    p = r.url.split("?")[0].split("/")[-1]
                    hdr = [h for h in r.headers if h.lower().startswith("x-kpsdk")]
                    out["reqs"].append(f"{p}:{st}")
                if "/tl" in r.url and r.headers.get("x-kpsdk-ct"):
                    cap["ct"] = r.headers.get("x-kpsdk-ct")
            except Exception:
                pass

        page.on("request", on_req)
        page.on("response", lambda r: asyncio.create_task(on_resp(r)))
        try:
            await page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            out["goto_err"] = str(e)[:120]

        for _ in range(30):
            await asyncio.sleep(1)
            if cap["cd"]:
                break
        out["ct"] = (cap["ct"][:36] + "...") if cap["ct"] else None
        out["cd"] = "有" if cap["cd"] else "(none)"
        try:
            out["kpsdk"] = await page.evaluate(
                "() => ({ready: (window.KPSDK&&window.KPSDK.isReady)?window.KPSDK.isReady():null})")
        except Exception:
            pass

        rnd = uuid.uuid4().hex[:10]
        payload = {"username": f"probe{rnd}", "password": "Aa1!" + uuid.uuid4().hex[:12],
                   "email": f"probe{rnd}@example.com",
                   "birthday": {"day": 15, "month": 6, "year": 1995, "isOver18": True},
                   "email_verification_enabled": False, "client_id": CLIENT_ID,
                   "is_password_guide": "nist"}
        try:
            out["step1"] = await page.evaluate(FETCH_JS, payload)
        except Exception as e:
            out["step1_err"] = str(e)[:150]
        await b.close()
    return out


async def main():
    out = {}
    out["warp"] = await attempt("http://127.0.0.1:8118", "warp")
    out["direct"] = await attempt(None, "direct")
    print("=====S1_BEGIN=====")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("=====S1_END=====")


asyncio.run(main())
