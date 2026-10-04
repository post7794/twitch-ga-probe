import asyncio
import json
import os

from playwright.async_api import async_playwright


async def main():
    proxy = os.getenv("PROXY") or None
    out = {"hosts": {}, "rows": []}
    async with async_playwright() as p:
        kw = {"channel": "chrome", "headless": True,
              "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            kw["proxy"] = {"server": proxy}
        b = await p.chromium.launch(**kw)
        ctx = await b.new_context()
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)
        await cdp.send("Network.enable")
        rows = []

        def on_req(params):
            try:
                req = params.get("request") or {}
                url = req.get("url") or ""
                if url.startswith("data:") or url.startswith("blob:"):
                    return
                host = url.split("/")[2] if "//" in url else url.split("/")[0]
                out["hosts"][host] = out["hosts"].get(host, 0) + 1
                rows.append({"m": req.get("method"), "u": url.split("?")[0][:110], "t": params.get("type")})
            except Exception:
                pass

        cdp.on("Network.requestWillBeSent", on_req)
        try:
            await page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            out["goto_err"] = str(e)[:120]
        await asyncio.sleep(30)
        out["rows"] = rows[:400]
        await b.close()
    print("=====NA_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====NA_END=====")


asyncio.run(main())
