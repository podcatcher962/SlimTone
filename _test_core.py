#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SlimTone 逻辑层自测（无头，不 import tkinter）。

造样本 -> 探测 -> 规划输出 -> 转码 -> 校验产物。
样本写在 <本文件目录>/_t/ 下；沙箱禁删，故用带时间戳的新目录，不清理旧目录。

© 永远的兰兰
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import slimcore as C  # noqa: E402
from _hardexit import hard_exit  # noqa: E402
from _tonegen import make_tone, tag_m4a, tag_mp3  # noqa: E402

ROOT = os.path.join(HERE, "_t", time.strftime("%Y%m%d-%H%M%S"))
os.makedirs(ROOT, exist_ok=True)
FAIL = []


def check(label, cond, extra=""):
    print(("  OK   " if cond else "  FAIL ") + label + ((" | " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(label)


print("== 造样本 ==")
mp3_src = os.path.join(ROOT, "src_mp3_128k.mp3")
m4a_src = os.path.join(ROOT, "src_m4a.m4a")
mono_src = os.path.join(ROOT, "src_mono_16k.m4a")
make_tone(mp3_src, 3.0, 44100, 2, "mp3", 128000)
make_tone(m4a_src, 2.5, 48000, 2, "aac", 128000)
make_tone(mono_src, 2.0, 16000, 1, "aac", 64000)
tag_mp3(mp3_src)
tag_m4a(m4a_src)
for p in (mp3_src, m4a_src, mono_src):
    print("   %s  %s" % (os.path.basename(p), C.human_size(os.path.getsize(p))))

print("== probe ==")
for p, want_codec, want_ch in ((mp3_src, "MP3", 2), (m4a_src, "AAC", 2), (mono_src, "AAC", 1)):
    i = C.probe(p)
    check("probe %s codec=%s" % (os.path.basename(p), i["codec"]), i["codec"] == want_codec and not i["err"], i)
    check("probe %s ch=%d" % (os.path.basename(p), i["ch"]), i["ch"] == want_ch, i["ch"])
    check("probe %s dur>0" % os.path.basename(p), i["dur"] > 0.5, "%.2f" % i["dur"])

print("== scan_folder ==")
sub = os.path.join(ROOT, "sub", "deep")
os.makedirs(sub, exist_ok=True)
make_tone(os.path.join(sub, "inner.mp3"), 1.0, 44100, 1, "mp3", 64000)
open(os.path.join(ROOT, "not_audio.txt"), "w").write("x")
flat = C.scan_folder(ROOT, recursive=False)
deep = C.scan_folder(ROOT, recursive=True)
check("scan 非递归不含子目录", all("inner.mp3" not in p for p in flat), len(flat))
check("scan 递归含子目录", any("inner.mp3" in p for p in deep), len(deep))
check("scan 过滤非音频", all(C.is_audio(p) for p in deep))

print("== plan_output ==")
outdir = os.path.join(ROOT, "out")
os.makedirs(outdir, exist_ok=True)
p1 = C.plan_output(m4a_src, outdir, ROOT, True, 64, C.SAME_RENAME)
check("plan 输出名 .mp3", p1.endswith(".mp3") and "src_m4a" in p1, p1)
p2 = C.plan_output(mp3_src, ROOT, ROOT, False, 64, C.SAME_RENAME)
check("plan 同目录同源 -> 加 64k 后缀", os.path.basename(p2) == "src_mp3_128k_64k.mp3", p2)
p3 = C.plan_output(mp3_src, ROOT, ROOT, False, 64, C.SAME_OVERWRITE)
check("plan overwrite -> 原路径", os.path.normcase(p3) == os.path.normcase(mp3_src), p3)
p3b = C.plan_output(mp3_src, ROOT, ROOT, False, 64, C.SAME_SKIP)
check("plan skip 与源同名时也加后缀", os.path.basename(p3b) == "src_mp3_128k_64k.mp3", p3b)
p4 = C.plan_output(os.path.join(sub, "inner.mp3"), outdir, ROOT, True, 64, C.SAME_RENAME)
check("plan 保持子目录结构", os.path.normcase(p4).endswith(os.path.normcase(os.path.join("sub", "deep", "inner.mp3"))), p4)

print("== convert: mp3 -> 64k ==")
d1 = os.path.join(outdir, "out_mp3.mp3")
r1 = C.convert_file(mp3_src, d1, bitrate=64)
check("mp3 转换成功", r1["ok"], r1["err"])
from mutagen.mp3 import MP3  # noqa: E402
check("mp3 输出码率 ≈ 64k", abs(round(MP3(d1).info.bitrate / 1000) - 64) <= 2, MP3(d1).info.bitrate)
check("mp3 时长保留", abs(MP3(d1).info.length - 3.0) < 0.35, MP3(d1).info.length)
check("mp3 标签已复制", r1["tags"] >= 3 and "永远的兰兰" in str(MP3(d1).tags), r1["tags"])

print("== convert: m4a -> 64k ==")
d2 = os.path.join(outdir, "out_m4a.mp3")
r2 = C.convert_file(m4a_src, d2, bitrate=64)
check("m4a 转换成功", r2["ok"], r2["err"])
check("m4a 输出码率 ≈ 64k", abs(round(MP3(d2).info.bitrate / 1000) - 64) <= 2, MP3(d2).info.bitrate)
check("m4a 时长保留", abs(MP3(d2).info.length - 2.5) < 0.35, MP3(d2).info.length)
check("m4a 标签映射成功", r2["tags"] >= 3, r2["tags"])
check("m4a 标签内容对", "M4A 测试曲" in str(MP3(d2).tags), str(MP3(d2).tags)[:80])

print("== convert: 单声道/16k m4a ==")
d3 = os.path.join(outdir, "out_mono.mp3")
r3 = C.convert_file(mono_src, d3, bitrate=64)
check("单声道 m4a 成功", r3["ok"], r3["err"])
check("单声道保持 mono", MP3(d3).info.channels == 1, MP3(d3).info.channels)
check("16k 采样率被接受", MP3(d3).info.sample_rate == 16000, MP3(d3).info.sample_rate)

print("== 强制单声道 / 指定采样率 ==")
d4 = os.path.join(outdir, "out_force_mono.mp3")
r4 = C.convert_file(m4a_src, d4, bitrate=64, channels=1, sample_rate=22050)
check("强制 mono+22050 成功", r4["ok"], r4["err"])
check("声道=1", MP3(d4).info.channels == 1, MP3(d4).info.channels)
check("采样率=22050", MP3(d4).info.sample_rate == 22050, MP3(d4).info.sample_rate)

print("== 码率可选 ==")
for br in (32, 96, 128):
    d = os.path.join(outdir, "out_%d.mp3" % br)
    rr = C.convert_file(mp3_src, d, bitrate=br)
    got = round(MP3(d).info.bitrate / 1000) if rr["ok"] else -1
    check("码率 %d 生效" % br, rr["ok"] and abs(got - br) <= 2, got)

print("== 同源覆盖（dst == src）不得损坏原文件 ==")
d5 = os.path.join(ROOT, "inplace.mp3")
make_tone(d5, 1.5, 44100, 2, "mp3", 128000)
before = os.path.getsize(d5)
r5 = C.convert_file(d5, d5, bitrate=64)
check("原地覆盖成功", r5["ok"], r5["err"])
check("原地覆盖后码率 ≈64k", abs(round(MP3(d5).info.bitrate / 1000) - 64) <= 2, MP3(d5).info.bitrate)
check("原地覆盖后无 .part 残留", not any(".slimtone.part" in f for f in os.listdir(ROOT)), os.listdir(ROOT))

print("== 取消 ==")
d6 = os.path.join(outdir, "out_cancel.mp3")
big = os.path.join(ROOT, "long.mp3")
make_tone(big, 25.0, 44100, 2, "mp3", 128000)
flag = {"stop": False}


def stop():
    flag["stop"] = True
    return True


r6 = C.convert_file(big, d6, bitrate=64, should_stop=stop)
check("取消被识别", (not r6["ok"]) and "取消" in r6["err"], r6["err"])
check("取消后不残留 .part", not [f for f in os.listdir(outdir) if f.endswith(".part")], os.listdir(outdir))

print("== 异常输入 ==")
bad = os.path.join(ROOT, "bad.mp3")
open(bad, "wb").write(b"not an audio file at all" * 100)
r7 = C.convert_file(bad, os.path.join(outdir, "bad_out.mp3"), bitrate=64)
check("坏文件返回失败且不抛异常", (not r7["ok"]) and bool(r7["err"]), r7["err"][:70])
info_bad = C.probe(bad)
check("坏文件 probe 不抛异常", bool(info_bad["err"]), info_bad["err"][:60])

print("== 工具函数 ==")
check("human_size", C.human_size(1536) == "1.50 KB", C.human_size(1536))
check("fmt_dur 分:秒", C.fmt_dur(95) == "1:35", C.fmt_dur(95))
check("fmt_dur 时:分:秒", C.fmt_dur(3725) == "1:02:05", C.fmt_dur(3725))
u = os.path.join(ROOT, "dup.txt")
open(u, "w").write("a")
check("unique_path 避让", C.unique_path(u).endswith("dup (1).txt"), C.unique_path(u))

print()
print("=" * 56)
if FAIL:
    print("结果：%d 项失败" % len(FAIL))
    for f in FAIL:
        print("   - " + f)
else:
    print("结果：全部通过 ✅   （样本目录 %s）" % ROOT)
print("=" * 56)
hard_exit(1 if FAIL else 0)
