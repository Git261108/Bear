#!/usr/bin/env bash
# 本地打包 APK 脚本（在 WSL Ubuntu 中运行）
# 用法：把整个 jiakao 文件夹复制到 Ubuntu 主目录后，进入该目录执行：
#   bash build_local.sh
set -e

echo "==== [1/3] 安装系统依赖（需要输入 sudo 密码）===="
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config \
    zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev python3-pip python3-venv
# libtinfo5 在部分 Ubuntu 版本不存在，失败不影响
sudo apt install -y libtinfo5 || true

echo "==== [2/3] 创建 Python 构建环境 ===="
python3 -m venv ~/buildozer-env
source ~/buildozer-env/bin/activate
pip install --upgrade pip wheel
pip install buildozer cython==0.29.33

echo "==== [3/3] 开始打包（首次运行会自动下载 Android SDK/NDK，约 5GB）===="
echo "首次打包需要 30~90 分钟，请耐心等待；之后重新打包只需几分钟。"
buildozer -v android debug

echo ""
echo "==== 完成！APK 文件在 bin/ 目录，传到手机安装即可 ===="
ls -lh bin/*.apk
