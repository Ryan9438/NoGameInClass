"""
流量分类器
四层检测：端口 → DNS → SNI → IP 缓存
一旦确认是游戏流量，立刻交给惩罚引擎
"""
from src.utils.dns_monitor import parse_dns_query
from src.utils.tls_sni import extract_sni
from src.engine.whitelist import Whitelist


class Classification:
    def __init__(self, is_game=False, reason="", domain=""):
        self.is_game = is_game          # 布尔值：是不是游戏流量
        self.is_distraction = False     # 布尔值：是不是干扰流量（短视频 / 娱乐）
        self.reason = reason            # 字符串：判断依据
        self.domain = domain            # 字符串：涉及的域名
        self.is_edu = False             # 布尔值：是不是教育流量

    @property
    def is_restricted(self):
        """需要被调控的流量：游戏 + 干扰"""
        return self.is_game or self.is_distraction

    def __bool__(self):
        return self.is_restricted

    def __repr__(self):
        if self.is_edu:
            return f"<Classification EDU: {self.reason}>"
        if self.is_distraction:
            return f"<Classification DISTRACTION: {self.reason}>"
        if self.is_game:
            return f"<Classification GAME: {self.reason}>"
        return "<Classification CLEAN>"


class Classifier:
    def __init__(self, whitelist: Whitelist):
        self.wl = whitelist

        # 流量缓存：避免重复解析同一个流
        # key: (src_ip, dst_ip, src_port, dst_port, proto) -> Classification
        self.flow_cache = {}
        self.cache_ttl = 300  # 5 分钟后重新检查

    def _flow_key(self, packet):
        """生成五元组缓存 key"""
        ip = getattr(packet, 'ipv4', None)
        if not ip:
            return None

        src_ip = ip.src_addr
        dst_ip = ip.dst_addr
        src_port = 0
        dst_port = 0

        tcp = getattr(packet, 'tcp', None)
        udp = getattr(packet, 'udp', None)

        if tcp:
            src_port = tcp.src_port
            dst_port = tcp.dst_port
            proto = 'tcp'
        elif udp:
            src_port = udp.src_port
            dst_port = udp.dst_port
            proto = 'udp'
        else:
            proto = 'other'

        return (src_ip, dst_ip, src_port, dst_port, proto)

    def classify(self, packet):
        """对单个数据包进行流量分类
        返回 Classification 对象
        """
        result = Classification()

        ip = getattr(packet, 'ipv4', None)
        if not ip:
            return result

        dst_ip = ip.dst_addr
        tcp = getattr(packet, 'tcp', None)
        udp = getattr(packet, 'udp', None)

        # ====== 第 0 层：macOS/开发模式下的回环检测 ======
        # 如果在 macOS 上运行测试，不把回环地址当游戏
        if dst_ip in ('127.0.0.1', '::1', '0.0.0.0'):
            return result

        # ====== 第 1 层：DNS 劫持检测 ======
        domain = parse_dns_query(packet)
        if domain:
            if self.wl.is_edu_domain(domain):
                result.is_edu = True
                result.reason = f"教育域名: {domain}"
                result.domain = domain
                return result
            elif self.wl.is_game_domain(domain):
                result.is_game = True
                result.reason = f"DNS 查询到游戏域名: {domain}"
                result.domain = domain
                return result
            elif self.wl.is_distraction_domain(domain):
                result.is_distraction = True
                result.reason = f"DNS 查询到干扰域名: {domain}"
                result.domain = domain
                return result
            else:
                # 未知域名，记录下来备用
                result.reason = f"未知域名: {domain}"
                result.domain = domain
                return result

        # ====== 第 2 层：TLS SNI 检测 ======
        # HTTPS/443 流量先查 SNI，不靠端口判断（443 什么都在用）
        # 这能精确区分"正在访问 classroom.google.com" vs "正在访问 epicgames.com"
        is_https = tcp and tcp.dst_port == 443
        is_http = tcp and tcp.dst_port == 80

        if is_https:
            sni = extract_sni(packet)
            if sni:
                if self.wl.is_edu_domain(sni):
                    result.is_edu = True
                    result.reason = f"SNI 教育域名: {sni}"
                    result.domain = sni
                    return result
                elif self.wl.is_game_domain(sni):
                    result.is_game = True
                    result.reason = f"SNI 游戏域名: {sni}"
                    result.domain = sni
                    return result
                elif self.wl.is_distraction_domain(sni):
                    result.is_distraction = True
                    result.reason = f"SNI 干扰域名: {sni}"
                    result.domain = sni
                    return result

        # ====== 第 3 层：端口启发式检测 ======
        # 跳过标准 Web 端口（80/443），这些靠 SNI 更准
        if not is_https and not is_http:
            if tcp:
                if self.wl.is_game_port('tcp', tcp.dst_port):
                    result.is_game = True
                    result.reason = f"游戏端口 TCP/{tcp.dst_port}"
                    return result
            elif udp:
                if self.wl.is_game_port('udp', udp.dst_port):
                    result.is_game = True
                    result.reason = f"游戏端口 UDP/{udp.dst_port}"
                    return result

        # ====== 第 4 层：IP 缓存检测 ======
        if self.wl.is_edu_ip(dst_ip):
            result.is_edu = True
            result.reason = f"IP 缓存教育: {dst_ip}"
            return result
        elif self.wl.is_game_ip(dst_ip):
            result.is_game = True
            result.reason = f"IP 缓存游戏: {dst_ip}"
            return result
        elif self.wl.is_distraction_ip(dst_ip):
            result.is_distraction = True
            result.reason = f"IP 缓存干扰: {dst_ip}"
            return result

        # ====== 第 5 层：流缓存检测 ======
        key = self._flow_key(packet)
        if key and key in self.flow_cache:
            cached = self.flow_cache[key]
            return cached

        return result

    def cache_result(self, packet, classification):
        """缓存分类结果"""
        key = self._flow_key(packet)
        if key:
            self.flow_cache[key] = classification
            # 限制缓存大小
            if len(self.flow_cache) > 10000:
                self.flow_cache.clear()

    def update_dns_cache(self, packet, domain):
        """从 DNS 响应中更新 IP 缓存"""
        ip = getattr(packet, 'ipv4', None)
        if not ip:
            return

        # 解析 DNS 响应里的 IP 地址
        payload = bytes(packet.payload)
        if not payload or len(payload) < 12:
            return

        is_response = (payload[2] >> 7) & 1
        if not is_response:
            return

        try:
            # 跳过 Question 段，到 Answer 段
            offset = 12
            # 解析 QNAME
            while offset < len(payload):
                length = payload[offset]
                if length == 0:
                    offset += 1
                    break
                if length & 0xC0:
                    offset += 2
                    break
                offset += 1 + length

            # 跳过 QTYPE 和 QCLASS
            offset += 4

            # 解析 Answers
            while offset + 12 <= len(payload):
                # 跳过 NAME（可能是指针）
                if payload[offset] & 0xC0:
                    offset += 2
                else:
                    while offset < len(payload) and payload[offset] != 0:
                        offset += 1
                    offset += 1

                if offset + 10 > len(payload):
                    break

                atype = (payload[offset] << 8) | payload[offset+1]
                aclass = (payload[offset+2] << 8) | payload[offset+3]
                ttl = (payload[offset+4] << 24) | (payload[offset+5] << 16) | (payload[offset+6] << 8) | payload[offset+7]
                rdlength = (payload[offset+8] << 8) | payload[offset+9]
                offset += 10

                if atype == 1 and rdlength == 4:  # A record
                    ip_str = f"{payload[offset]}.{payload[offset+1]}.{payload[offset+2]}.{payload[offset+3]}"
                    self.wl.cache_dns(domain, [ip_str])

                offset += rdlength

        except (IndexError, ValueError):
            pass
