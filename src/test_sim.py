"""
NoGameInClass 模拟测试 —— 在 macOS 上也能测试制裁逻辑

用法: python src/main.py --test

会生成模拟的游戏流量包，看着制裁引擎怎么收拾它们
"""
import time
import random


class FakePacket:
    """模拟 PyDivert 的 Packet 对象"""

    class FakeIP:
        def __init__(self, src, dst):
            self.src_addr = src
            self.dst_addr = dst

    class FakeTCP:
        def __init__(self, src_port, dst_port):
            self.src_port = src_port
            self.dst_port = dst_port

    class FakeUDP:
        def __init__(self, src_port, dst_port):
            self.src_port = src_port
            self.dst_port = dst_port

    def __init__(self, src, dst, proto='tcp', sport=12345, dport=443, payload=b''):
        self.ipv4 = self.FakeIP(src, dst)
        self.is_inbound = False
        self.payload = payload
        if proto == 'tcp':
            self.tcp = self.FakeTCP(sport, dport)
            self.udp = None
        else:
            self.udp = self.FakeUDP(sport, dport)
            self.tcp = None


def build_dns_query(src_ip, domain):
    """构造一个模拟的 DNS 查询包"""
    # DNS 查询格式
    labels = domain.split('.')
    qname = b''
    for label in labels:
        qname += bytes([len(label)]) + label.encode()
    qname += b'\x00'

    # DNS 头部 (12 bytes) + QNAME + QTYPE(2) + QCLASS(2)
    dns_id = random.randint(0, 65535).to_bytes(2, 'big')
    dns_flags = b'\x01\x00'  # 标准查询
    dns_qdcount = b'\x00\x01'  # 1 个问题
    dns_ancount = b'\x00\x00'
    dns_nscount = b'\x00\x00'
    dns_arcount = b'\x00\x00'
    dns_header = dns_id + dns_flags + dns_qdcount + dns_ancount + dns_nscount + dns_arcount
    dns_question = qname + b'\x00\x01\x00\x01'  # QTYPE=A, QCLASS=IN

    payload = dns_header + dns_question
    return FakePacket(src_ip, '8.8.8.8', 'udp', sport=random.randint(1024, 65535), dport=53, payload=payload)


def build_dns_response(src_ip, dst_ip, domain):
    """构造模拟的 DNS 响应包"""
    labels = domain.split('.')
    qname = b''
    for label in labels:
        qname += bytes([len(label)]) + label.encode()
    qname += b'\x00'

    dns_id = random.randint(0, 65535).to_bytes(2, 'big')
    dns_flags = b'\x81\x80'  # 响应, 无错误
    dns_qdcount = b'\x00\x01'
    dns_ancount = b'\x00\x01'
    dns_nscount = b'\x00\x00'
    dns_arcount = b'\x00\x00'

    fake_ip = f"{random.randint(1, 200)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

    # Answer: NAME pointer (0xc00c) + TYPE A(1) + CLASS IN(1) + TTL + RDLENGTH(4) + RDATA(4)
    answer = b'\xc0\x0c' + b'\x00\x01\x00\x01' + (3600).to_bytes(4, 'big') + b'\x00\x04'
    for part in fake_ip.split('.'):
        answer += bytes([int(part)])

    payload = dns_id + dns_flags + dns_qdcount + dns_ancount + dns_nscount + dns_arcount + qname + b'\x00\x01\x00\x01' + answer
    return FakePacket(dst_ip, src_ip, 'udp', sport=53, dport=random.randint(1024, 65535), payload=payload)


def build_tls_sni_packet(src_ip, dst_ip, sni_domain):
    """构造模拟的 TLS ClientHello 包（带 SNI）
    严格按照 TLS 协议格式构造，确保 SNI 能被正确提取
    """
    sni_name = sni_domain.encode()

    # RFC 6066: Server Name List 条目 = NameType(1) + NameLength(2) + Name(N)
    name_entry = b'\x00' + len(sni_name).to_bytes(2, 'big') + sni_name
    # Server Name List = ListLength(2) + entries
    server_name_list = len(name_entry).to_bytes(2, 'big') + name_entry
    # SNI Extension = ExtType(2) + ExtDataLength(2) + server_name_list
    sni_ext = b'\x00\x00' + len(server_name_list).to_bytes(2, 'big') + server_name_list

    # ClientHello body
    body = b'\x03\x03'  # TLS 1.2
    body += b'\x00' * 32  # Random
    body += b'\x20' + b'\x00' * 32  # Session ID
    body += b'\x00\x02' + b'\xc0\x2b'  # Cipher Suites
    body += b'\x01\x00'  # Compression
    body += len(sni_ext).to_bytes(2, 'big') + sni_ext  # Extensions

    handshake = b'\x01' + len(body).to_bytes(3, 'big') + body
    record = b'\x16' + b'\x03\x01' + len(handshake).to_bytes(2, 'big') + handshake

    return FakePacket(src_ip, dst_ip, 'tcp',
                      sport=random.randint(1024, 65535), dport=443,
                      payload=record)


def build_game_port_packet(src_ip, dst_ip, port, proto='udp'):
    """构造模拟的游戏端口包"""
    return FakePacket(src_ip, dst_ip, 'tcp' if proto == 'tcp' else 'udp',
                      sport=random.randint(1024, 65535), dport=port,
                      payload=b'\x00' * random.randint(100, 1400))


