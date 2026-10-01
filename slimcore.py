#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SlimTone 瘦音 · 核心逻辑层

把任意 MP3 / M4A（及其他常见音频）重新编码为目标码率的 MP3。
本文件只依赖标准库 + av(PyAV) + mutagen，**不 import tkinter**，可被无头脚本直接测试。

© 永远的兰兰 / Lanlan Eternal
"""
from __future__ import annotations

import os
import time

AUDIO_EXTS = (
    # 主角
    ".mp3", ".m4a",
    # 顺手支持（ffmpeg 能解的都给解）
    ".m4b", ".aac", ".mp4", ".m4v", ".mov",
    ".wav", ".flac", ".ogg", ".oga", ".opus",
    ".wma", ".aif", ".aiff", ".ape", ".mka", ".amr", ".3gp", ".wv",
)

BITRATES = (32, 48, 64, 96, 128, 160, 192)
DEFAULT_BITRATE = 64

# MP3（MPEG-1/2/2.5 Layer III）允许的采样率
MP3_RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)

SAME_SKIP, SAME_OVERWRITE, SAME_RENAME = "skip", "overwrite", "rename"


# --------------------------------------------------------------------------
#  小工具
# --------------------------------------------------------------------------
def ext_of(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def is_audio(path: str) -> bool:
    return ext_of(path) in AUDIO_EXTS


def human_size(n) -> str:
    try:
        n = float(n)
    except Exception:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%.0f %s" % (n, unit)) if unit == "B" else ("%.2f %s" % (n, unit))
        n /= 1024.0


def fmt_dur(sec) -> str:
    if not sec or sec <= 0:
        return "-"
    sec = int(round(sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%d:%02d" % (m, s))


def unique_path(path: str) -> str:
    """若文件已存在，追加 (1)(2)… 直到不冲突。"""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    i = 1
    while True:
        cand = "%s (%d)%s" % (stem, i, ext)
        if not os.path.exists(cand):
            return cand
        i += 1


def scan_folder(root: str, recursive: bool = True, exts=AUDIO_EXTS):
    """扫描目录，返回音频文件绝对路径列表（去重、排序）。"""
    found = []
    root = os.path.abspath(root)
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in ("$recycle.bin", "system volume information")]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in exts:
                    found.append(os.path.join(dirpath, fn))
    else:
        try:
            for fn in os.listdir(root):
                fp = os.path.join(root, fn)
                if os.path.isfile(fp) and os.path.splitext(fn)[1].lower() in exts:
                    found.append(fp)
        except OSError:
            pass
    return sorted(set(os.path.abspath(p) for p in found))


# --------------------------------------------------------------------------
#  探测
# --------------------------------------------------------------------------
_CODEC_ALIAS = {
    "mp3float": "MP3", "mp3": "MP3", "mp3adu": "MP3", "mp3adufloat": "MP3", "mp3on4": "MP3",
    "aac": "AAC", "aac_latm": "AAC", "alac": "ALAC",
    "vorbis": "Vorbis", "opus": "Opus", "flac": "FLAC", "wmav2": "WMA", "wmapro": "WMA",
    "pcm_s16le": "PCM/WAV", "pcm_s24le": "PCM/WAV", "pcm_f32le": "PCM/WAV",
    "ape": "APE", "amr_nb": "AMR", "ac3": "AC3", "eac3": "EAC3", "mp2": "MP2",
}


def pretty_codec(name: str) -> str:
    """把 ffmpeg 的编码器内部名换成给人看的名字。"""
    if not name:
        return "-"
    return _CODEC_ALIAS.get(name.lower(), name.upper())


def probe(path: str) -> dict:
    """快速读元信息（不整段解码）。失败时 err 有值。"""
    info = {"codec": "-", "sr": 0, "ch": 0, "dur": 0.0, "br": 0, "size": 0, "err": ""}
    try:
        info["size"] = os.path.getsize(path)
    except OSError as e:
        info["err"] = "无法读取：%s" % e
        return info
    try:
        import av
        with av.open(path) as c:
            if not c.streams.audio:
                info["err"] = "无音频轨"
                return info
            s = c.streams.audio[0]
            ctx = s.codec_context
            info["codec"] = pretty_codec(ctx.name)
            info["sr"] = ctx.sample_rate or 0
            try:
                info["ch"] = ctx.layout.nb_channels
            except Exception:
                info["ch"] = ctx.channels or 0
            if s.duration:
                info["dur"] = float(s.duration * s.time_base)
            elif c.duration:
                info["dur"] = float(c.duration) / 1_000_000.0
            if s.bit_rate:
                info["br"] = int(s.bit_rate)
            elif info["dur"] > 0:
                info["br"] = int(info["size"] * 8 / info["dur"])
    except Exception as e:
        info["err"] = "%s: %s" % (type(e).__name__, e)
    return info


# --------------------------------------------------------------------------
#  输出路径规划
# --------------------------------------------------------------------------
def plan_output(src: str, out_dir: str, src_root: str = "", keep_tree: bool = True,
                bitrate: int = DEFAULT_BITRATE, mode: str = SAME_RENAME):
    """算出目标文件路径（不落盘）。

    与源文件同名（输出目录 == 源目录 且 不加后缀）时，mode 决定行为：
      - skip      跳过（返回 None，由调用方判断是否已存在）
      - overwrite 覆盖（返回原路径，转换时走临时文件再替换）
      - rename    加 _64k 后缀
    """
    stem = os.path.splitext(os.path.basename(src))[0]
    out_dir = os.path.abspath(out_dir)
    if keep_tree and src_root:
        try:
            rel = os.path.relpath(os.path.dirname(os.path.abspath(src)), os.path.abspath(src_root))
        except ValueError:
            rel = "."
        if rel not in (".", ""):
            out_dir = os.path.join(out_dir, rel)
    cand = os.path.join(out_dir, stem + ".mp3")
    if os.path.normcase(os.path.abspath(cand)) != os.path.normcase(os.path.abspath(src)):
        return cand
    # 与源文件同名 —— 读写同一个文件是禁止的
    if mode == SAME_OVERWRITE:
        return cand          # 走临时文件再替换
    # 「跳过」在这里也必须加后缀，否则「与源文件同目录 + 跳过」会退化成「整批全跳过」
    tag = "%dk" % bitrate
    cand2 = os.path.join(out_dir, "%s_%s.mp3" % (stem, tag))
    i = 1
    while os.path.normcase(os.path.abspath(cand2)) == os.path.normcase(os.path.abspath(src)):
        cand2 = os.path.join(out_dir, "%s_%s_%d.mp3" % (stem, tag, i))
        i += 1
    return cand2


# --------------------------------------------------------------------------
#  标签
# --------------------------------------------------------------------------
def copy_tags(src: str, dst: str) -> int:
    """把源文件的标签/封面搬到目标 MP3，返回搬运的条目数（0 表示没有/失败）。"""
    try:
        from mutagen import File as MutagenFile
        from mutagen.id3 import (ID3, ID3NoHeaderError, APIC, COMM, TALB, TCON,
                                 TDRC, TIT2, TPE1, TPE2, TRCK)
    except Exception:
        return 0

    src_ext = ext_of(src)
    try:
        if src_ext == ".mp3":
            try:
                tags = ID3(src)
            except ID3NoHeaderError:
                return 0
            except Exception:
                return 0
            if not tags:
                return 0
            tags.save(dst)
            return len(tags)

        # M4A / MP4 / AAC 等：把 iTunes 原子映射成 ID3
        m = MutagenFile(src)
        if m is None or not m.tags:
            return 0
        t = m.tags
        out = ID3()
        pairs = [("\xa9nam", TIT2), ("\xa9ART", TPE1), ("aART", TPE2),
                 ("\xa9alb", TALB), ("\xa9gen", TCON), ("\xa9day", TDRC),
                 ("\xa9cmt", COMM)]
        n = 0
        for atom, frame in pairs:
            try:
                v = t.get(atom)
            except Exception:
                v = None
            if not v:
                continue
            val = v[0] if isinstance(v, (list, tuple)) and v else v
            try:
                out.add(frame(encoding=3, text=str(val)))
                n += 1
            except Exception:
                pass
        try:
            trk = t.get("trkn")
            if trk:
                num = trk[0][0] if isinstance(trk[0], (list, tuple)) else trk[0]
                out.add(TRCK(encoding=3, text=str(num)))
                n += 1
        except Exception:
            pass
        try:
            for c in t.get("covr") or []:
                raw = bytes(c)
                fmt = int(getattr(c, "imageformat", 0) or 0)
                mime = "image/png" if fmt == 14 else "image/jpeg"
                out.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=raw))
                n += 1
                break
        except Exception:
            pass
        if n:
            out.save(dst)
        return n
    except Exception:
        return 0


# --------------------------------------------------------------------------
#  转码
# --------------------------------------------------------------------------
class Cancelled(Exception):
    pass


def convert_file(src: str, dst: str, *, bitrate: int = DEFAULT_BITRATE,
                 channels: int = 0, sample_rate: int = 0,
                 copy_meta: bool = True, progress=None, should_stop=None) -> dict:
    """把 src 转成 dst（MP3, CBR bitrate）。

    channels: 0=保持（>1 声道压成立体声） 1=单声道 2=立体声
    sample_rate: 0=保持（非 MP3 合法率则回落到 44100）
    progress: callable(float 0~1)
    should_stop: callable -> bool，返回 True 时抛 Cancelled
    返回 dict(ok, out, size, dur, elapsed, tags, err)
    """
    import av
    t0 = time.time()
    res = {"ok": False, "out": dst, "size": 0, "dur": 0.0, "elapsed": 0.0, "tags": 0, "err": ""}
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)

    same = os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst))
    tmp = dst + ".slimtone.part" if same else dst
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            tmp = unique_path(tmp)

    inc = outc = None
    try:
        inc = av.open(src)
        if not inc.streams.audio:
            raise RuntimeError("文件里没有音频轨")
        ins = inc.streams.audio[0]
        ictx = ins.codec_context

        src_ch = ictx.channels or 1
        layout = "mono" if (channels == 1 or (channels == 0 and src_ch == 1)) else "stereo"
        rate = sample_rate or ictx.sample_rate or 44100
        if rate not in MP3_RATES:
            rate = 44100
        dur = 0.0
        if ins.duration:
            dur = float(ins.duration * ins.time_base)
        elif inc.duration:
            dur = float(inc.duration) / 1_000_000.0
        res["dur"] = dur

        outc = av.open(tmp, "w", format="mp3")
        outs = outc.add_stream("libmp3lame", rate=rate)
        outs.bit_rate = int(bitrate) * 1000
        outs.layout = layout
        rs = av.AudioResampler(format="fltp", layout=layout, rate=rate)

        done = 0.0
        for frame in inc.decode(ins):
            if should_stop and should_stop():
                raise Cancelled()
            for rf in rs.resample(frame):
                for pkt in outs.encode(rf):
                    outc.mux(pkt)
            try:
                if frame.pts is not None:
                    done = float(frame.pts * frame.time_base)
            except Exception:
                pass
            if progress and dur > 0:
                progress(min(0.999, done / dur))
        for rf in rs.resample(None):
            for pkt in outs.encode(rf):
                outc.mux(pkt)
        for pkt in outs.encode(None):
            outc.mux(pkt)

        outc.close()
        outc = None
        inc.close()
        inc = None

        if same:
            os.replace(tmp, dst)
        res["size"] = os.path.getsize(dst)
        if copy_meta:
            res["tags"] = copy_tags(src, dst)
        if progress:
            progress(1.0)
        res["ok"] = True
    except Cancelled:
        res["err"] = "已取消"
    except Exception as e:
        res["err"] = "%s: %s" % (type(e).__name__, e)
    finally:
        for c in (inc, outc):
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass
        if not res["ok"] and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    res["elapsed"] = time.time() - t0
    return res


def default_out_dir(src_dir: str) -> str:
    """默认输出目录 = 源文件所在目录。"""
    return os.path.abspath(src_dir)
