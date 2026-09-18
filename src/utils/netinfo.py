"""
网络接口自检
用来确认热点所在的网段，避免过滤器写错导致一个包都抓不到。
"""
import re
import socket
import subprocess
from ipaddress import ip_address, ip_network


def list_local_ipv4():
    """列出本机所有 IPv4 地址（尽量少依赖）。"""
    ips = []

    # Windows: 解析 ipconfig 输出
    try:
        out = subprocess.run(
            ["ipconfig"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=10,
        ).stdout
        for m in re.finditer(r"IPv4[^:]*:\s*([0-9]{1,3}(?:\.[0-9]{1,3}){3})", out):
            ips.append(m.group(1))
    except Exception:
        pass

    # 兜底：用 hostname 解析
    if not ips:
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ips.append(info[4][0])
        except Exception:
            pass

    return sorted(set(ips))


def find_matching_ips(subnet_str):
    """返回落在指定网段内的本机地址。"""
    try:
        net = ip_network(subnet_str, strict=False)
    except Exception:
        return []
    matched = []
    for ip in list_local_ipv4():
        try:
            if ip_address(ip) in net:
                matched.append(ip)
        except Exception:
            continue
    return matched
