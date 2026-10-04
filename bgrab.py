import asyncio
import json

from playwright.async_api import async_playwright

CID = "149e9513-01fa-4fb0-aad4-566afd725d1b"
HASH = "2d206a39-8ed7-437e-a3be-862e0f06eea3"
FP = f"https://k.twitchcdn.net/{CID}/{HASH}/fp?x-kpsdk-v=j-1.2.825"


async def grab(proxy, label):
    res = {"label": label, "kasada": [], "hosts": {}}
    async with async_playwright() as p:
        kw = {"channel": "chrome", "headless": True,
              "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            kw["proxy"] = {"server": proxy}
        b = await p.chromium.launch(**kw)
        ctx = await b.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"))
        page = await ctx.new_page()

        async def on_resp(r):
            try:
                if "twitchcdn.net" in r.url or "kasada" in r.url.lower():
                    sa = {}
                    try:
                        sa = await r.server_addr() or {}
                    except Exception:
                        pass
                    res["kasada"].append({"u": r.url.split("?")[0][-90:],
                                          "q": r.url.split("?", 1)[1][:30] if "?" in r.url else "",
                                          "s": r.status, "ip": sa.get("ipAddress")})
                else:
                    h = r.url.split("/")[2] if "//" in r.url else ""
                    res["hosts"][h] = res["hosts"].get(h, 0) + 1
            except Exception:
                pass

        page.on("response", lambda r: asyncio.create_task(on_resp(r)))
        try:
            await page.goto("https://www.twitch.tv/signup",
                            wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            res["goto_err"] = str(e)[:150]
        await asyncio.sleep(20)

        # direct JS fetch in page context to the /fp endpoint
        try:
            r = await page.evaluate(
                """async (u) => {
                    try {
                        const resp = await fetch(u, {credentials:'include'});
                        return {status: resp.status};
                    } catch(e) { return {error: String(e)}; }
                }""", FP)
            res["js_fetch_fp"] = r
        except Exception as e:
            res["js_fetch_fp"] = {"error": str(e)[:120]}

        # raw curl-like fetch of /fp from page origin
        await b.close()
    return res


async def main():
    out = {}
    out["direct"] = await grab(None, "direct")
    out["warp"] = await grab("http://127.0.0.1:8118", "warp")
    print("=====BG_BEGIN=====")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("=====BG_END=====")


asyncio.run(main())
