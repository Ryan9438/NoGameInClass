#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NoGameInClass 便携包构建脚本
在 macOS / Linux 上组装 Windows 绿色便携版（不需要 Windows 机器）。

用法:
    python3 tools/build_portable.py
产物:
    dist/NoGameInClass-portable/      文件夹，直接拷 U 盘
    dist/NoGameInClass-portable.zip   压缩包，用于分发
"""
import os
import sys
import shutil
import zipfile
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build" / "cache"
SEED_DIR = ROOT / "probe" / "wheels"          # 之前探测包下载好的资产，可复用
DIST = ROOT / "dist"
OUT = DIST / "NoGameInClass-portable"

PY_VERSION = "3.12.10"
PY_EMBED_NAME = f"python-{PY_VERSION}-embed-amd64.zip"
PY_EMBED_URL = (
    f"https://www.python.org/ftp/python/{PY_VERSION}/{PY_EMBED_NAME}"
)
PYDIVERT_VERSION = "3.1.3"
PYDIVERT_WHEEL = f"pydivert-{PYDIVERT_VERSION}-py3-none-any.whl"
PYPI_MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.org/simple",
]


def log(msg):
    print(f"[*] {msg}", flush=True)


def download(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"下载 {url}")
    urllib.request.urlretrieve(url, dest)


def _from_cache_or_seed(name: str) -> Path | None:
    """先看 build/cache，再看探测包留下的 probe/wheels。"""
    for base in (CACHE, SEED_DIR):
        p = base / name
        if p.exists():
            return p
    return None


def fetch_python_embed() -> Path:
    cached = _from_cache_or_seed(PY_EMBED_NAME)
    if cached:
        log(f"复用已缓存的运行时: {cached}")
        return cached
    dest = CACHE / PY_EMBED_NAME
    download(PY_EMBED_URL, dest)
    return dest


def fetch_pydivert() -> Path:
    cached = _from_cache_or_seed(PYDIVERT_WHEEL)
    if cached:
        log(f"复用已缓存的 pydivert: {cached}")
        return cached
    for index in PYPI_MIRRORS:
        try:
            log(f"尝试从 {index} 下载 pydivert")
            subprocess.run(
                [
                    sys.executable, "-m", "pip", "download",
                    f"pydivert=={PYDIVERT_VERSION}", "--no-deps",
                    "-d", str(CACHE), "-i", index,
                ],
                check=True,
            )
            wheel = CACHE / PYDIVERT_WHEEL
            if wheel.exists():
                return wheel
        except Exception as e:
            log(f"失败: {e}")
    raise SystemExit("[!] 无法获取 pydivert wheel")


def extract(zip_path: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)


def copytree_clean(src: Path, dest: Path):
    shutil.copytree(
        src, dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


# ----------------------------- 启动器 -----------------------------

LAUNCHER = r"""@echo off
chcp 65001 >nul
title NoGameInClass - 校园网络公平使用工具

REM 检查管理员权限（WinDivert 驱动必须管理员才能加载）
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在申请管理员权限...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo 已获得管理员权限，启动 NoGameInClass...
echo 按 Ctrl+C 可随时停止。
echo.

"%~dp0python\python.exe" "%~dp0src\main.py"

echo.
echo 程序已退出。
pause
"""

DIAG = r"""@echo off
chcp 65001 >nul
title NoGameInClass - 诊断

net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

"%~dp0python\python.exe" "%~dp0probe.py"
pause
"""

README_TXT = f"""NoGameInClass 使用说明
================================

这是什么？
  校园网络公平使用工具。在共享热点上自动识别游戏与短视频流量，
  进行限速 / 封禁，保障正常学习用网的公平性。

怎么用？
  1. 右键 "启动.bat" -> 以管理员身份运行（直接双击也会自动申请权限）
  2. 看到"制裁面板"就说明跑起来了
  3. 按 Ctrl+C 停止

需要什么？
  Windows 7 及以上 64 位。
  不需要安装 Python，所有东西都在这个文件夹里，绿色免安装。

改配置？
  用记事本打开 config.json，改完保存，下次启动生效。
  常用项：
    restrict_games        是否调控游戏（true/false）
    restrict_distractions 是否限制短视频（true/false）
    throttle_bandwidth_kbps 限速多少 Kbps

出问题了？
  右键 "诊断.bat" -> 以管理员身份运行，按提示排查。

声明
  本工具用于在你有权管理的网络中维护网络资源的公平使用。
  请遵守所在机构的信息技术使用规定。
"""


def build():
    log("清理旧产物")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    embed = fetch_python_embed()
    wheel = fetch_pydivert()

    log("解压嵌入式 Python 运行时")
    py_dir = OUT / "python"
    extract(embed, py_dir)

    log("写入 python312._pth（指向 site-packages）")
    (py_dir / "python312._pth").write_text(
        "python312.zip\n.\nLib\\site-packages\nimport site\n",
        encoding="utf-8",
    )

    log("vendor pydivert 到 site-packages")
    site = py_dir / "Lib" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    tmp = CACHE / "_wheel_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    extract(wheel, tmp)
    for item in tmp.iterdir():
        if item.name.startswith("pydivert"):
            shutil.move(str(item), str(site / item.name))
    shutil.rmtree(tmp, ignore_errors=True)

    log("拷贝源码与配置")
    copytree_clean(ROOT / "src", OUT / "src")
    shutil.copy2(ROOT / "config.json", OUT / "config.json")

    log("写入启动器 / 说明 / 诊断")
    (OUT / "启动.bat").write_text(LAUNCHER, encoding="utf-8")
    (OUT / "start.bat").write_text(LAUNCHER, encoding="utf-8")
    (OUT / "诊断.bat").write_text(DIAG, encoding="utf-8")
    (OUT / "probe.py").write_text(
        (ROOT / "probe" / "probe.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (OUT / "使用说明.txt").write_text(README_TXT, encoding="utf-8")

    log("打包 zip（UTF-8 文件名）")
    zip_path = DIST / "NoGameInClass-portable.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(OUT):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in files:
                full = Path(base) / fn
                z.write(full, full.relative_to(OUT.parent))

    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    log(f"完成: {OUT}")
    log(f"大小: {size / 1024 / 1024:.1f} MB（zip {zip_path.stat().st_size / 1024 / 1024:.1f} MB）")


if __name__ == "__main__":
    build()
