# -*- coding: utf-8 -*-
"""打包入口（APK 用）：
- 在安卓上：后台线程启动 Flask 服务器，再用原生 WebView 全屏加载页面
- 在 PC 上：也可以直接 `python main.py` 启动并自动打开浏览器
"""
import os
import socket
import sys
import threading
import time

PORT = 5000


def is_android():
    try:
        import jnius  # noqa: F401
        return True
    except ImportError:
        return False


def start_server():
    import database as db
    db.init_db()
    from app import app
    host = '127.0.0.1' if is_android() else '0.0.0.0'
    app.run(host=host, port=PORT, threaded=True, use_reloader=False, debug=False)


def wait_server(timeout=20):
    """等待服务器就绪"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def show_webview():
    """安卓：用原生 WebView 全屏显示应用"""
    from jnius import autoclass

    WebView = autoclass('android.webkit.WebView')
    WebViewClient = autoclass('android.webkit.WebViewClient')
    WebChromeClient = autoclass('android.webkit.WebChromeClient')
    WebSettings = autoclass('android.webkit.WebSettings')
    Looper = autoclass('android.os.Looper')
    Handler = autoclass('android.os.Handler')
    ColorDrawable = autoclass('android.graphics.drawable.ColorDrawable')
    Color = autoclass('android.graphics.Color')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = PythonActivity.mActivity

    handler = Handler(Looper.getMainLooper())

    def _show():
        webview = WebView(activity)
        s = webview.getSettings()
        s.setJavaScriptEnabled(True)
        s.setDomStorageEnabled(True)
        s.setAllowFileAccess(True)
        s.setCacheMode(WebSettings.LOAD_NO_CACHE)
        webview.setWebViewClient(WebViewClient())
        webview.setWebChromeClient(WebChromeClient())
        # 背景色与页面一致，避免启动白屏闪烁
        webview.setBackgroundDrawable(ColorDrawable(Color.parseColor('#F2F4F8')))
        activity.setContentView(webview)
        webview.loadUrl(f'http://127.0.0.1:{PORT}/')

    handler.post(_show)


def main():
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    if is_android():
        # 等待服务器就绪后再显示 WebView
        while not wait_server():
            pass
        show_webview()
        # p4a 中 python 脚本结束 = 应用退出，保持常驻
        while True:
            time.sleep(1)
    else:
        wait_server()
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{PORT}/')
        try:
            t.join()
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == '__main__':
    main()
