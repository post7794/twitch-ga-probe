import asyncio
import json

from playwright.async_api import async_playwright


async def run(proxy, label):
    out = {"label": label, "kpsdk_req_headers": [], "kpsdk_resp_headers": [], "hosts": {}}
    async with async_playwright() as p:
        kw = {"channel": "chrome", "headless": True,
              "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            kw["proxy"] = {"server": proxy}
        b = await p.chromium.launch(**kw)
        ctx = await b.new_context()
        page = await ctx.new_page()

        def on_req(r):
            try:
                u = r.url
                h = r.headers
                hh = {k.lower(): v for k, v in h.items()}
                if "twitchcdn.net" in u:
                    out["hosts"]["twitchcdn"] = out["hosts"].get("twitchcdn", 0) + 1
                    kk = {k: v[:120] for k, v in hh.items() if k.startswith("x-kpsdk")}
                    if kk:
                        out["kpsdk_req_headers"].append({"u": u.split("?")[0].split("/")[-1], "h": kk})
                else:
                    host = u.split("/")[2] if "//" in u else u
                    out["hosts"][host] = out["hosts"].get(host, 0) + 1
            except Exception:
                pass

        async def on_resp(r):
            try:
                if "twitchcdn.net" in r.url:
                    h = r.headers
                    kk = {k.lower(): v[:120] for k, v in h.items() if k.lower().startswith("x-kpsdk")}
                    if kk:
                        out["kpsdk_resp_headers"].append(
                            {"u": r.url.split("?")[0].split("/")[-1], "s": r.status, "h": kk})
            except Exception:
                pass

        page.on("request", on_req)
        page.on("response", lambda r: asyncio.create_task(on_resp(r)))
        try:
            await page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            out["goto_err"] = str(e)[:120]
        await asyncio.sleep(30)

        try:
            out["kpsdk"] = await page.evaluate(
                "() => ({has: typeof window.KPSDK, keys: (window.KPSDK&&typeof window.KPSDK==='object')?Object.keys(window.KPSDK):null})")
        except Exception as e:
            out["eval_err"] = str(e)[:100]
        await b.close()
    return out


async def main():
    out = {}
    out["warp"] = await run("http://127.0.0.1:8118", "warp")
    print("=====CTCD2_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====CTCD2_END=====")


asyncio.run(main())
