"""
流量劫持层
基于 PyDivert 劫持 WinDivert 驱动，拦截流过 ICS 子网的所有包
"""
import sys
import threading
from ipaddress import ip_network

from src.utils.netinfo import list_local_ipv4, find_matching_ips


# 尝试导入 PyDivert，如果导入失败则在屏幕上提示
try:
    import pydivert
    HAS_PYDIVERT = True
except ImportError:
    HAS_PYDIVERT = False


class Capturer:
    def __init__(self, config):
        self.config = config
        self.subnet = ip_network(config.get("ics_subnet", "192.168.137.0/24"))
        self.running = False
        self.handle = None
        self.callback = None
        self.thread = None

    def _build_filter(self):
        """构建 WinDivert 过滤器，
        只劫持 ICS 子网内的流量，避免误伤宿主机自身
        """
        subnet = self.config.get("ics_subnet", "192.168.137.0/24")
        network = ip_network(subnet)
        first = network.network_address
        last = network.broadcast_address
        return (
            f"(ip.SrcAddr >= {first} and ip.SrcAddr <= {last}) or "
            f"(ip.DstAddr >= {first} and ip.DstAddr <= {last})"
        )

    def start(self, callback):
        """启动捕获。callback(packet) 会在每个包到达时被调用。
        callback 必须返回 "FORWARD" | "DROP" | "THROTTLE"
        """
        self.callback = callback
        self.running = True

        # 网卡自检：确认热点网段，避免过滤器写错导致抓不到流量
        subnet_str = self.config.get("ics_subnet", "192.168.137.0/24")
        local_ips = list_local_ipv4()
        matched = find_matching_ips(subnet_str)
        print(f"[*] 本机 IPv4 地址: {', '.join(local_ips) if local_ips else '（未检测到）'}")
        if matched:
            print(f"[✓] 热点网段匹配成功: {', '.join(matched)} ∈ {subnet_str}")
        else:
            print(f"[!] 警告: 配置网段 {subnet_str} 与本机任何地址都不匹配")
            print("[!] 若抓不到流量，请把 config.json 里的 ics_subnet 改成热点实际网段")
        print()

        if not HAS_PYDIVERT:
            print("[!] 没找到 PyDivert！在 Windows 上先装: pip install pydivert")
            print("[*] 当前在开发模式运行，使用模拟捕获")
            self._dev_mode()
            return None

        try:
            filter_str = self._build_filter()
            self.handle = pydivert.WinDivert(filter_str, layer=pydivert.Layer.NETWORK)
            self.handle.open()
        except Exception as e:
            print(f"[!] WinDivert 启动失败: {e}")
            print("[!] 请确保：")
            print("    1. 以管理员身份运行")
            print("    2. 已安装: pip install pydivert")
            print("    3. 系统是 Windows 7+")
            print("[*] 切换到开发模拟模式...")
            self._dev_mode()
            return None

        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print(f"[✓] WinDivert 已上线，监控子网 {self.config.get('ics_subnet')}")
        print(f"[✓] 按 Ctrl+C 停止制裁")
        return self.thread

    def _capture_loop(self):
        """WinDivert 捕获主循环"""
        while self.running:
            try:
                packet = self.handle.recv()
                if self.callback:
                    action = self.callback(packet)
                    if action == "FORWARD":
                        self.handle.send(packet)
                    # DROP 和 THROTTLE：不调用 send，直接丢弃
                    # THROTTLE 的放行逻辑在 penalizer 里已经通过返回 FORWARD 处理了
            except Exception as e:
                if self.running:
                    print(f"[-] 捕获异常: {e}")

    def _dev_mode(self):
        """开发模式：在没有 WinDivert 的平台上模拟运行"""
        print("[*] 开发模式已启动（不会真的劫持流量）")
        print("[*] 你可以正常调试检测和惩罚逻辑")
        print()
        # 在开发模式下，启动一个模拟循环
        self.running = False
        print("[*] 提示: 在 Windows 上以管理员身份运行即可激活真正的劫持功能")

    def send(self, packet):
        """重新注入数据包到网络栈"""
        if self.handle and HAS_PYDIVERT:
            try:
                self.handle.send(packet)
            except Exception:
                pass

    def stop(self):
        """停止捕获并释放资源"""
        self.running = False
        if self.handle and HAS_PYDIVERT:
            try:
                self.handle.close()
            except Exception:
                pass
        print("\n[✓] 捕获已停止")
