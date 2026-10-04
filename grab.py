import asyncio
import json

from playwright.async_api import async_playwright

KA = ("149e9513", "/tl", "/fp", "kasada", "integrity", "kpsdk", "k.twitch")


async def main():
    out = {"hosts": {}, "kasada": [], "all_hosts_sorted": []}

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"))
        page = await ctx.new_page()
        hosts = {}

        async def on_resp(resp):
            try:
                url = resp.url
                host = url.split("/")[2] if "//" in url else ""
                hosts[host] = hosts.get(host, 0) + 1
                if any(k in url.lower() for k in KA):
                    sa = {}
                    try:
                        sa = await resp.server_addr() or {}
                    except Exception:
                        pass
                    out["kasada"].append({
                        "url": url[:220],
                        "status": resp.status,
                        "ip": sa.get("ipAddress"),
                        "fam": "ipv6" if ":" in (sa.get("ipAddress") or "") else "ipv4",
                        "kpsdk": {k: v[:40] for k, v in resp.headers.items()
                                  if k.lower().startswith("x-kpsdk")},
                    })
            except Exception:
                pass

        page.on("response", lambda r: asyncio.create_task(on_resp(r)))

        try:
            await page.goto("https://www.twitch.tv/signup",
                            wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            out["goto_error"] = str(e)[:200]

        await asyncio.sleep(18)

        # 页面内看看 p.js 是否初始化
        try:
            out["kpsdk_ready"] = await page.evaluate(
                "() => ({has: typeof window.KPSDK, ready: (window.KPSDK && window.KPSDK.isReady) ? window.KPSDK.isReady() : null})")
        except Exception as e:
            out["kpsdk_ready"] = str(e)[:120]

        await browser.close()

    out["hosts"] = hosts
    out["all_hosts_sorted"] = sorted(hosts.keys())
    print("=====GRAB_JSON_BEGIN=====")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("=====GRAB_JSON_END=====")


asyncio.run(main())
