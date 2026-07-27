"""
TLS SNI 提取器
从 TLS ClientHello 的 SNI 扩展里抠出域名
很多游戏用 HTTPS，SNI 是明文的关键证据
"""
import struct


def extract_sni(packet):
    """从 TCP 包的 TLS ClientHello 里提取 SNI 域名
    返回域名或 None
    只抓 ClientHello（不是 ServerHello 或其他 TLS 消息）
    """
    tcp = getattr(packet, 'tcp', None)
    if not tcp:
        return None

    # 只检查 443 端口的流量
    if tcp.dst_port != 443:
        return None

    payload = bytes(packet.payload)
    if not payload or len(payload) < 5:
        return None

    offset = 0

    # TCP payload 可能包含多个 TLS 记录
    while offset + 5 <= len(payload):
        # TLS Record 格式:
        # ContentType (1 byte) | Version (2 bytes) | Length (2 bytes)
        content_type = payload[offset]
        
        if content_type not in (0x16, 0x17):  # 0x16 = Handshake, 0x17 = Application Data
            break

        # 跳过 TLS 版本检查 —— 实际流量中有各种魔改版本
        # 只要 ContentType 是 Handshake(0x16) 就尝试解析

        record_length = struct.unpack('!H', payload[offset+3:offset+5])[0]
        record_end = offset + 5 + record_length
        
        if record_end > len(payload):
            break

        if content_type == 0x16:  # Handshake
            handshake_data = payload[offset+5:record_end]
            sni = _parse_tls_handshake(handshake_data)
            if sni:
                return sni

        offset = record_end

    return None


def _parse_tls_handshake(data):
    """从 Handshake 消息里解析 ClientHello 的 SNI"""
    if len(data) < 4:
        return None

    # Handshake 类型
    handshake_type = data[0]
    if handshake_type != 0x01:  # 0x01 = ClientHello
        return None

    # Handshake 消息体长度 (3 bytes, big-endian, 不包括类型和长度自身)
    body_len = (data[1] << 16) | (data[2] << 8) | data[3]
    
    if body_len < 34 or body_len > len(data) - 4:
        return None

    body = data[4:4 + body_len]
    return _parse_client_hello(body)


def _parse_client_hello(body):
    """从 ClientHello 中提取 SNI"""
    offset = 0

    # 跳过 Protocol Version (2 bytes)
    if offset + 2 > len(body):
        return None
    offset += 2

    # 跳过 Random (32 bytes)
    if offset + 32 > len(body):
        return None
    offset += 32

    # 跳过 Session ID (长度可变)
    if offset + 1 > len(body):
        return None
    session_id_len = body[offset]
    offset += 1 + session_id_len

    # 跳过 Cipher Suites (长度可变)
    if offset + 2 > len(body):
        return None
    cipher_len = struct.unpack('!H', body[offset:offset+2])[0]
    offset += 2 + cipher_len

    # 跳过 Compression Methods (长度可变)
    if offset + 1 > len(body):
        return None
    comp_len = body[offset]
    offset += 1 + comp_len

    # 现在到 Extensions 了
    if offset + 2 > len(body):
        return None
    ext_total_len = struct.unpack('!H', body[offset:offset+2])[0]
    offset += 2

    if ext_total_len == 0 or offset + ext_total_len > len(body):
        return None

    # 遍历 Extension
    while offset + 4 <= len(body):
        ext_type = struct.unpack('!H', body[offset:offset+2])[0]
        ext_len = struct.unpack('!H', body[offset+2:offset+4])[0]
        offset += 4

        if ext_type == 0x0000:  # SNI Extension！
            return _parse_sni_extension(body[offset:offset+ext_len])

        offset += ext_len

    return None


def _parse_sni_extension(data):
    """从 SNI Extension 中提取 Server Name"""
    if len(data) < 3:
        return None

    # Server Name List 长度 (2 bytes)
    list_len = struct.unpack('!H', data[0:2])[0]
    if list_len < 3 or list_len > len(data) - 2:
        return None

    offset = 2
    while offset + 3 <= len(data):
        name_type = data[offset]
        name_len = struct.unpack('!H', data[offset+1:offset+3])[0]
        offset += 3

        if name_type == 0x00:  # host_name
            if offset + name_len <= len(data):
                try:
                    return data[offset:offset+name_len].decode('ascii').lower()
                except:
                    return None

        offset += name_len

    return None
