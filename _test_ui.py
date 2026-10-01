#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SlimTone 布局探测（无头）：构建 App，update 后逐个量控件尺寸，防 1×1。

© 永远的兰兰
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import tkinter as tk  # noqa: E402
import SlimTone_Desktop as G  # noqa: E402
from _hardexit import hard_exit  # noqa: E402

# 干净配置：不让 __init__ 去读用户真实配置
G.CFG_PATH = os.path.join(HERE, "_t", "_ui_test_cfg.json")

FAIL = []


def check(label, cond, extra=""):
    print(("  OK   " if cond else "  FAIL ") + label + ((" | " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(label)


root = G.TkinterDnD.Tk() if G._HAS_DND else tk.Tk()
app = G.App(root)
root.geometry("1060x740")
root.update_idletasks()
root.update()
time.sleep(0.4)
root.update()

print("== 关键控件尺寸 ==")
checks = [
    ("标题条", app.tb_sub, 900, 30),
    ("加入文件按钮", app.b_addf, 70, 24),
    ("加入文件夹按钮", app.b_addd, 90, 24),
    ("队列表格", app.tv, 700, 120),
    ("日志框", app.log_txt, 300, 60),
    ("开始按钮", app.b_go, 90, 28),
    ("停止按钮", app.b_stop, 60, 28),
    ("总进度条", app.pb, 200, 8),
]
for label, w, minw, minh in checks:
    w.update_idletasks()
    ok = w.winfo_width() >= minw and w.winfo_height() >= minh
    check("%s ≥ %dx%d" % (label, minw, minh), ok, "%dx%d" % (w.winfo_width(), w.winfo_height()))

print("== 表格列 ==")
cols = app.tv["columns"]
check("7 列齐全", len(cols) == 7, cols)
for c in cols:
    w = app.tv.column(c, "width")
    check("列 %s 有宽度" % c, w and int(w) > 30, w)

print("== 输出模式联动 ==")
app.v_custom_out.set(False)
app._sync_out_state()
root.update()
check("同目录模式下输出框禁用", str(app.e_out.cget("state")) == "disabled", app.e_out.cget("state"))
check("同目录模式下浏览键禁用", str(app.b_browse.cget("state")) == "disabled")
check("同目录模式下子目录勾选禁用", str(app.cb_tree.cget("state")) == "disabled")
app.v_custom_out.set(True)
app._sync_out_state()
root.update()
check("自定义模式下输出框可用", str(app.e_out.cget("state")) == "normal")
check("自定义模式下浏览键可用", str(app.b_browse.cget("state")) == "normal")

print("== 设置读写 ==")
app.v_bitrate.set("96 kbps")
app.v_chan.set("单声道")
app.v_rate.set("44100")
app.v_same.set("覆盖")
app.v_jobs.set("3")
app.v_custom_out.set(True)
app.v_outdir.set(r"D:\_slimtone_ui_test_out")
app.v_keep_tree.set(True)
s = app._settings()
check("码率读出 96", s["bitrate"] == 96, s)
check("声道读出 1", s["chan"] == 1, s)
check("采样率读出 44100", s["rate"] == 44100, s)
check("同名策略读出 overwrite", s["same"] == G.C.SAME_OVERWRITE, s)
check("并发读出 3", s["jobs"] == 3, s)
check("输出目录读出", s["outdir"].endswith("_slimtone_ui_test_out"), s["outdir"])
check("keep_tree 读出 True", s["keep_tree"] is True, s)

print("== 加入文件（造样本，走 _add_paths）==")
from _tonegen import make_tone  # noqa: E402


def tone(path, sec, codec="mp3"):
    make_tone(path, sec, 44100 if codec == "mp3" else 48000, 1, codec, 64000)


tmp = os.path.join(HERE, "_t", "ui_samples_" + time.strftime("%H%M%S"))
sub = os.path.join(tmp, "专辑A", "CD1")
os.makedirs(sub, exist_ok=True)
tone(os.path.join(tmp, "a.mp3"), 1.0)
tone(os.path.join(sub, "b.m4a"), 1.0, "aac")
open(os.path.join(tmp, "readme.txt"), "w").write("x")
app._add_paths([tmp])
root.update()
check("文件夹扫描加入 2 个", len(app.rows) == 2, len(app.rows))
check("表格行数一致", len(app.tv.get_children()) == 2, len(app.tv.get_children()))
check("非音频被过滤", all(r["path"].endswith((".mp3", ".m4a")) for r in app.rows))
check("子目录文件已收录", any("b.m4a" in r["path"] for r in app.rows))
check("root 记录为加入的文件夹", all(os.path.normcase(r["root"]) == os.path.normcase(tmp) for r in app.rows),
      [r["root"] for r in app.rows])
check("状态列为等待", all(app.tv.set(r["iid"], "status") == "等待" for r in app.rows))
check("时长已填", all(app.tv.set(r["iid"], "dur") != "-" for r in app.rows),
      [app.tv.set(r["iid"], "dur") for r in app.rows])

app._add_paths([tmp])
check("重复加入不重复", len(app.rows) == 2, len(app.rows))

print("== 移除 / 清空 ==")
first = app.rows[0]["iid"]
app.tv.selection_set(first)
app.remove_sel()
root.update()
check("移除 1 项后剩 1", len(app.rows) == 1 and len(app.tv.get_children()) == 1,
      (len(app.rows), len(app.tv.get_children())))
app.rows.clear()
app.by_iid.clear()
app.tv.delete(*app.tv.get_children())
app._renumber()
check("清空后列表为空", len(app.tv.get_children()) == 0)

print("== 日志与计数 ==")
app.log("布局测试写入一行")
root.update()
check("日志有内容", "布局测试写入一行" in app.log_txt.get("1.0", "end"))
check("计数文本非空", bool(app.count_var.get()), app.count_var.get())

print("== 恢复默认 ==")
app.reset_settings()
s2 = app._settings()
check("恢复默认码率 64", s2["bitrate"] == 64, s2["bitrate"])
check("恢复默认同名策略 rename", s2["same"] == G.C.SAME_RENAME, s2["same"])
check("恢复默认并发 2", s2["jobs"] == 2, s2["jobs"])
check("恢复默认不删源", s2["delsrc"] is False)

print("== 帮助文本 ==")
check("使用说明含关键词", "开始转换" in G.HELP_TEXT and "64" in G.HELP_TEXT)
check("免责声明含免责要点", "AS-IS" in G.DISCLAIMER and "回收站" in G.DISCLAIMER)
check("署名到位", "永远的兰兰" in G.DISCLAIMER and G.AUTHOR.endswith("永远的兰兰"), G.AUTHOR)

try:
    root.destroy()
except Exception:
    pass

print()
print("=" * 56)
if FAIL:
    print("结果：%d 项失败" % len(FAIL))
    for f in FAIL:
        print("   - " + f)
else:
    print("结果：布局测试全部通过 ✅")
print("=" * 56)
hard_exit(1 if FAIL else 0)
