#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SlimTone 端到端流程测试：真实起线程跑一遍（不是同步直调 worker）。

覆盖：加入文件夹 → 自定义输出目录 → 点开始 → 等结束 → 校验产物/表格/状态栏。
再跑一轮「与源文件同目录 + 自动改名」与「停止」。

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
from _tonegen import make_tone, tag_m4a, tag_mp3  # noqa: E402

FAIL = []


def check(label, cond, extra=""):
    print(("  OK   " if cond else "  FAIL ") + label + ((" | " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(label)


os.startfile = lambda *a, **k: None          # 别弹资源管理器
G.os.startfile = os.startfile

ROOT = os.path.join(HERE, "_t", "flow_" + time.strftime("%H%M%S"))
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "out")
os.makedirs(os.path.join(SRC, "专辑甲"), exist_ok=True)
os.makedirs(OUT, exist_ok=True)
G.CFG_PATH = os.path.join(ROOT, "_cfg.json")

print("== 造样本 ==")
f1 = tag_mp3(make_tone(os.path.join(SRC, "one.mp3"), 2.0, 44100, 2, "mp3", 128000))
f2 = tag_m4a(make_tone(os.path.join(SRC, "专辑甲", "two.m4a"), 2.0, 48000, 2, "aac", 128000))
f3 = make_tone(os.path.join(SRC, "专辑甲", "three.m4a"), 2.0, 16000, 1, "aac", 64000)
for p in (f1, f2, f3):
    print("   %s  %d B" % (os.path.relpath(p, ROOT), os.path.getsize(p)))

root = G.TkinterDnD.Tk() if G._HAS_DND else tk.Tk()
app = G.App(root)
root.geometry("1060x740")
root.update()


def pump(seconds, until=None):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        if until and until():
            break
        time.sleep(0.05)
    root.update()


print("== 第一轮：自定义输出目录 + 保留子目录 ==")
app._add_paths([SRC])
pump(0.4)
check("加入 3 个文件", len(app.rows) == 3, len(app.rows))
app.v_custom_out.set(True)
app.v_outdir.set(OUT)
app.v_keep_tree.set(True)
app.v_bitrate.set("64 kbps")
app.v_openout.set(False)
app.v_delsrc.set(False)
app.v_jobs.set("2")
root.update()

app.start()                                  # 真实起线程
check("busy=True（线程已起）", app.busy is True)
check("开始键已禁用", str(app.b_go.cget("state")) == "disabled")
deadline = time.time() + 90
while app.busy and time.time() < deadline:
    root.update()
    time.sleep(0.05)
pump(0.5)
check("线程内无 tk 变量访问异常（未卡死）", app.busy is False, "超时未结束" if app.busy else "")

from mutagen.mp3 import MP3  # noqa: E402
outs = []
for dirpath, _dn, fns in os.walk(OUT):
    for fn in fns:
        if fn.lower().endswith(".mp3"):
            outs.append(os.path.join(dirpath, fn))
check("输出 3 个 mp3", len(outs) == 3, outs)
check("全部 64k", all(abs(round(MP3(p).info.bitrate / 1000) - 64) <= 2 for p in outs),
      [(os.path.basename(p), MP3(p).info.bitrate) for p in outs])
check("保留子目录结构", os.path.isdir(os.path.join(OUT, "专辑甲")) and
      len([p for p in outs if os.path.dirname(p).endswith("专辑甲")]) == 2, outs)
check("mp3 标签已搬", any("永远的兰兰" in str(MP3(p).tags) for p in outs))
check("m4a 标签已映射", any("M4A 测试曲" in str(MP3(p).tags) for p in outs))
check("单声道 m4a 输出仍单声道",
      any(MP3(p).info.channels == 1 for p in outs if "three" in p),
      [(os.path.basename(p), MP3(p).info.channels) for p in outs])
check("表格状态均为完成",
      all(app.tv.set(r["iid"], "status") == "完成" for r in app.rows),
      [app.tv.set(r["iid"], "status") for r in app.rows])
check("表格进度均为 100%",
      all(app.tv.set(r["iid"], "prog") == "100%" for r in app.rows),
      [app.tv.set(r["iid"], "prog") for r in app.rows])
check("总进度条 100%", int(app.pb["value"]) == 1000, app.pb["value"])
check("百分比显示 100%", app.pct_var.get() == "100%", app.pct_var.get())
check("状态栏含成功数", "完成 3" in app.status_var.get(), app.status_var.get())
check("日志有 ✅", "✅" in app.log_txt.get("1.0", "end"))
check("源文件未被删除", all(os.path.exists(p) for p in (f1, f2, f3)))

print("== 第二轮：与源文件同目录 + 自动改名（不得覆盖源）==")
app.tv.delete(*app.tv.get_children())
app.rows.clear()
app.by_iid.clear()
app._add_paths([SRC])
pump(0.3)
app.v_custom_out.set(False)
app.v_same.set("自动改名")
root.update()
app.start()
while app.busy and time.time() < deadline:
    root.update()
    time.sleep(0.05)
pump(0.4)
check("第二轮结束", app.busy is False)
made = []
for dirpath, _dn, fns in os.walk(SRC):
    for fn in fns:
        if fn.lower().endswith(".mp3"):
            made.append(os.path.join(dirpath, fn))
newmp3 = [p for p in made if os.path.basename(p) not in ("one.mp3",)]
check("就地输出 3 个（同名的加 _64k，m4a 直接落 .mp3）", len(newmp3) == 3, newmp3)
check("与源同名的 mp3 加了 _64k 后缀",
      any(os.path.basename(p) == "one_64k.mp3" for p in newmp3), newmp3)
check("m4a 就地产物为 two.mp3 / three.mp3",
      sorted(os.path.basename(p) for p in newmp3 if "_64k" not in p) == ["three.mp3", "two.mp3"],
      newmp3)
check("源 mp3 仍在（没被覆盖）", os.path.exists(f1) and os.path.getsize(f1) > 0)
check("源 m4a 仍在", os.path.exists(f2) and os.path.exists(f3))
check("源 mp3 未被降码率", round(MP3(f1).info.bitrate / 1000) > 100, MP3(f1).info.bitrate)
check("就地产物为 64k", all(abs(round(MP3(p).info.bitrate / 1000) - 64) <= 2 for p in newmp3))
check("标签仍在", "永远的兰兰" in str(MP3(f1).tags))

print("== 第三轮：跳过已存在 ==")
app.tv.delete(*app.tv.get_children())
app.rows.clear()
app.by_iid.clear()
app._add_paths([SRC])
pump(0.3)
app.v_same.set("跳过")
root.update()
app.start()
while app.busy and time.time() < deadline:
    root.update()
    time.sleep(0.05)
pump(0.4)
check("跳过轮结束", app.busy is False)
check("状态栏含跳过数", "跳过 3" in app.status_var.get(), app.status_var.get())

print("== 第四轮：停止 ==")
app.tv.delete(*app.tv.get_children())
app.rows.clear()
app.by_iid.clear()
big = os.path.join(ROOT, "long")
os.makedirs(big, exist_ok=True)
for i in range(4):
    make_tone(os.path.join(big, "long%d.mp3" % i), 300.0, 44100, 2, "mp3", 64000)
app._add_paths([big])
pump(0.3)
app.v_custom_out.set(True)
app.v_outdir.set(os.path.join(ROOT, "out2"))
root.update()
app.start()
pump(1.0)
check("停止前还没跑完（测试有效）", app.busy is True,
      [app.tv.set(r["iid"], "status") for r in app.rows])
app.stop()
deadline2 = time.time() + 60
while app.busy and time.time() < deadline2:
    root.update()
    time.sleep(0.05)
pump(0.3)
check("停止后线程收尾", app.busy is False)
st = [app.tv.set(r["iid"], "status") for r in app.rows]
check("停止后有已取消的文件", any(x == "已取消" for x in st), st)
check("停止后没有全部完成", st.count("完成") < len(st), st)
check("停止后按钮恢复",
      str(app.b_go.cget("state")) == "normal" and str(app.b_stop.cget("state")) == "disabled")

print("== 收尾 ==")
app.on_close()
check("配置已落盘", os.path.exists(G.CFG_PATH), G.CFG_PATH)

print()
print("=" * 56)
if FAIL:
    print("结果：%d 项失败" % len(FAIL))
    for f in FAIL:
        print("   - " + f)
else:
    print("结果：端到端流程全部通过 ✅   （工作目录 %s）" % ROOT)
print("=" * 56)
hard_exit(1 if FAIL else 0)
