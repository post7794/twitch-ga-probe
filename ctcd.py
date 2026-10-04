import asyncio
import json

from playwright.async_api import async_playwright

HOOK = r"""
(() => {
  window.__k = {hdr: [], fetch: [], kpsdk: null};
  function rec(k, v, src) {
    try {
      if (/^x-kpsdk/i.test(k)) window.__k.hdr.push({k: k, v: String(v).slice(0, 100), src: src, st: (new Error()).stack});
    } catch(e) {}
  }
  try {
    const o = XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.setRequestHeader = function(k, v){ rec(k, v, 'xhr.setRequestHeader'); return o.apply(this, arguments); };
  } catch(e) {}
  try {
    const hs = Headers.prototype.set;
    Headers.prototype.set = function(k, v){ rec(k, v, 'Headers.set'); return hs.apply(this, arguments); };
  } catch(e) {}
  try {
    const ha = Headers.prototype.append;
    Headers.prototype.append = function(k, v){ rec(k, v, 'Headers.append'); return ha.apply(this, arguments); };
  } catch(e) {}
  try {
    const of = window.fetch;
    window.fetch = function(input, init){
      try {
        let u = '';
        try { u = (typeof input === 'string') ? input : (input && input.url) || ''; } catch(e) {}
        if (init && init.headers) {
          if (init.headers instanceof Headers) {
            init.headers.forEach((v, k) => { if (/^x-kpsdk/i.test(k)) rec(k, v, 'fetch.init.Headers'); });
          } else if (Array.isArray(init.headers)) {
            init.headers.forEach(p => { if (p && /^x-kpsdk/i.test(p[0])) rec(p[0], p[1], 'fetch.init.array'); });
          } else if (typeof init.headers === 'object') {
            for (const k in init.headers) if (/^x-kpsdk/i.test(k)) rec(k, init.headers[k], 'fetch.init.obj');
          }
        }
        if (u) window.__k.fetch.push(String(u).slice(0, 120));
      } catch(e) {}
      return of.apply(this, arguments);
    };
  } catch(e) {}
  // capture KPSDK surface when defined
  try {
    let _k = undefined;
    Object.defineProperty(window, 'KPSDK', {
      configurable: true,
      get(){ return _k; },
      set(v){
        _k = v;
        try {
          window.__k.kpsdk = {type: typeof v, keys: v ? Object.keys(v).slice(0, 60) : null};
        } catch(e) {}
      }
    });
  } catch(e) {}
})();
"""


async def run(proxy, label):
    out = {"label": label, "hdr": [], "kpsdk": None, "reqs": []}
    async with async_playwright() as p:
        kw = {"channel": "chrome", "headless": True,
              "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            kw["proxy"] = {"server": proxy}
        b = await p.chromium.launch(**kw)
        ctx = await b.new_context()
        await ctx.add_init_script(HOOK)
        page = await ctx.new_page()

        async def on_resp(r):
            try:
                if "twitchcdn.net" in r.url and ("/tl" in r.url or "/fp" in r.url or "/mfc" in r.url):
                    out["reqs"].append({"p": r.url.split("?")[0].split("/")[-1],
                                        "s": r.status,
                                        "ct": (r.headers.get("x-kpsdk-ct") or "")[:50],
                                        "st": (r.headers.get("x-kpsdk-st") or "")[:40],
                                        "cr": (r.headers.get("x-kpsdk-cr") or "")[:40]})
            except Exception:
                pass

        page.on("response", lambda r: asyncio.create_task(on_resp(r)))
        try:
            await page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            out["goto_err"] = str(e)[:120]
        await asyncio.sleep(25)

        try:
            k = await page.evaluate("() => window.__k")
            out["hdr"] = k.get("hdr", [])[:40]
            out["kpsdk"] = k.get("kpsdk")
            out["fetch"] = k.get("fetch", [])[:20]
        except Exception as e:
            out["eval_err"] = str(e)[:150]

        # try to expose KPSDK internals
        try:
            out["kpsdk_deep"] = await page.evaluate(
                """() => {
                    const K = window.KPSDK;
                    if (!K) return null;
                    const r = {keys: Object.keys(K)};
                    try { r.proto = Object.getOwnPropertyNames(Object.getPrototypeOf(K)); } catch(e){}
                    return r;
                }""")
        except Exception as e:
            out["deep_err"] = str(e)[:100]
        await b.close()
    return out


async def main():
    out = {}
    out["warp"] = await run("http://127.0.0.1:8118", "warp")
    print("=====CTCD_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====CTCD_END=====")


asyncio.run(main())
