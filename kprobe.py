import json
import socket
import ssl
import struct
import urllib.request

KA = "k.twitchcdn.net"
CID = "149e9513-01fa-4fb0-aad4-566afd725d1b"
HASH = "2d206a39-8ed7-437e-a3be-862e0f06eea3"
FP = f"/{CID}/{HASH}/fp?x-kpsdk-v=j-1.2.825"
PJS = f"/{CID}/{HASH}/p.js"
SOCKS = ("127.0.0.1", 1080)


def doh(name, rtype):
    try:
        url = f"https://cloudflare-dns.com/dns-query?name={name}&type={rtype}"
        req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            j = json.loads(r.read().decode())
        return {"status": j.get("Status"),
                "answers": [a["data"] for a in j.get("Answer", [])]}
    except Exception as e:
        return {"err": f"{type(e).__name__}:{e}"}


def first_addr(doh_res, want_aaaa):
    for a in doh_res.get("answers", []):
        if want_aaaa and ":" in a:
            return a
        if not want_aaaa and ":" not in a and any(c.isdigit() for c in a) and "." in a:
            return a
    return None


def socks5(ip, port, timeout=12):
    s = socket.create_connection(SOCKS, timeout=timeout)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00":
        raise RuntimeError("socks greeting")
    if ":" in ip:
        req = b"\x05\x01\x00\x04" + socket.inet_pton(socket.AF_INET6, ip) + struct.pack("!H", port)
    else:
        req = b"\x05\x01\x00\x01" + socket.inet_aton(ip) + struct.pack("!H", port)
    s.sendall(req)
    resp = s.recv(10)
    if len(resp) < 2 or resp[1] != 0:
        raise RuntimeError(f"socks rc={resp[1] if len(resp) > 1 else '?'}")
    return s


def https_via_socks(ip, host, path, timeout=15):
    s = socks5(ip, 443)
    ss = ssl.create_default_context().wrap_socket(s, server_hostname=host)
    req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\n"
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
    return {"status": lines[0], "len": len(data)}


def https_direct(host, path):
    try:
        infos = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ip = infos[0][4][0]
        s = socket.create_connection((ip, 443), timeout=12)
        r = https_via_socks_ip(s, host, path)
        r["ip"] = ip
        return r
    except Exception as e:
        return {"err": f"{type(e).__name__}:{e}"}


def https_via_socks_ip(sock, host, path):
    ss = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
    req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\n"
           f"Accept: */*\r\nConnection: close\r\n\r\n")
    ss.sendall(req.encode())
    data = b""
    while True:
        ch = ss.recv(8192)
        if not ch:
            break
        data += ch
    head = data.split(b"\r\n\r\n")[0].decode("utf-8", "replace")
    return {"status": head.split("\r\n")[0], "len": len(data)}


def probe(name, target, path):
    out = {}
    try:
        out["direct"] = https_direct(target, path)
    except Exception as e:
        out["direct"] = {"err": str(e)}
    return out


def main():
    r = {}
    r["doh_ka_A"] = doh(KA, "A")
    r["doh_ka_AAAA"] = doh(KA, "AAAA")
    for h in ("www.twitch.tv", "passport.twitch.tv", "gql.twitch.tv",
              "assets.twitch.tv", "static-cdn.jtvnw.net", "k.twitchcdn.net",
              "client-integrity.twitch.tv", "api6.ipify.org"):
        r[f"doh_{h}_AAAA"] = doh(h, "AAAA")

    a_ip = first_addr(r["doh_ka_A"], False)
    aaaa_ip = first_addr(r["doh_ka_AAAA"], True)
    r["ka_A_ip"] = a_ip
    r["ka_AAAA_ip"] = aaaa_ip

    # direct
    try:
        r["direct_fp"] = https_direct(KA, FP)
        r["direct_pjs"] = https_direct(KA, PJS)
    except Exception as e:
        r["direct_err"] = str(e)

    # via WARP socks, forced v4
    if a_ip:
        try:
            r["socks44_fp"] = https_via_socks(a_ip, KA, FP)
        except Exception as e:
            r["socks44_fp"] = {"err": f"{type(e).__name__}:{e}"}
        try:
            r["socks44_pjs"] = https_via_socks(a_ip, KA, PJS)
        except Exception as e:
            r["socks44_pjs"] = {"err": f"{type(e).__name__}:{e}"}
    # via WARP socks, forced v6
    if aaaa_ip:
        try:
            r["socks66_fp"] = https_via_socks(aaaa_ip, KA, FP)
        except Exception as e:
            r["socks66_fp"] = {"err": f"{type(e).__name__}:{e}"}
        try:
            r["socks66_pjs"] = https_via_socks(aaaa_ip, KA, PJS)
        except Exception as e:
            r["socks66_pjs"] = {"err": f"{type(e).__name__}:{e}"}
    else:
        r["socks66_fp"] = "no AAAA for k.twitchcdn.net"

    print("=====KPROBE_BEGIN=====")
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print("=====KPROBE_END=====")


main()
