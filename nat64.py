import json
import socket
import ssl
import struct

SOCKS = ("127.0.0.1", 1080)
KA = "k.twitchcdn.net"
FP = "/149e9513-01fa-4fb0-aad4-566afd725d1b/2d206a39-8ed7-437e-a3be-862e0f06eea3/fp?x-kpsdk-v=j-1.2.825"


def recvn(s, n):
    buf = b""
    while len(buf) < n:
        ch = s.recv(n - len(buf))
        if not ch:
            raise RuntimeError("eof")
        buf += ch
    return buf


def socks5_connect(ip, port, timeout=12):
    s = socket.create_connection(SOCKS, timeout=timeout)
    s.sendall(b"\x05\x01\x00")
    if recvn(s, 2) != b"\x05\x00":
        raise RuntimeError("greeting failed")
    if ":" in ip:
        req = b"\x05\x01\x00\x04" + socket.inet_pton(socket.AF_INET6, ip) + struct.pack("!H", port)
    else:
        req = b"\x05\x01\x00\x01" + socket.inet_aton(ip) + struct.pack("!H", port)
    s.sendall(req)
    head = recvn(s, 4)
    if head[1] != 0:
        raise RuntimeError(f"socks rc={head[1]}")
    atyp = head[3]
    if atyp == 1:
        recvn(s, 4)
    elif atyp == 4:
        recvn(s, 16)
    elif atyp == 3:
        recvn(s, recvn(s, 1)[0])
    recvn(s, 2)
    return s


def https(ip, host, path, timeout=15):
    try:
        s = socks5_connect(ip, 443, timeout)
    except Exception as e:
        return {"err": f"socks:{type(e).__name__}:{e}"}
    try:
        ss = ssl.create_default_context().wrap_socket(s, server_hostname=host)
    except Exception as e:
        s.close()
        return {"err": f"tls:{type(e).__name__}:{e}"}
    try:
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\n"
               f"Accept: */*\r\nConnection: close\r\n\r\n")
        ss.sendall(req.encode())
        data = b""
        while True:
            ch = ss.recv(8192)
            if not ch:
                break
            data += ch
    except Exception as e:
        return {"err": f"io:{type(e).__name__}:{e}"}
    head = data.split(b"\r\n\r\n")[0].decode("utf-8", "replace")
    body = data.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in data else b""
    return {"status": head.split("\r\n")[0], "len": len(data),
            "body": body[:180].decode("utf-8", "replace")}


def nat64(ip):
    return "64:ff9b::" + socket.inet_ntop(socket.AF_INET6, b"\x00" * 12 + socket.inet_aton(ip))


def main():
    out = {}
    out["v6_cloudflare_dns"] = https("2606:4700:4700::1111", "cloudflare.com", "/cdn-cgi/trace")
    out["nat64_of_1_1_1_1"] = https("64:ff9b::101:101", "cloudflare.com", "/cdn-cgi/trace")
    out["nat64_of_ipify"] = https(nat64("104.26.12.205"), "api.ipify.org", "/")
    for ipv4 in ("146.75.106.167", "151.101.2.167", "151.101.130.167"):
        out[f"v4_fp_{ipv4}"] = https(ipv4, KA, FP)
        out[f"nat64_fp_{ipv4}"] = https(nat64(ipv4), KA, FP)
    print("=====NAT_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====NAT_END=====")


main()
