import asyncio
import json
import os
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

EXIT_JS = """
async () => {
    try {
        const r = await fetch('https://cloudflare.com/cdn-cgi/trace');
        const t = await r.text();
        const d = {};
        t.split('\\n').forEach(l => { const i = l.indexOf('='); if (i > 0) d[l.slice(0,i)] = l.slice(i+1); });
        return {ip: d.ip, loc: d.loc, colo: d.colo, warp: d.warp};
    } catch(e) { return {error: String(e)}; }
}
"""


async def main():
    proxy = os.getenv("PROXY") or None
    label = os.getenv("LABEL", "?")
    out = {"label": label, "proxy": proxy}
    async with async_playwright() as p:
        kw = {"channel": "chrome", "headless": True,
              "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            kw["proxy"] = {"server": proxy}
        b = await p.chromium.launch(**kw)
        ctx = await b.new_context()
        page = await ctx.new_page()
        try:
            await page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            out["goto_err"] = str(e)[:120]
        await asyncio.sleep(25)
        try:
            out["egress"] = await page.evaluate(EXIT_JS)
        except Exception as e:
            out["egress_err"] = str(e)[:120]
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
    print("=====EG_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====EG_END=====")


asyncio.run(main())
