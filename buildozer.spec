[app]
# ==== 应用基本信息 ====
title = Bear·熊笔记
package.name = bearnotes
package.domain = org.bearbiji
source.dir = .
source.include_exts = py,html,css,xlsx,db
# 打包时排除不需要的文件
source.exclude_dirs = .git,__pycache__,data/backup
source.exclude_patterns = selftest.py,upload.xlsx,*.spec,*.md

# 版本号
version = 0.9.0

# ==== 依赖（APK 内置 Python 运行时与第三方库）====
requirements = python3,kivy==2.3.0,flask,openpyxl,jnius,plyer,xlrd

# ==== 安卓配置 ====
orientation = portrait
fullscreen = 0
android.api = 33
android.minapi = 24
# 固定 build-tools 为稳定版，避免 sdkmanager 自动追最新版（37）导致的许可/兼容问题
android.build_tools_version = 34.0.0
android.archs = arm64-v8a, armeabi-v7a
# 权限：网络 + 读取存储（用于从手机下载文件夹导入题库）
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.allow_backup = True

# CI 环境自动接受 Android SDK 许可协议（否则无交互输入会跳过 build-tools 安装）
android.accept_license = 1

# 首页方向锁定竖屏、保留状态栏
android.wakelock = 1

[buildozer]
log_level = 2
warn_on_root = 1
