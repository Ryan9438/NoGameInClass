"""
白名单管理系统
教育域名永远放行，游戏域名永远被制裁
"""
from pathlib import Path
import fnmatch


def _load_domains(filepath):
    """从文件加载域名列表，支持通配符"""
    domains = []
    try:
        path = Path(__file__).parent.parent / filepath
        text = path.read_text(encoding='utf-8')
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            domains.append(line.lower())
    except FileNotFoundError:
        path = Path(filepath)
        if path.exists():
            text = path.read_text(encoding='utf-8')
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('//'):
                    continue
                domains.append(line.lower())
        else:
            print(f"[!] 白名单文件找不到: {filepath}，跳过")
    return domains


class Whitelist:
    def __init__(self, data_dir="data"):
        # 教育白名单
        self.edu_domains = _load_domains(f"{data_dir}/edu_domains.txt")
        # 游戏域名黑名单
        self.game_domains = _load_domains(f"{data_dir}/game_domains.txt")
        # 干扰流量域名黑名单（短视频 / 娱乐平台）
        self.distraction_domains = _load_domains(f"{data_dir}/distraction_domains.txt")
        # 游戏端口
        self.game_ports = self._load_ports(f"{data_dir}/game_ports.txt")

        # DNS 解析缓存: domain/ip -> 关联值
        self.dns_cache = {}

        print(f"[+] 加载了 {len(self.edu_domains)} 个教育域名（白名单）")
        print(f"[+] 加载了 {len(self.game_domains)} 个游戏域名（黑名单）")
        print(f"[+] 加载了 {len(self.distraction_domains)} 个干扰域名（短视频 / 娱乐）")
        print(f"[+] 加载了 {len(self.game_ports)} 个游戏端口")

    def _load_ports(self, filepath):
        """加载游戏端口列表"""
        ports = {'tcp': set(), 'udp': set()}
        try:
            path = Path(__file__).parent.parent / filepath
            text = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            path = Path(filepath)
            if not path.exists():
                return ports
            text = path.read_text(encoding='utf-8')

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue

            proto = parts[0].lower()
            port_str = parts[1]

            if proto not in ('tcp', 'udp'):
                continue

            for p in port_str.split(','):
                p = p.strip()
                if '-' in p:
                    try:
                        start, end = map(int, p.split('-'))
                        for i in range(start, end + 1):
                            ports[proto].add(i)
                    except:
                        pass
                else:
                    try:
                        ports[proto].add(int(p))
                    except:
                        pass
        return ports

    def is_edu_domain(self, domain):
        """检查域名是否在教育白名单中（支持通配符匹配）"""
        if not domain:
            return False
        domain = domain.lower()
        for pattern in self.edu_domains:
            if fnmatch.fnmatch(domain, pattern):
                return True
            # 也检查父域名（如 sub.example.com 匹配 example.com）
            if pattern.startswith('*.') and domain.endswith(pattern[1:]):
                return True
        return False

    def is_game_domain(self, domain):
        """检查域名是否在游戏黑名单中"""
        if not domain:
            return False
        domain = domain.lower()
        for pattern in self.game_domains:
            if fnmatch.fnmatch(domain, pattern):
                return True
            if pattern.startswith('*.') and domain.endswith(pattern[1:]):
                return True
        return False

    def is_distraction_domain(self, domain):
        """检查域名是否在干扰流量黑名单中（短视频 / 娱乐平台）"""
        if not domain:
            return False
        domain = domain.lower()
        for pattern in self.distraction_domains:
            if fnmatch.fnmatch(domain, pattern):
                return True
            if pattern.startswith('*.') and domain.endswith(pattern[1:]):
                return True
        return False

    def is_game_port(self, protocol, port):
        """检查端口是否在游戏端口列表中"""
        ports = self.game_ports.get(protocol, set())
        return port in ports

    def cache_dns(self, domain, ips):
        """缓存 DNS 解析结果"""
        domain = domain.lower()
        self.dns_cache[domain] = ips
        # 同时缓存单个 IP 到域名的反向映射
        for ip in ips:
            self.dns_cache[ip] = domain

    def get_cached_domain(self, ip):
        """通过 IP 查缓存的域名"""
        return self.dns_cache.get(ip)

    def is_edu_ip(self, ip):
        """检查 IP 是否属于已知的教育域名"""
        domain = self.dns_cache.get(ip)
        if domain:
            return self.is_edu_domain(domain)
        return False

    def is_game_ip(self, ip):
        """检查 IP 是否属于已知的游戏域名"""
        domain = self.dns_cache.get(ip)
        if domain:
            return self.is_game_domain(domain)
        return False

    def is_distraction_ip(self, ip):
        """检查 IP 是否属于已知的干扰流量域名"""
        domain = self.dns_cache.get(ip)
        if domain:
            return self.is_distraction_domain(domain)
        return False
