# NoGameInClass

校园网络公平使用工具。在设备热点上自动识别并限制游戏流量，保障正常学习用网。

## 背景

国际学校常见场景：教室通过希沃白板开启 Wi-Fi 热点共享网络，设备连接上限 8 台。当部分设备占用带宽进行游戏时，其余设备正常学习（查资料、提交作业、GitHub push 等）会受到严重影响。

本项目旨在通过流量识别与调控，恢复网络资源的公平分配。

## 原理

在开启热点的 Windows 主机上运行。基于 [WinDivert](https://github.com/basil00/WinDivert) 在系统网络层拦截所有经过热点的数据包，通过多层检测识别游戏流量，并实施带宽调控。

### 流量识别

| 检测层 | 方法 | 覆盖范围 |
|--------|------|----------|
| DNS 分析 | 拦截 DNS 查询，匹配游戏域名库 | 148+ 游戏域名 |
| TLS SNI | 从 HTTPS 握手中提取目标域名 | 加密流量同样可识别 |
| 端口分析 | 匹配已知游戏服务端口 | Minecraft(25565), Xbox(3074), Steam(27000-27036) 等 |
| IP 缓存 | 通过 DNS 响应自动关联 IP→域名 | 动态 CDN IP 也可追踪 |

### 调控策略

1. **带宽限制**：对识别为游戏的流量实施限速（默认 50Kbps），使其无法正常游戏
2. **周期性连接调控**：每 2-3 分钟对游戏连接进行间歇性调控，持续 1 分钟以上
3. **白名单保护**：Google Classroom、Canvas、GitHub、Zoom 等教育/学习平台流量完全不受影响

## 快速开始

### Windows

```cmd
pip install -r requirements.txt
python src/main.py
```

需要以管理员身份运行（WinDivert 驱动需要管理员权限）。也可双击 `启动.bat`。

### macOS / Linux（逻辑验证）

```bash
python3 src/main.py --test
```

测试模式会模拟各类网络流量，验证识别与调控逻辑，不会实际拦截数据包。

### 打包为单文件 exe

在 Windows 上运行 `build_exe.bat`，生成 `NoGameInClass.exe`，便于 U 盘携带部署。

## 项目结构

```
NoGameInClass/
├── src/
│   ├── main.py              # 程序入口
│   ├── engine/
│   │   ├── capturer.py      # WinDivert 流量劫持
│   │   ├── classifier.py    # 流量分类识别
│   │   ├── penalizer.py     # 带宽调控状态机
│   │   └── whitelist.py     # 域名白/黑名单管理
│   ├── utils/
│   │   ├── dns_monitor.py   # DNS 查询解析
│   │   └── tls_sni.py       # TLS SNI 提取
│   ├── ui/
│   │   └── console.py       # 状态监控面板
│   ├── data/
│   │   ├── game_domains.txt # 游戏域名列表
│   │   ├── game_ports.txt   # 游戏端口列表
│   │   └── edu_domains.txt  # 教育域名白名单
│   └── test_sim.py          # 模拟测试
├── config.json              # 运行时配置
├── 启动.bat                 # Windows 启动脚本
└── build_exe.bat            # exe 打包脚本
```

## 配置

编辑 `config.json`：

```json
{
    "ics_subnet": "192.168.137.0/24",
    "throttle_bandwidth_kbps": 50,
    "throttle_duration_min": 2,
    "throttle_duration_max": 3,
    "disconnect_duration_min": 1,
    "disconnect_duration_max": 2
}
```

## 贡献

如果发现未覆盖的游戏域名，欢迎提交 Issue 或 PR。项目域名列表采用社区维护方式，共同完善识别覆盖。

## 免责声明

本项目的目的是在合理范围内维护网络资源的公平使用。使用者应确保在有权管理的网络环境中运行，并遵守所在机构的信息技术使用规定。
