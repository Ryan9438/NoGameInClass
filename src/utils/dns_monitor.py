"""
DNS 查询劫持器
从 DNS 请求包里提取客户端正在查的域名
然后拿去跟游戏域名库对线
"""
import struct

def parse_dns_query(packet):
    """从 UDP 包 payload 里抠出 DNS 查询的域名
    返回 (domain_name, is_response) 或 None
    只提取 A/AAAA 查询里的 QNAME
    """
    payload = bytes(packet.payload)
    if not payload or len(payload) < 12:
        return None

    udp = getattr(packet, 'udp', None)
    if not udp:
        return None

    # 只处理 DNS（端口 53）
    if udp.src_port != 53 and udp.dst_port != 53:
        return None

    is_response = (payload[2] >> 7) & 1
    if is_response:
        # 这是 DNS 响应，我们暂时不用
        # 未来可以从响应里提取解析出的 IP 地址
        return None

    # 从第 12 字节开始解析 QNAME
    offset = 12
    labels = []
    
    while offset < len(payload):
        length = payload[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0:  # 压缩指针，跳过
            offset += 2
            break
        offset += 1
        if offset + length > len(payload):
            return None
        try:
            label = payload[offset:offset + length].decode('ascii', errors='ignore')
        except:
            return None
        if not label:
            return None
        labels.append(label)
        offset += length

    if not labels:
        return None

    return '.'.join(labels).lower()
