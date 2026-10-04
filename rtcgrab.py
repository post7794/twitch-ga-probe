import asyncio
import json

from playwright.async_api import async_playwright

HOOK = r"""
(() => {
  window.__probe = {rtc: [], fetch: [], xhr: [], ws: [], beacon: []};
  try {
    const O = window.RTCPeerConnection || window.webkitRTCPeerConnection;
    if (O) {
      function P(cfg, ...rest) {
        try {
          const pc = new O(cfg, ...rest);
          window.__probe.rtc.push({cfg: JSON.stringify(cfg || {}), stack: (new Error()).stack || ''});
          const co = pc.createOffer && pc.createOffer.bind(pc);
          if (co) pc.createOffer = function(...a){ window.__probe.rtc.push({ev:'createOffer'}); return co(...a); };
          const sl = pc.setLocalDescription && pc.setLocalDescription.bind(pc);
          if (sl) pc.setLocalDescription = function(...a){ window.__probe.rtc.push({ev:'setLocalDescription'}); return sl(...a); };
          pc.addEventListener('icecandidate', (e) => {
            try {
              window.__probe.rtc.push({ev:'icecandidate', cand: e.candidate ? e.candidate.candidate : null,
                ip: e.candidate && e.candidate.address ? e.candidate.address : null});
            } catch(x){}
          });
          return pc;
        } catch(e) { window.__probe.rtc.push({err: String(e)}); throw e; }
      }
      P.prototype = O.prototype;
      window.RTCPeerConnection = P;
      window.webkitRTCPeerConnection = P;
    }
  } catch(e) {}
  try {
    const of = window.fetch;
    window.fetch = function(...a){
      try { window.__probe.fetch.push(String(a[0]).slice(0,160)); } catch(x){}
      return of.apply(this, a);
    };
  } catch(e) {}
  try {
    const oo = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, u, ...r){
      try { window.__probe.xhr.push(m+' '+String(u).slice(0,160)); } catch(x){}
      return oo.call(this, m, u, ...r);
    };
  } catch(e) {}
  try {
    const ow = window.WebSocket;
    window.WebSocket = function(u, ...r){ try { window.__probe.ws.push(String(u).slice(0,160)); } catch(x){} return new ow(u, ...r); };
    window.WebSocket.prototype = ow.prototype;
  } catch(e) {}
  try {
    const ob = navigator.sendBeacon && navigator.sendBeacon.bind(navigator);
    if (ob) navigator.sendBeacon = function(u, d){ try { window.__probe.beacon.push(String(u).slice(0,160)); } catch(x){} return ob(u, d); };
  } catch(e) {}
})();
"""


async def run(proxy, label):
    out = {"label": label, "reqs": [], "rtc": [], "fetch": [], "xhr": []}
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
                u = r.url
                if any(k in u for k in ("twitchcdn.net", "kasada", "integrity", "passport")):
                    sa = {}
                    try:
                        sa = await r.server_addr() or {}
                    except Exception:
                        pass
                    out["reqs"].append({"u": u.split("?")[0][-70:],
                                        "q": (u.split("?", 1)[1][:36] if "?" in u else ""),
                                        "s": r.status, "ip": sa.get("ipAddress"),
                                        "kpsdk": [h for h in r.headers if h.lower().startswith("x-kpsdk")]})
            except Exception:
                pass

        page.on("response", lambda r: asyncio.create_task(on_resp(r)))
        try:
            await page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            out["goto_err"] = str(e)[:150]
        await asyncio.sleep(22)
        try:
            pr = await page.evaluate("() => window.__probe")
            out["rtc"] = pr.get("rtc", [])[:20]
            out["fetch"] = [x for x in pr.get("fetch", []) if "twitchcdn" in x or "kasada" in x][:30]
            out["xhr"] = [x for x in pr.get("xhr", []) if "twitchcdn" in x or "kasada" in x][:30]
            out["kpsdk"] = await page.evaluate(
                "() => ({has: typeof window.KPSDK, ready: (window.KPSDK&&window.KPSDK.isReady)?window.KPSDK.isReady():null})")
        except Exception as e:
            out["eval_err"] = str(e)[:150]
        await b.close()
    return out


async def main():
    out = {}
    out["direct"] = await run(None, "direct")
    out["warp"] = await run("http://127.0.0.1:8118", "warp")
    print("=====RTC_BEGIN=====")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("=====RTC_END=====")


asyncio.run(main())
