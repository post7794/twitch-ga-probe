import json
import socket
import ssl
import struct

SOCKS = ("127.0.0.1", 1080)

KA = "k.twitchcdn.net"
FP = "/149e9513-01fa-4fb0-aad4-566afd725d1b/2d206a39-8ed7-437e-a3be-862e0f06eea3/fp?x-kpsdk-v=j-1.2.825"


def socks5_connect(ip, port, timeout=12):
    s = socket.create_connection(SOCKS, timeout=timeout)
    s.sendall(b"\x05\x01\x00")
    r = s.recv(2)
    if r != b"\x05\x00":
        raise RuntimeError(f"greeting {r!r}")
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
    s = socks5_connect(ip, 443)
    try:
        ss = ssl.create_default_context().wrap_socket(s, server_hostname=host)
    except Exception as e:
        s.close()
        return {"err": f"tls:{type(e).__name__}:{e}"}
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


def ipv4_to_nat64(ip):
    octs = socket.inet_aton(ip)
    return "64:ff9b::" + socket.inet_ntop(socket.AF_INET6, b"\x00" * 12 + octs)


def main():
    out = {}
    # NAT64 of cloudflare 1.1.1.1
    out["nat64_1111"] = https("64:ff9b::101:101", "cloudflare.com", "/cdn-cgi/trace")
    # direct IPv6 to cloudflare DNS
    out["v6_2606"] = https("2606:4700:4700::1111", "cloudflare.com", "/cdn-cgi/trace")
    # NAT64 of a known IPv4-only echo
    out["nat64_ipify"] = https(ipv4_to_nat64("104.26.12.205"), "api.ipify.org", "/")
    # Kasada /fp over NAT64 of fastly ipv4
    for ipv4 in ("146.75.106.167", "151.101.2.167"):
        out[f"nat64_fp_{ipv4}"] = https(ipv4_to_nat64(ipv4), KA, FP)
    # Kasada /fp over plain IPv4 via socks
    out["v4_fp_146_75_106_167"] = https("146.75.106.167", KA, FP)
    print("=====NAT_BEGIN=====")
    print(json.dumps(out, ensure_ascii=True, indent=2))
    print("=====NAT_END=====")


main()
