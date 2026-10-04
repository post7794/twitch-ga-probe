import json
import socket
import ssl
import struct

SOCKS = ("127.0.0.1", 1080)
KA = "k.twitchcdn.net"
CID = "149e9513-01fa-4fb0-aad4-566afd725d1b"
H = "2d206a39-8ed7-437e-a3be-862e0f06eea3"
FP = f"/{CID}/{H}/fp?x-kpsdk-v=j-1.2.825"
PJS = f"/{CID}/{H}/p.js"

FASTLY_V6 = [
    "2a04:4e42:7b::313",
    "2a04:4e42::313",
    "2a04:4e42:200::313",
    "2a04:4e42:600::313",
    "2a04:4e42:400::313",
]


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
    hdrs = [h for h in head.split("\r\n")[1:] if h.lower().startswith(("x-kpsdk", "x-served", "via", "x-cache"))]
    return {"status": head.split("\r\n")[0], "len": len(data), "hdr": hdrs}


def main():
    out = {}
    for v6 in FASTLY_V6:
        out[f"v6_{v6}_pjs"] = https(v6, KA, PJS)
        out[f"v6_{v6}_fp"] = https(v6, KA, FP)
    print("=====F6_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====F6_END=====")


main()
