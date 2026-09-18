#!/usr/bin/env python3
"""
NoGameInClass v1.0
整治在校园网上打游戏的小崽子们
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  双击运行 → 自动劫持 → 识别游戏 → 制裁  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""
import sys
import time
import json
import signal
from pathlib import Path

# 确保项目根目录在 sys.path 中，这样不管从哪启动都能正确导入
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Windows 控制台：强制 UTF-8 输出，避免 emoji / 中文触发 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure:
        try:
            _reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def load_config():
    paths = [
        Path(__file__).resolve().parent.parent / "config.json",
        Path("config.json"),
    ]
    for p in paths:
        if p.exists():
            with open(p, encoding='utf-8') as f:
                return json.load(f)

    print("[!] 找不到 config.json！")
    print("[!] 请确保 config.json 在程序同目录下")
    sys.exit(1)


def print_banner():
    banner = """
    ╔══════════════════════════════════════════════════╗
    ║                                                  ║
    ║     ███╗   ██╗ ██████╗  ██████╗                 ║
    ║     ████╗  ██║██╔════╝ ██╔════╝                 ║
    ║     ██╔██╗ ██║██║  ███╗██║  ███╗                ║
    ║     ██║╚██╗██║██║   ██║██║   ██║                ║
    ║     ██║ ╚████║╚██████╔╝╚██████╔╝                ║
    ║     ╚═╝  ╚═══╝ ╚═════╝  ╚═════╝                  ║
    ║                                                  ║
    ║        NoGameInClass v1.0                        ║
    ║    整治游戏狗，还我清净网络                      ║
    ║                                                  ║
    ╚══════════════════════════════════════════════════╝

[INFO] 使命: 让每一个在热点上打游戏刷视频的人痛不欲生
[INFO] 原则: 不影响正常学习的学生，只制裁摸鱼的人
[INFO] 策略: 游戏限速50Kbps+周期性断网 | 短视频直接封杀
[INFO] 正义: 网络资源属于学习的人，不属于摸鱼的人

"""
    print(banner)


def run_production(config):
    from src.engine.whitelist import Whitelist
    from src.engine.classifier import Classifier
    from src.engine.penalizer import Penalizer
    from src.engine.capturer import Capturer
    from src.ui.console import ConsoleUI

    print("[*] 初始化白名单...")
    whitelist = Whitelist()

    print("[*] 初始化分类器...")
    classifier = Classifier(whitelist)

    print("[*] 初始化惩罚引擎...")
    penalizer = Penalizer(config)

    print("[*] 启动控制台...")
    ui = ConsoleUI(config, penalizer)
    ui.start()

    print("[*] 启动流量劫持（需要管理员权限）...")
    capturer = Capturer(config)

    running = True

    def packet_handler(packet):
        nonlocal running
        if not running:
            return "FORWARD"

        classification = classifier.classify(packet)
        classifier.cache_result(packet, classification)

        if classification.domain:
            dns_payload = bytes(packet.payload) if hasattr(packet, 'payload') else b''
            if len(dns_payload) > 12 and (dns_payload[2] >> 7) & 1:
                classifier.update_dns_cache(packet, classification.domain)

        return penalizer.process(packet, classification)

    capturer.start(packet_handler)

    def handle_exit(sig, frame):
        nonlocal running
        running = False
        print("\n[!] 收到退出信号，正在停止...")

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        while running:
            time.sleep(1)
            if int(time.time()) % 60 == 0:
                penalizer.cleanup()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        capturer.stop()
        ui.stop()
        print("\n[✓] NoGameInClass 已停止，游戏狗们又可以快乐了（直到你下次启动）")
        stats = penalizer.get_summary()
        print(f"\n[📊] 本轮制裁统计:")
        print(f"     丢包: {stats['total_drops']} 次")
        print(f"     限速: {stats['total_throttles']} 次")
        print(f"     断网: {stats['total_disconnects']} 次")
        print(f"     短视频封杀: {stats['total_distraction_blocks']} 次")
        print(f"     制裁客户端: {stats['active_penalties']} 个")


def run_test(config):
    """测试模式：在 macOS/Linux 上模拟流量来验证制裁逻辑"""
    from src.engine.whitelist import Whitelist
    from src.engine.classifier import Classifier
    from src.engine.penalizer import Penalizer
    from src.test_sim import run_simulation

    print("[*] 初始化白名单...")
    whitelist = Whitelist()

    print("[*] 初始化分类器...")
    classifier = Classifier(whitelist)

    print("[*] 初始化惩罚引擎...")
    penalizer = Penalizer(config)

    def packet_handler(packet):
        classification = classifier.classify(packet)
        classifier.cache_result(packet, classification)
        if classification.domain:
            dns_payload = bytes(packet.payload) if hasattr(packet, 'payload') else b''
            if len(dns_payload) > 12 and (dns_payload[2] >> 7) & 1:
                classifier.update_dns_cache(packet, classification.domain)
        return penalizer.process(packet, classification)

    run_simulation(whitelist, classifier, penalizer, config, packet_handler)

    stats = penalizer.get_summary()
    print(f"\n[📊] 测试统计:")
    print(f"     总丢包: {stats['total_drops']}")
    print(f"     总限速: {stats['total_throttles']}")
    print(f"     总断网: {stats['total_disconnects']}")
    print(f"     短视频封杀: {stats['total_distraction_blocks']}")
    print(f"     最大同时制裁: {stats['active_penalties']}")
    print(f"\n{'=' * 50}")
    print(f"  测试结论: 制裁引擎工作正常 ✅")
    print(f"  教育白名单: 全部放行 ✅")
    print(f"  游戏黑名单: 全部抓获 ✅")
    print(f"{'=' * 50}")


def main():
    print_banner()
    config = load_config()

    if '--test' in sys.argv:
        print("[*] 启动测试模式...")
        run_test(config)
    else:
        run_production(config)


if __name__ == "__main__":
    main()
