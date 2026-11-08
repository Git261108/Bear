# -*- coding: utf-8 -*-
"""文件选择器模块

- 安卓：通过 plyer 调用系统文件选择器（SAF），选中后 plyer 会把文件
        复制到应用缓存目录并返回路径
- PC：  使用 tkinter 弹出文件选择对话框

用法（非阻塞）：
    open_excel_dialog(subject_name)   # 立即返回，state 变为 waiting
    poll_result()                     # 轮询: idle/waiting/done/cancelled/error
"""
import threading

_lock = threading.Lock()
_result = {'state': 'idle'}          # idle / waiting / done / cancelled / error
_pending_name = None


def is_android():
    try:
        import jnius  # noqa: F401
        return True
    except ImportError:
        return False


def open_excel_dialog(subject_name):
    """打开文件选择对话框，立即返回；结果通过 poll_result() 轮询获取"""
    global _pending_name
    with _lock:
        _result.clear()
        _result.update(state='waiting')
        _pending_name = subject_name
    target = _pick_android if is_android() else _pick_pc
    threading.Thread(target=target, daemon=True).start()


def _finish(state, **kw):
    with _lock:
        _result.update(state=state, **kw)


def _pick_android():
    try:
        from plyer import filechooser

        def on_selection(selection):
            if selection:
                _finish('done', path=selection[0])
            else:
                _finish('cancelled')

        filechooser.open_file(on_selection=on_selection)
    except Exception as e:
        _finish('error', error=str(e))


def _pick_pc():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askopenfilename(
            title='选择题库 Excel 文件',
            filetypes=[('Excel 文件', '*.xlsx *.xls *.xlsm'), ('所有文件', '*.*')])
        root.destroy()
        if path:
            _finish('done', path=path)
        else:
            _finish('cancelled')
    except Exception as e:
        _finish('error', error=str(e))


def poll_result():
    with _lock:
        return dict(_result)


def pending_name():
    return _pending_name


def reset():
    with _lock:
        _result.clear()
        _result.update(state='idle')
