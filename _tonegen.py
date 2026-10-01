#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试用音频样本生成器（用 PyAV 合成正弦波，不依赖外部素材）。

© 永远的兰兰
"""
import math
import os
from fractions import Fraction


def make_tone(path, seconds, rate=44100, ch=1, codec="mp3", bitrate=128000):
    import av
    fmt = {".mp3": "mp3", ".m4a": "ipod"}.get(os.path.splitext(path)[1].lower(), "mp3")
    cc = "libmp3lame" if codec == "mp3" else "aac"
    out = av.open(path, "w", format=fmt)
    st = out.add_stream(cc, rate=rate)
    try:
        st.bit_rate = bitrate
    except Exception:
        pass
    st.layout = "mono" if ch == 1 else "stereo"
    rs = av.AudioResampler(format="fltp", layout=st.layout.name, rate=rate)
    total, pos, step = int(rate * seconds), 0, 1024
    while pos < total:
        n = min(step, total - pos)
        fr = av.AudioFrame(format="fltp", layout=st.layout.name, samples=n)
        fr.sample_rate = rate
        for pi, plane in enumerate(fr.planes):
            arr = memoryview(plane).cast("f")
            for k in range(n):
                v = 0.2 * math.sin(2 * math.pi * 440 * (pos + k) / rate)
                arr[k] = v if pi == 0 else v * 0.5
        fr.pts = pos
        fr.time_base = Fraction(1, rate)
        for rf in rs.resample(fr):
            for pkt in st.encode(rf):
                out.mux(pkt)
        pos += n
    for rf in rs.resample(None):
        for pkt in st.encode(rf):
            out.mux(pkt)
    for pkt in st.encode(None):
        out.mux(pkt)
    out.close()
    return path


def tag_mp3(path):
    from mutagen.id3 import ID3, TALB, TIT2, TPE1
    t = ID3()
    t.add(TIT2(encoding=3, text="瘦音测试曲"))
    t.add(TPE1(encoding=3, text="永远的兰兰"))
    t.add(TALB(encoding=3, text="SlimTone"))
    t.save(path)
    return path


def tag_m4a(path):
    from mutagen.mp4 import MP4
    m = MP4(path)
    m["\xa9nam"] = ["M4A 测试曲"]
    m["\xa9ART"] = ["永远的兰兰"]
    m["\xa9alb"] = ["SlimTone"]
    m.save()
    return path
