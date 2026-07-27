# NoGameInClass 🔥

**整治在校园网上打游戏的小崽子们，还我清净网络环境。**

国际学校学生都懂：打开希沃白板热点 → 8 台设备上限 → 一群人在上面打原神打 Steam → 你连个 GitHub push 都跑不动。

这个项目就是为了治这帮人写的。

## 原理

装在那台开热点的 Windows 电脑上，用 [WinDivert](https://github.com/basil00/WinDivert) 劫持所有经过热点的网络包，用深度包检测（DNS + SNI + 端口分析）识别出游戏流量，然后——

### 制裁三连

1. **限速 50Kbps**：游戏流量？给你限到 50Kbps，连个人物都加载不出来
2. **周期性断网**：每 2-3 分钟彻底断掉游戏连接至少 1 分钟。刚重连上 → 又断 → 再重连 → 再断
3. **白名单保护**：Google Classroom、Canvas、GitHub、Zoom 等教育流量完全不受影响

**结果**: 打游戏的人痛不欲生，正常学习的人毫无感觉。

## 快速开始

### Windows（学校电脑）

```cmd
# 1. 装 Python
# 2. 装依赖
pip install -r requirements.txt

# 3. 以管理员身份运行（右键 → 以管理员身份运行）
python src/main.py
```

或者直接双击 `启动.bat`（会自动请求管理员权限）。

### macOS / Linux（测试用）

```bash
# 测试制裁逻辑（不会真的劫持流量）
python3 src/main.py --test
```

### 打包成单文件 exe（U盘即插即用）

在 Windows 上运行 `build_exe.bat`，生成 `NoGameInClass.exe`，扔 U 盘里带去学校。

## 项目结构

```
NoGameInClass/
├── src/
│   ├── main.py           # 主入口
│   ├── engine/
│   │   ├── capturer.py   # WinDivert 流量劫持
│   │   ├── classifier.py # 游戏/教育流量分类
│   │   ├── penalizer.py  # 限速 + 断网状态机
│   │   └── whitelist.py  # 域名白/黑名单
│   ├── utils/
│   │   ├── dns_monitor.py # DNS 查询提取
│   │   └── tls_sni.py     # TLS SNI 提取
│   ├── ui/
│   │   └── console.py    # 制裁实时面板
│   ├── data/
│   │   ├── game_domains.txt  # 游戏域名黑名单
│   │   ├── game_ports.txt    # 游戏端口列表
│   │   └── edu_domains.txt   # 教育域名白名单
│   └── test_sim.py      # 模拟测试
├── config.json           # 配置文件
├── 启动.bat              # Windows 一键启动
└── build_exe.bat         # 打包 exe 脚本
```

## 检测能力

| 检测层 | 方法 | 覆盖范围 |
|--------|------|----------|
| DNS 劫持 | 拦截 DNS 查询域名 | Steam, Epic, Riot, Blizzard, Roblox, 米哈游 等 148+ 游戏域名 |
| TLS SNI | 从 HTTPS 握手提取域名 | 同上，加密流量也不放过 |
| 端口启发 | 游戏专用端口 | Minecraft(25565), Xbox(3074), Steam(27000-27036) 等 |
| IP 缓存 | DNS 响应自动学习 | 自动关联 IP → 域名 |

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

所有参数随便调。觉得 50Kbps 太仁慈？改成 10。觉得断网 1 分钟太短？改成 5。

## 贡献游戏域名

发现数据库里没有的游戏？提 Issue 或 PR。一个人的发现，全国国际生受益。

## 免责声明

本项目的唯一目的是维护校园网络的公平使用。请合法使用，不要在未经授权的网络上运行。
