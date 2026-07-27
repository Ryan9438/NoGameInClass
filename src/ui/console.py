"""
制裁控制台 —— 实时显示你正在制裁哪些游戏狗
"""
import time
import threading
import sys


class ConsoleUI:
    def __init__(self, config, penalizer):
        self.config = config
        self.penalizer = penalizer
        self.running = False
        self.thread = None
        self.log_lines = []
        self.max_log = 100

        # 是否支持 ANSI 转义
        self.has_ansi = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _refresh_loop(self):
        time.sleep(0.5)  # 等 main 初始化完
        while self.running:
            self._render()
            time.sleep(2)

    def _clear_screen(self):
        if self.has_ansi:
            print('\033[2J\033[H', end='')
        else:
            print('\n' * 3)

    def _render(self):
        if not self.has_ansi:
            return

        stats = self.penalizer.get_summary()

        out = []
        out.append("\033[1;36m")  # 青色粗体
        out.append("╔══════════════════════════════════════════════════════╗\n")
        out.append("║              \033[1;33mNoGameInClass - 制裁进行中\033[1;36m               ║\n")
        out.append("╚══════════════════════════════════════════════════════╝\n")
        out.append("\033[0m")  # 重置

        out.append("\n")

        # 统计信息
        out.append(f"\033[1;32m📊 制裁统计\033[0m\n")
        out.append(f"  丢包数:           \033[1;31m{stats['total_drops']}\033[0m\n")
        out.append(f"  限速次数:         \033[1;33m{stats['total_throttles']}\033[0m\n")
        out.append(f"  断网次数:         \033[1;31m{stats['total_disconnects']}\033[0m\n")
        out.append(f"  正在被制裁的客户端: \033[1;31m{stats['active_penalties']}\033[0m 个\n")
        out.append(f"  跟踪的客户端数:   {stats['clients_tracked']} 个\n")

        out.append("\n")

        # 正在被制裁的客户端
        if stats['clients']:
            out.append(f"\033[1;31m🔥 正在被制裁的狗\033[0m\n")
            for ip, info in stats['clients'].items():
                state_icon = "⛔" if info['state'] == "DISCONNECTED" else "🐢"
                state_color = "\033[1;31m" if info['state'] == "DISCONNECTED" else "\033[1;33m"
                elapsed_min = info['elapsed'] // 60
                elapsed_sec = info['elapsed'] % 60
                out.append(f"  {state_icon} {state_color}{ip:<16}\033[0m "
                           f"{info['state']:<12} "
                           f"({elapsed_min}:{elapsed_sec:02d}) "
                           f"x{info['penalty_count']}次\n")
                if info['reason']:
                    out.append(f"     └─ 原因: {info['reason']}\n")
        else:
            out.append(f"\033[1;32m✅ 岁月静好，没有游戏狗\033[0m\n")

        out.append("\n")
        out.append(f"\033[2m按 Ctrl+C 停止制裁 | "
                   f"限速 {self.config.get('throttle_bandwidth_kbps')}Kbps | "
                   f"周期 {self.config.get('throttle_duration_min')}-{self.config.get('throttle_duration_max')}min\033[0m\n")

        self._clear_screen()
        sys.stdout.write(''.join(out))
        sys.stdout.flush()

    def log(self, message):
        """记录一条日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{timestamp}] {message}")
        if len(self.log_lines) > self.max_log:
            self.log_lines.pop(0)
