#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""硬退出：建过 tkinter 窗口后，Tcl 的 DllMain(PROCESS_DETACH) 可能让进程卡住不消失
（脚本跑完却一直挂着、退出码被 SIGTERM）。TerminateProcess 绕开 Tcl 收尾回调。

⚠️ 64 位下必须显式声明 argtypes —— GetCurrentProcess() 返回的是伪句柄 -1（HANDLE 宽 64 位），
ctypes 默认按 32 位 int 传参会截断 → TerminateProcess 报 ERROR_INVALID_HANDLE 静默失败，
只剩后面的 os._exit() 去撞 Tcl 的 DllMain，于是照样卡死。

所有无头测试脚本与 GUI main() 的结尾都调它。© 永远的兰兰
"""
import os
import sys


def hard_exit(code=0):
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    try:
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.GetCurrentProcess.argtypes = []
        k32.TerminateProcess.restype = ctypes.c_int
        k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        k32.TerminateProcess(k32.GetCurrentProcess(), int(code))
    except Exception:
        pass
    os._exit(code)  # 兜底（正常情况下到不了这里）