def run_simulation(whitelist, classifier, penalizer, config, callback):
    """运行模拟测试：生成各种流量让制裁引擎处理"""
    print()
    print("=" * 50)
    print("  模拟测试模式")
    print("  正在生成模拟流量，观察制裁引擎如何工作...")
    print("=" * 50)
    print()

    # 模拟客户端
    gamers = [
        '192.168.137.10',
        '192.168.137.11',
        '192.168.137.12',
    ]
    normal_users = [
        '192.168.137.20',
        '192.168.137.21',
    ]

    game_scenarios = [
        ("DNS: steam.com", lambda ip: build_dns_query(ip, 'steamcommunity.com')),
        ("DNS: roblox.com", lambda ip: build_dns_query(ip, 'roblox.com')),
        ("DNS: epicgames.com", lambda ip: build_dns_query(ip, 'epicgames.com')),
        ("DNS: minecraft.net", lambda ip: build_dns_query(ip, 'minecraft.net')),
        ("SNI: discord", lambda ip: build_tls_sni_packet(ip, '1.2.3.4', 'discord.com')),
        ("SNI: riot", lambda ip: build_tls_sni_packet(ip, '1.2.3.5', 'riotgames.com')),
        ("Port: Steam UDP 27015", lambda ip: build_game_port_packet(ip, '5.6.7.8', 27015, 'udp')),
        ("Port: MC TCP 25565", lambda ip: build_game_port_packet(ip, '5.6.7.9', 25565, 'tcp')),
        ("Port: Xbox UDP 3074", lambda ip: build_game_port_packet(ip, '5.6.7.10', 3074, 'udp')),
    ]

    edu_scenarios = [
        ("Edu: Google Classroom", lambda ip: build_dns_query(ip, 'classroom.google.com')),
        ("Edu: GitHub", lambda ip: build_dns_query(ip, 'github.com')),
        ("Edu: Canvas", lambda ip: build_dns_query(ip, 'canvas.instructure.com')),
        ("Edu: Zoom", lambda ip: build_dns_query(ip, 'zoom.us')),
        ("Edu SNI: Google", lambda ip: build_tls_sni_packet(ip, '142.250.80.46', 'classroom.google.com')),
        ("Edu SNI: GitHub", lambda ip: build_tls_sni_packet(ip, '140.82.121.3', 'github.com')),
    ]

    distraction_scenarios = [
        ("DNS: 抖音 douyin.com", lambda ip: build_dns_query(ip, 'douyin.com')),
        ("DNS: 快手 kuaishou.com", lambda ip: build_dns_query(ip, 'kuaishou.com')),
        ("DNS: 小红书 xiaohongshu.com", lambda ip: build_dns_query(ip, 'xiaohongshu.com')),
        ("DNS: 视频号 channels.weixin.qq.com", lambda ip: build_dns_query(ip, 'channels.weixin.qq.com')),
        ("SNI: 抖音", lambda ip: build_tls_sni_packet(ip, '1.2.3.6', 'douyin.com')),
        ("SNI: 小红书", lambda ip: build_tls_sni_packet(ip, '1.2.3.7', 'xiaohongshu.com')),
    ]

    print("场景 1: 游戏狗开始作妖")
    print("-" * 40)

    for gamer in gamers:
        for desc, maker in game_scenarios[:3]:
            packet = maker(gamer)
            cb_result = callback(packet)
            status = "🚫 DROP" if cb_result in ("DROP", "THROTTLE") else "✅ PASS"
            print(f"  [{status}] {gamer:16} → {desc:<25}")
            time.sleep(0.1)

    print()
    print("场景 2: 正常学生上网（应该全部放行）")
    print("-" * 40)

    for user in normal_users:
        for desc, maker in edu_scenarios:
            packet = maker(user)
            cb_result = callback(packet)
            status = "✅ PASS" if cb_result == "FORWARD" else f"⚠️  {cb_result}"
            print(f"  [{status}] {user:16} → {desc:<25}")
            time.sleep(0.05)

    print()
    print("场景 3: 短视频狗（直接全封，不给活路）")
    print("-" * 40)

    for user in normal_users:
        for desc, maker in distraction_scenarios:
            packet = maker(user)
            cb_result = callback(packet)
            status = "🚫 BLOCK" if cb_result == "DROP" else f"⚠️  {cb_result}"
            print(f"  [{status}] {user:16} → {desc:<30}")
            time.sleep(0.05)

    print()
    print("场景 4: 游戏狗持续输出（观察状态切换）")
    print("-" * 40)

    heavy_gamer = gamers[0]
    for round_num in range(15):
        # 每轮随机选一个场景
        desc, maker = random.choice(game_scenarios)
        packet = maker(heavy_gamer)
        cb_result = callback(packet)

        state = "?"
        if hasattr(penalizer, 'clients') and heavy_gamer in penalizer.clients:
            state = penalizer.clients[heavy_gamer]['state']

        status = "🚫" if cb_result in ("DROP", "THROTTLE") else "✅"
        status_char = "D" if cb_result in ("DROP", "THROTTLE") else "."
        print(f"  [{status}] 轮{round_num+1:2d} | {desc:<30} | 状态: {state:<14} | → {cb_result}")
        time.sleep(0.3)

    print()
    print("模拟结束！")
    s = penalizer.get_summary()
    print(f"制裁统计: {s['total_drops']} 次丢包, "
          f"{s['total_throttles']} 次限速, "
          f"{s['total_disconnects']} 次断网, "
          f"{s['total_distraction_blocks']} 次短视频封杀")
    print()
