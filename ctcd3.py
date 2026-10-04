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
    return {status: r.status, body};
}
"""


async def run(proxy, label):
    out = {"label": label, "steps": [], "all_kpsdk": []}
    async with async_playwright() as p:
        kw = {"channel": "chrome", "headless": True,
              "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            kw["proxy"] = {"server": proxy}
        b = await p.chromium.launch(**kw)
        ctx = await b.new_context()
        page = await ctx.new_page()
        rec = []

        def on_req(r):
            try:
                h = {k.lower(): v for k, v in r.headers.items() if k.lower().startswith("x-kpsdk")}
                if h:
                    rec.append({"phase": "pre", "url": r.url.split("?")[0][-60:],
                                "host": r.url.split("/")[2], "h": {k: str(v) for k, v in h.items()}})
            except Exception:
                pass

        page.on("request", on_req)
        try:
            await page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            out["goto_err"] = str(e)[:120]
        await asyncio.sleep(25)

        rnd = uuid.uuid4().hex[:10]
        payload = {"username": f"probe{rnd}", "password": "Aa1!" + uuid.uuid4().hex[:12],
                   "email": f"probe{rnd}@example.com",
                   "birthday": {"day": 15, "month": 6, "year": 1995, "isOver18": True},
                   "email_verification_enabled": False, "client_id": CLIENT_ID,
                   "is_password_guide": "nist"}
        try:
            r = await page.evaluate(FETCH_JS, payload)
            out["step1"] = r
        except Exception as e:
            out["step1_err"] = str(e)[:150]
        await asyncio.sleep(2)
        out["all_kpsdk"] = rec
        try:
            out["cookies"] = await page.evaluate("() => document.cookie")
        except Exception:
            pass
        await b.close()
    return out


async def main():
    out = {}
    out["warp"] = await run("http://127.0.0.1:8118", "warp")
    print("=====CTCD3_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====CTCD3_END=====")


asyncio.run(main())
