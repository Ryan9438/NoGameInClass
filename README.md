# NoGameInClass

校园网络公平使用工具。在设备热点上自动识别并限制游戏与娱乐流量，保障正常学习用网。

## 背景

国际学校常见场景：教室通过希沃白板开启 Wi-Fi 热点共享网络，设备连接上限 8 台。当部分设备占用带宽进行游戏或刷短视频时，其余设备正常学习（查资料、提交作业、GitHub push 等）会受到严重影响。

本项目旨在通过流量识别与调控，恢复网络资源的公平分配。

## 原理

在开启热点的 Windows 主机上运行。基于 [WinDivert](https://github.com/basil00/WinDivert) 在系统网络层拦截所有经过热点的数据包，通过多层检测识别游戏流量，并实施带宽调控。

### 流量识别

| 检测层 | 方法 | 覆盖范围 |
|--------|------|----------|
| DNS 分析 | 拦截 DNS 查询，匹配域名库 | 148+ 游戏域名 / 75+ 娱乐域名 |
| TLS SNI | 从 HTTPS 握手中提取目标域名 | 加密流量同样可识别 |
| 端口分析 | 匹配已知游戏服务端口 | Minecraft(25565), Xbox(3074), Steam(27000-27036) 等 |
| IP 缓存 | 通过 DNS 响应自动关联 IP→域名 | 动态 CDN IP 也可追踪 |

### 调控策略

按流量类别区分处理：

| 类别 | 示例 | 策略 |
|------|------|------|
| 游戏 | Steam、原神、Minecraft、Discord | 带宽限制 + 周期性连接调控 |
| 娱乐 | 抖音、快手、小红书、微信视频号 | 直接封禁（可配置为与游戏相同） |
| 学习 | Google Classroom、Canvas、GitHub、Zoom | 完全放行 |

## 快速开始

### Windows

```cmd
pip install -r requirements.txt
python src/main.py
```

需要以管理员身份运行（WinDivert 驱动需要管理员权限）。也可双击 `启动.bat`。

### Windows 免安装便携版（目标机没有 Python 时用这个）

在开发机上运行：

```bash
python3 tools/build_portable.py
```

生成 `dist/NoGameInClass-portable/`（含嵌入式 Python 运行时），整个文件夹拷到 U 盘，目标机右键 `启动.bat` → 以管理员身份运行即可，**目标机无需安装 Python 或任何依赖**。

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
│   │   ├── netinfo.py       # 网卡自检（定位热点网段）
│   │   └── tls_sni.py       # TLS SNI 提取
│   ├── ui/
│   │   └── console.py       # 状态监控面板
│   ├── data/
│   │   ├── game_domains.txt        # 游戏域名列表
│   │   ├── distraction_domains.txt # 娱乐域名列表（短视频 / 直播）
│   │   ├── game_ports.txt          # 游戏端口列表
│   │   └── edu_domains.txt         # 教育域名白名单
│   └── test_sim.py          # 模拟测试
├── tools/
│   └── build_portable.py    # 便携包构建脚本
├── config.json              # 运行时配置
├── 启动.bat                 # Windows 启动脚本
└── build_exe.bat            # exe 打包脚本
```

## 配置

编辑 `config.json`：

```json
{
    "ics_subnet": "192.168.137.0/24",
    "restrict_games": true,
    "restrict_distractions": true,
    "block_distractions": true,
    "throttle_bandwidth_kbps": 50,
    "throttle_duration_min": 2,
    "throttle_duration_max": 3,
    "disconnect_duration_min": 1,
    "disconnect_duration_max": 2
}
```

| 配置项 | 说明 |
|--------|------|
| `restrict_games` | 是否调控游戏流量 |
| `restrict_distractions` | 是否限制娱乐流量 |
| `block_distractions` | 娱乐流量：`true` 直接封禁，`false` 走与游戏相同的限速流程 |
| `throttle_bandwidth_kbps` | 限速带宽 |
| `throttle_duration_*` | 限速阶段时长（分钟，随机区间） |
| `disconnect_duration_*` | 断网阶段时长（分钟，随机区间） |

## 贡献

如果发现未覆盖的游戏或娱乐域名，欢迎提交 Issue 或 PR。项目域名列表采用社区维护方式，共同完善识别覆盖。

## 免责声明

本项目的目的是在合理范围内维护网络资源的公平使用。使用者应确保在有权管理的网络环境中运行，并遵守所在机构的信息技术使用规定。
