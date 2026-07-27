"""
惩罚引擎 —— 整个项目最爽的部分
对每个游戏客户端维持一个状态机:
  CLEAN → THROTTLED → DISCONNECTED → CLEAN (循环)
并配合令牌桶限速，让游戏狗体验什么叫绝望
"""
import time
import random
import threading


class ClientState:
    CLEAN = "CLEAN"          # 清白之身
    THROTTLED = "THROTTLED"  # 限速中，生不如死
    DISCONNECTED = "DISCONNECTED"  # 断网中，直接破防


class Penalizer:
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()

        # 每个客户端的状态
        self.clients = {}  # {client_ip: state_dict}

        # 参数
        self.throttle_bw = config.get("throttle_bandwidth_kbps", 50) * 1024 / 8  # bytes/s
        self.throttle_min = config.get("throttle_duration_min", 2) * 60
        self.throttle_max = config.get("throttle_duration_max", 3) * 60
        self.disconnect_min = config.get("disconnect_duration_min", 1) * 60
        self.disconnect_max = config.get("disconnect_duration_max", 2) * 60
        self.clean_timeout = config.get("clean_timeout_seconds", 30)

        # 统计信息
        self.stats = {
            "total_drops": 0,
            "total_throttles": 0,
            "total_disconnects": 0,
            "active_penalties": 0,
        }

    def _get_state(self, client_ip):
        """获取或初始化客户端状态"""
        now = time.time()
        if client_ip not in self.clients:
            self.clients[client_ip] = {
                "state": ClientState.CLEAN,
                "last_game_time": 0,       # 最后一次检测到游戏流量的时间
                "state_start_time": now,   # 当前状态开始的时间
                "tokens": 0,                # 令牌桶当前令牌数
                "last_token_update": now,  # 上次更新令牌的时间
                "game_reason": "",          # 被制裁的原因
                "penalty_count": 0,         # 被制裁次数
            }
        return self.clients[client_ip]

    def _update_tokens(self, client):
        """更新令牌桶"""
        now = time.time()
        elapsed = now - client["last_token_update"]
        # 每秒恢复 throttle_bw 字节的额度，最多攒 2 秒的桶
        max_burst = self.throttle_bw * 2
        client["tokens"] = min(client["tokens"] + elapsed * self.throttle_bw, max_burst)
        client["last_token_update"] = now

    def process(self, packet, classification):
        """处理一个数据包，返回 Action
        Returns: "FORWARD" | "DROP" | "THROTTLE"
        """
        ip = getattr(packet, 'ipv4', None)
        if not ip:
            return "FORWARD"

        client_ip = ip.src_addr

        with self.lock:
            client = self._get_state(client_ip)
            now = time.time()

            # 如果是教育流量，永远放行
            if classification.is_edu:
                return "FORWARD"

            is_game = classification.is_game
            is_game_packet = is_game  # 这个包本身是不是游戏包

            if is_game:
                client["last_game_time"] = now
                client["game_reason"] = classification.reason

            # ====== 状态机 ======
            if client["state"] == ClientState.CLEAN:
                if is_game:
                    # 抓到了！直接进入限速模式
                    client["state"] = ClientState.THROTTLED
                    client["state_start_time"] = now
                    client["penalty_count"] += 1
                    self.stats["active_penalties"] += 1
                    # 第一个游戏包，丢！
                    self.stats["total_drops"] += 1
                    return "THROTTLE"
                return "FORWARD"

            elif client["state"] == ClientState.THROTTLED:
                elapsed = now - client["state_start_time"]
                throttle_duration = random.uniform(self.throttle_min, self.throttle_max)

                if elapsed >= throttle_duration:
                    # 限时到了，进入断网模式
                    client["state"] = ClientState.DISCONNECTED
                    client["state_start_time"] = now
                    self.stats["total_disconnects"] += 1
                    if is_game_packet:
                        self.stats["total_drops"] += 1
                        return "DROP"
                    return "FORWARD"

                # 如果很久没检测到游戏流量了，放他一马
                if now - client["last_game_time"] > self.clean_timeout:
                    client["state"] = ClientState.CLEAN
                    self.stats["active_penalties"] -= 1
                    return "FORWARD"

                # 限速：令牌桶算法
                packet_size = self._packet_size(packet)
                self._update_tokens(client)

                if is_game_packet:
                    if client["tokens"] >= packet_size:
                        client["tokens"] -= packet_size
                        self.stats["total_throttles"] += 1
                        return "FORWARD"  # 放行但限速
                    else:
                        self.stats["total_drops"] += 1
                        return "DROP"  # 没令牌了，丢包
                else:
                    # 非游戏包，即使在限速状态也放行
                    return "FORWARD"

            elif client["state"] == ClientState.DISCONNECTED:
                elapsed = now - client["state_start_time"]
                disconnect_duration = random.uniform(self.disconnect_min, self.disconnect_max)

                if elapsed >= disconnect_duration:
                    # 断网结束，回到清白
                    client["state"] = ClientState.CLEAN
                    self.stats["active_penalties"] -= 1
                    return "FORWARD"

                if is_game_packet:
                    self.stats["total_drops"] += 1
                    return "DROP"  # 游戏包，不给过
                else:
                    return "FORWARD"  # 非游戏包，正常放行

            return "FORWARD"

    def _packet_size(self, packet):
        """估算包大小用于令牌桶"""
        payload = getattr(packet, 'payload', None)
        if payload:
            return len(payload)
        return 1500  # 猜一个 MTU

    def cleanup(self):
        """清理过期客户端（超过 5 分钟无活动的）"""
        now = time.time()
        with self.lock:
            expired = []
            for ip, client in self.clients.items():
                if client["state"] == ClientState.CLEAN and \
                   now - client["last_game_time"] > 300:
                    expired.append(ip)
            for ip in expired:
                del self.clients[ip]

    def get_summary(self):
        """获取制裁统计"""
        with self.lock:
            stats = dict(self.stats)
            stats["clients_tracked"] = len(self.clients)
            stats["clients"] = {}
            for ip, client in self.clients.items():
                if client["state"] != ClientState.CLEAN:
                    stats["clients"][ip] = {
                        "state": client["state"],
                        "reason": client["game_reason"],
                        "penalty_count": client["penalty_count"],
                        "elapsed": int(time.time() - client["state_start_time"]),
                    }
            return stats
