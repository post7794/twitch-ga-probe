import json
import socket
import ssl
import struct
import urllib.request

KA_HOST = "k.twitchcdn.net"
KA_PATH = "/149e9513-01fa-4fb0-aad4-566afd725d1b/2d206a39-8ed7-437e-a3be-862e0f06eea3/fp?x-kpsdk-v=j-1.2.825"
PJS_PATH = "/149e9513-01fa-4fb0-aad4-566afd725d1b/2d206a39-8ed7-437e-a3be-862e0f06eea3/p.js"

SOCKS = ("127.0.0.1", 1080)
HTTP_PROXY = ("127.0.0.1", 8118)


def doh(name, rtype):
    try:
        url = f"https://cloudflare-dns.com/dns-query?name={name}&type={rtype}"
        req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            j = json.loads(r.read().decode())
        return [a["data"] for a in j.get("Answer", []) if a.get("type") in (1, 28, 5)]
    except Exception as e:
        return f"ERR:{type(e).__name__}:{e}"


def socks5_connect(family, ip, port, timeout=12):
    s = socket.create_connection(SOCKS, timeout=timeout)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00":
        raise RuntimeError("socks greeting failed")
    if family == socket.AF_INET6:
        req = b"\x05\x01\x00\x04" + socket.inet_pton(socket.AF_INET6, ip) + struct.pack("!H", port)
    else:
        req = b"\x05\x01\x00\x01" + socket.inet_aton(ip) + struct.pack("!H", port)
    s.sendall(req)
    resp = s.recv(10)
    if len(resp) < 2 or resp[1] != 0:
        raise RuntimeError(f"socks connect rc={resp[1] if len(resp) > 1 else '?'}")
    return s


def tls_http(sock, host, path, timeout=15):
    ctx = ssl.create_default_context()
    ss = ctx.wrap_socket(sock, server_hostname=host)
    req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
           f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           f"(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36\r\n"
           f"Accept: */*\r\nConnection: close\r\n\r\n")
    ss.sendall(req.encode())
    data = b""
    while True:
        ch = ss.recv(8192)
        if not ch:
            break
        data += ch
    head = data.split(b"\r\n\r\n")[0].decode("utf-8", "replace")
    lines = head.split("\r\n")
    status = lines[0]
    hdrs = {k.lower(): v for k, v in (l.split(": ", 1) for l in lines[1:] if ": " in l)}
    return {"status": status, "kpsdk": {k: v[:40] for k, v in hdrs.items() if k.startswith("x-kpsdk")},
            "len": len(data)}


def via_socks(host, path, family):
    infos = socket.getaddrinfo(host, 443, family, socket.SOCK_STREAM)
    ip = infos[0][4][0]
    try:
        s = socks5_connect(family, ip, 443)
        r = tls_http(s, host, path)
        r["used_ip"] = ip
        r["family"] = "ipv6" if ":" in ip else "ipv4"
        return r
    except Exception as e:
        return {"used_ip": ip, "family": "ipv6" if ":" in ip else "ipv4",
                "error": f"{type(e).__name__}:{e}"}


def direct(host, path):
    try:
        infos = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        # prefer ipv4-first like default
        ip = infos[0][4][0]
        s = socket.create_connection((ip, 443), timeout=12)
        r = tls_http(s, host, path)
        r["used_ip"] = ip
        return r
    except Exception as e:
        return {"error": f"{type(e).__name__}:{e}"}


def main():
    out = {}
    out["doh_pjs"] = {"A": doh("k.twitchcdn.net", "A"), "AAAA": doh("k.twitchcdn.net", "AAAA")}
    out["doh_twitch"] = {h: {"AAAA": doh(h, "AAAA")}
                         for h in ("www.twitch.tv", "passport.twitch.tv", "gql.twitch.tv",
                                   "assets.twitch.tv", "static-cdn.jtvnw.net")}

    out["direct_fp"] = direct(KA_HOST, KA_PATH)
    out["direct_pjs"] = direct(KA_HOST, PJS_PATH)
    out["socks_v4_fp"] = via_socks(KA_HOST, KA_PATH, socket.AF_INET)
    out["socks_v6_fp"] = via_socks(KA_HOST, KA_PATH, socket.AF_INET6)
    out["socks_v4_pjs"] = via_socks(KA_HOST, PJS_PATH, socket.AF_INET)
    out["socks_v6_pjs"] = via_socks(KA_HOST, PJS_PATH, socket.AF_INET6)

    print("=====KPROBE_BEGIN=====")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("=====KPROBE_END=====")


main()
