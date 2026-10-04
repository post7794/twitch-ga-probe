#!/usr/bin/env python3
# probe.py - GA runner 上强制 IPv4/IPv6 分别探测 Twitch / Kasada 可达性
# 只用标准库，避免安装依赖。输出结构化，便于在 Actions 日志里读。
import json
import socket
import ssl
import time
import uuid

CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

TARGETS = [
    "www.twitch.tv", "twitch.tv", "passport.twitch.tv", "gql.twitch.tv",
    "client-integrity.twitch.tv", "k.twitch.tv", "assets.twitch.tv",
    "static.twitch.tv", "api.ipify.org", "api6.ipify.org",
    "ipv4only.arpa", "ipv6.google.com",
]
FAM = {"v4": socket.AF_INET, "v6": socket.AF_INET6}


def dns(host, fam):
    try:
        infos = socket.getaddrinfo(host, 443, FAM[fam], socket.SOCK_STREAM)
        return sorted({i[4][0] for i in infos})
    except Exception as e:
        return f"ERR:{type(e).__name__}:{e}"


def tcp(host, fam, port=443, timeout=6):
    famc = FAM[fam]
    try:
        infos = socket.getaddrinfo(host, port, famc, socket.SOCK_STREAM)
    except Exception as e:
        return {"ok": False, "dns_err": f"{type(e).__name__}:{e}"}
    ip = infos[0][4][0]
    s = socket.socket(famc, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.connect((ip, port))
        return {"ok": True, "ip": ip, "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "ip": ip, "err": f"{type(e).__name__}:{e}"}
    finally:
        try:
            s.close()
        except Exception:
            pass


def https(host, path, fam, method="GET", body=b"", headers=None, timeout=10):
    famc = FAM[fam]
    try:
        infos = socket.getaddrinfo(host, 443, famc, socket.SOCK_STREAM)
    except Exception as e:
        return {"ok": False, "dns_err": f"{type(e).__name__}:{e}"}
    ip = infos[0][4][0]
    try:
        raw = socket.socket(famc, socket.SOCK_STREAM)
        raw.settimeout(timeout)
        raw.connect((ip, 443))
        ss = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
    except Exception as e:
        return {"ok": False, "ip": ip, "err": f"{type(e).__name__}:{e}"}
    try:
        req = [f"{method} {path} HTTP/1.1", f"Host: {host}", "Connection: close",
               f"User-Agent: {UA}"]
        for k, v in (headers or {}).items():
            req.append(f"{k}: {v}")
        if body:
            req.append(f"Content-Length: {len(body)}")
        req.append("")
        req.append("")
        ss.sendall("\r\n".join(req).encode() + body)
        data = b""
        while True:
            ch = ss.recv(8192)
            if not ch:
                break
            data += ch
    except Exception as e:
        return {"ok": False, "ip": ip, "err": f"recv:{type(e).__name__}:{e}"}
    finally:
        try:
            ss.close()
        except Exception:
            pass
    head, _, rest = data.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    status = lines[0].decode(errors="replace")
    hdrs = {}
    for line in lines[1:]:
        if b":" in line:
            k, v = line.split(b":", 1)
            hdrs[k.decode().strip().lower()] = v.decode(errors="replace").strip()
    kpsdk = {k: v for k, v in hdrs.items() if k.startswith("x-kpsdk")}
    out = {"ok": True, "ip": ip, "status": status, "body_len": len(rest), "kpsdk": kpsdk}
    # 尝试从 body 里抽取 error_code / token 长度
    try:
        j = json.loads(rest.decode("utf-8", "replace"))
        if isinstance(j, dict):
            if "error_code" in j:
                out["error_code"] = j.get("error_code")
                out["error"] = str(j.get("error"))[:120]
            if "token" in j:
                out["token_len"] = len(j.get("token") or "")
    except Exception:
        out["body_head"] = rest[:160].decode("utf-8", "replace")
    return out


def main():
    report = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # 1) DNS A / AAAA
    report["dns"] = {h: {"A": dns(h, "v4"), "AAAA": dns(h, "v6")} for h in TARGETS}

    # 2) TCP 443 v4 / v6
    report["tcp443"] = {h: {"v4": tcp(h, "v4"), "v6": tcp(h, "v6")} for h in TARGETS}

    # 3) HTTPS 首页 v4 / v6
    report["https_home"] = {}
    for h in ("www.twitch.tv", "passport.twitch.tv", "gql.twitch.tv", "k.twitch.tv"):
        report["https_home"][h] = {
            "v4": https(h, "/", "v4"),
            "v6": https(h, "/", "v6"),
        }

    # 4) Kasada /integrity（gql.twitch.tv）v4 / v6
    dev = str(uuid.uuid4())
    integ_hdr = {"Client-ID": CLIENT_ID, "X-Device-Id": dev,
                 "Origin": "https://www.twitch.tv", "Referer": "https://www.twitch.tv/",
                 "Content-Type": "text/plain;charset=UTF-8"}
    report["kasada_integrity"] = {
        "v4": https("gql.twitch.tv", "/integrity", "v4", "POST", b"", integ_hdr),
        "v6": https("gql.twitch.tv", "/integrity", "v6", "POST", b"", integ_hdr),
    }

    # 5) step1 protected_register（占位邮箱，不建号）v4 / v6 —— 直接看 error_code(5025?)
    rnd = uuid.uuid4().hex[:10]
    payload = json.dumps({
        "username": f"probe{rnd}", "password": "Aa1!" + uuid.uuid4().hex[:12],
        "email": f"probe{rnd}@example.com",
        "birthday": {"day": 15, "month": 6, "year": 1995, "isOver18": True},
        "email_verification_enabled": False, "client_id": CLIENT_ID,
        "is_password_guide": "nist",
    }).encode()
    reg_hdr = {"Content-Type": "text/plain;charset=UTF-8",
               "Origin": "https://www.twitch.tv", "Referer": "https://www.twitch.tv/"}
    report["step1_register"] = {
        "v4": https("passport.twitch.tv", "/protected_register", "v4", "POST", payload, reg_hdr),
        "v6": https("passport.twitch.tv", "/protected_register", "v6", "POST", payload, reg_hdr),
    }

    out = json.dumps(report, ensure_ascii=False, indent=2)
    print("=====PROBE_JSON_BEGIN=====")
    print(out)
    print("=====PROBE_JSON_END=====")
    try:
        with open("probe-out.json", "w", encoding="utf-8") as f:
            f.write(out)
    except Exception:
        pass


if __name__ == "__main__":
    main()
