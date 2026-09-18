"""
惩罚引擎 —— 整个项目最爽的部分
对每个被限制的客户端维持一个状态机:
  CLEAN → THROTTLED → DISCONNECTED → CLEAN (循环)
并配合令牌桶限速，让游戏狗体验什么叫绝望

干扰流量（短视频 / 娱乐平台）走另一条路：默认直接全封，不留活口。
"""
import time
import random
import threading
from typing import Any


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

        # 开关
        self.restrict_games = config.get("restrict_games", True)
        self.restrict_distractions = config.get("restrict_distractions", True)
        self.block_distractions = config.get("block_distractions", True)

        # 参数
        self.throttle_bw = config.get("throttle_bandwidth_kbps", 50) * 1024 / 8  # bytes/s
        self.throttle_min = config.get("throttle_duration_min", 2) * 60
        self.throttle_max = config.get("throttle_duration_max", 3) * 60
        self.disconnect_min = config.get("disconnect_duration_min", 1) * 60
        self.disconnect_max = config.get("disconnect_duration_max", 2) * 60
        self.clean_timeout = config.get("clean_timeout_seconds", 30)

        # 统计信息
        self.stats: dict[str, Any] = {
            "total_drops": 0,
            "total_throttles": 0,
            "total_disconnects": 0,
            "total_distraction_blocks": 0,
            "active_penalties": 0,
        }

    def _get_state(self, client_ip):
        """获取或初始化客户端状态"""
        now = time.time()
        if client_ip not in self.clients:
            self.clients[client_ip] = {
                "state": ClientState.CLEAN,
                "last_restricted_time": 0,  # 最后一次检测到受限流量的时间
                "state_start_time": now,    # 当前状态开始的时间
                "tokens": 0,                # 令牌桶当前令牌数
                "last_token_update": now,   # 上次更新令牌的时间
                "penalty_reason": "",       # 被制裁的原因
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

    def _is_restricted(self, classification):
        """该流量是否需要被调控"""
        if classification.is_game and self.restrict_games:
            return True
        if classification.is_distraction and self.restrict_distractions:
            return True
        return False

    def process(self, packet, classification):
        """处理一个数据包，返回 Action
        Returns: "FORWARD" | "DROP" | "THROTTLE"
        """
        ip = getattr(packet, 'ipv4', None)
        if not ip:
            return "FORWARD"

        client_ip = ip.src_addr

        with self.lock:
            # 教育流量永远放行
            if classification.is_edu:
                return "FORWARD"

            # 干扰流量（短视频 / 娱乐）：默认直接封死，不进入状态机
            if classification.is_distraction and self.restrict_distractions and self.block_distractions:
                self.stats["total_drops"] += 1
                self.stats["total_distraction_blocks"] += 1
                client = self._get_state(client_ip)
                client["penalty_reason"] = classification.reason
                return "DROP"

            client = self._get_state(client_ip)
            now = time.time()

            is_restricted = self._is_restricted(classification)

            if is_restricted:
                client["last_restricted_time"] = now
                client["penalty_reason"] = classification.reason

            # ====== 状态机 ======
            state = client["state"]

            if state == ClientState.CLEAN:
                if is_restricted:
                    # 抓到了！直接进入限速模式
                    client["state"] = ClientState.THROTTLED
                    client["state_start_time"] = now
                    client["penalty_count"] += 1
                    self.stats["active_penalties"] += 1
                    self.stats["total_drops"] += 1
                    return "THROTTLE"
                return "FORWARD"

            elif state == ClientState.THROTTLED:
                elapsed = now - client["state_start_time"]
                throttle_duration = random.uniform(self.throttle_min, self.throttle_max)

                if elapsed >= throttle_duration:
                    # 限时到了，进入断网模式
                    client["state"] = ClientState.DISCONNECTED
                    client["state_start_time"] = now
                    self.stats["total_disconnects"] += 1
                    if is_restricted:
                        self.stats["total_drops"] += 1
                        return "DROP"
                    return "FORWARD"

                # 如果很久没检测到受限流量了，放他一马
                if now - client["last_restricted_time"] > self.clean_timeout:
                    client["state"] = ClientState.CLEAN
                    self.stats["active_penalties"] -= 1
                    return "FORWARD"

                # 限速：令牌桶算法
                if is_restricted:
                    packet_size = self._packet_size(packet)
                    self._update_tokens(client)
                    if client["tokens"] >= packet_size:
                        client["tokens"] -= packet_size
                        self.stats["total_throttles"] += 1
                        return "FORWARD"  # 放行但限速
                    else:
                        self.stats["total_drops"] += 1
                        return "DROP"  # 没令牌了，丢包
                else:
                    # 非受限包，即使在限速状态也放行
                    return "FORWARD"

            elif state == ClientState.DISCONNECTED:
                elapsed = now - client["state_start_time"]
                disconnect_duration = random.uniform(self.disconnect_min, self.disconnect_max)

                if elapsed >= disconnect_duration:
                    # 断网结束，回到清白
                    client["state"] = ClientState.CLEAN
                    self.stats["active_penalties"] -= 1
                    return "FORWARD"

                if is_restricted:
                    self.stats["total_drops"] += 1
                    return "DROP"  # 受限流量，不给过
                else:
                    return "FORWARD"  # 其他流量正常放行

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
                   now - client["last_restricted_time"] > 300:
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
                        "reason": client["penalty_reason"],
                        "penalty_count": client["penalty_count"],
                        "elapsed": int(time.time() - client["state_start_time"]),
                    }
            return stats
