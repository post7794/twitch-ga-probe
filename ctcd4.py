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

HOOK = r"""
(() => {
  window.__cds = [];
  const ojs = JSON.stringify;
  JSON.stringify = function(v, ...rest) {
    try {
      if (v && typeof v === 'object' && !Array.isArray(v) &&
          ('workTime' in v) && ('answers' in v)) {
        const copy = {};
        for (const k in v) { try { copy[k] = v[k]; } catch(e) { copy[k] = '<err>'; } }
        window.__cds.push({obj: copy, st: (new Error()).stack});
      }
    } catch(e) {}
    return ojs.apply(this, arguments);
  };
})();
"""


async def run(proxy, label):
    out = {"label": label, "cds": [], "step1": None}
    async with async_playwright() as p:
        kw = {"channel": "chrome", "headless": True,
              "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            kw["proxy"] = {"server": proxy}
        b = await p.chromium.launch(**kw)
        ctx = await b.new_context()
        await ctx.add_init_script(HOOK)
        page = await ctx.new_page()
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
            out["step1"] = await page.evaluate(FETCH_JS, payload)
        except Exception as e:
            out["step1_err"] = str(e)[:150]
        await asyncio.sleep(1)
        try:
            cds = await page.evaluate("() => window.__cds")
            # keep only a few with stacks
            out["cds"] = [{"obj": c["obj"], "st": (c.get("st") or "")[:900]} for c in cds[:4]]
        except Exception as e:
            out["eval_err"] = str(e)[:120]
        await b.close()
    return out


async def main():
    out = {}
    out["warp"] = await run("http://127.0.0.1:8118", "warp")
    print("=====CTCD4_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====CTCD4_END=====")


asyncio.run(main())
