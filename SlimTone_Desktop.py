#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""瘦音 SlimTone v1.0 — 把 MP3 / M4A 批量转成目标码率 MP3（默认 64k）

界面层：只管 UI 与线程调度；转码逻辑在 slimcore.py。
灰色底 + 彩色主键，菜单栏齐全（文件 / 设置 / 帮助）。

© 永远的兰兰 / Lanlan Eternal
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import slimcore as C  # noqa: E402
from _hardexit import hard_exit  # noqa: E402

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _HAS_DND = True
except Exception:
    _HAS_DND = False

APP_NAME = "瘦音 SlimTone"
APP_VER = "v1.0"
AUTHOR = "© 永远的兰兰"
CFG_PATH = os.path.join(os.path.expanduser("~"), ".slimtone.json")

# ---- 色板（沿用家族风格：灰底 + 彩色主键）----
BG = "#F0F0F0"
CARD = "#FAFAFA"
LINE = "#D8D8D8"
FG = "#333333"
FG2 = "#757575"
GREEN = "#4CAF50"
BLUE = "#2196F3"
RED = "#F44336"
ORANGE = "#FF9800"
GREY = "#9E9E9E"

FONT = "Microsoft YaHei UI"

HELP_TEXT = """🗜️ 瘦音 SlimTone 使用说明

【它是干什么的】
  把一个或一堆 MP3 / M4A 重新编码成更小体积的 MP3，默认 64 kbps。
  典型用途：把高码率音乐/播客压到 64k，塞进老播放器、车载 U 盘、内存卡。

【三步上手】
  1. 点「＋ 加入文件」挑单个/多个文件，或点「📁 加入文件夹」整个目录扫进来
     （也支持直接把文件/文件夹拖进列表）
  2. 选输出目录：默认「与源文件同目录」；想集中放就勾「自定义输出目录」再浏览
  3. 点绿色的「▶ 开始转换」，看总进度条走完即可

【支持的输入】
  MP3、M4A 为主；顺带能吃 M4B / AAC / MP4 / MOV / WAV / FLAC / OGG / OPUS /
  WMA / AIFF / APE / MKA / AMR 等常见格式。输出统一为 .mp3。

【关键设置】
  · 目标码率   默认 64k；另有 32 / 48 / 96 / 128 / 160 / 192 可选
  · 声道       保持原样 / 单声道 / 立体声。人声播客选「单声道」更省更清楚
  · 采样率     保持原样 或 手动指定（22050 / 32000 / 44100 / 48000）
  · 同名文件   跳过 / 覆盖 / 自动改名（加 _64k 后缀）。默认自动改名，最安全
  · 保留标签与封面   把原标题/歌手/专辑/封面搬进新文件
  · 完成后打开输出目录
  · ⚠ 转换后删除源文件   默认关闭。开了会把原文件丢进回收站，请谨慎

【列表操作】
  · 双击某行 → 在资源管理器中定位该文件
  · 选中若干行 → 「－ 移除选中」；「🗑 清空列表」清干净
  · 单行「进度」列实时显示百分比；状态列为 等待/转换中/完成/跳过/失败

【关于体积】
  输出体积 ≈ 原体积 × (目标码率 ÷ 原码率)。320k 的 MP3 降到 64k，约剩 1/5。
  重新编码是有损的：64k 对人声播客足够，音乐细节会有损失。

⚠️ 本工具全程离线运行，不联网、不上传任何文件。
"""

DISCLAIMER = """免责声明 / Disclaimer

1. 瘦音 SlimTone 是纯本地离线工具。音频解码与编码全部在本机完成，不连接互联网、
   不上传任何文件、不收集任何使用数据。
   SlimTone is a purely offline local tool. All decoding/encoding happens on your own
   machine. No internet access, no file upload, no telemetry.

2. 音频重新编码属于有损处理，音质必然下降。请务必先小批量试听确认效果，
   并对重要原始文件自行备份。
   Audio re-encoding is lossy. Quality will degrade. Test on a few files first and
   keep backups of anything irreplaceable.

3. 勾选「转换后删除源文件」后，原文件将被移入系统回收站。开发者不对误删、
   覆盖或任何数据丢失承担责任。
   If "delete source after conversion" is enabled, original files are moved to the
   system Recycle Bin. The developer is not liable for any data loss.

4. 请仅对你拥有合法权利的文件使用本工具。使用者须自行遵守所在地法律法规及
   相关平台的服务条款，不得将本工具用于侵犯版权或其他违法用途。
   Only use this tool on files you have the legal right to process. Users are solely
   responsible for complying with local laws and applicable terms of service, and
   must not use this tool for copyright infringement or any unlawful purpose.

5. 本软件按"原样"（AS-IS）提供，不提供任何明示或暗示的担保。
   This software is provided AS-IS, without warranty of any kind.

6. 本软件仅供个人学习与工作效率提升使用。
   For personal study and productivity use only.

© 永远的兰兰 / Lanlan Eternal"""


def open_in_explorer(path: str):
    try:
        if os.path.isdir(path):
            os.startfile(path)  # noqa: S606
        else:
            subprocess.Popen('explorer /select,"%s"' % os.path.normpath(path))
    except Exception:
        pass


def recycle(path: str):
    """把文件移入回收站（不真删）。"""
    try:
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                        ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

        op = SHFILEOPSTRUCTW()
        op.wFunc = 3
        op.pFrom = os.path.normpath(path) + "\0\0"
        op.fFlags = 0x40 | 0x10 | 0x04 | 0x400
        ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        return not os.path.exists(path)
    except Exception:
        return False


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = self._load_cfg()
        self.rows = []            # [{path, iid}]
        self.by_iid = {}
        self.q = queue.Queue()
        self.busy = False
        self._stop = threading.Event()
        self._prog_last = {}
        self._done = 0
        self._total = 0
        self._fail = 0
        self._skip = 0
        self._t_start = 0.0

        root.title("%s %s — MP3/M4A 转 %dk · 永远的兰兰" % (APP_NAME, APP_VER, C.DEFAULT_BITRATE))
        root.geometry("1060x740")
        root.minsize(880, 560)
        root.configure(bg=BG)
        self._set_icon()

        self._init_vars()
        self._style()
        self._menu()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(90, self._pump)
        self.log("瘦音 SlimTone %s 就绪 · 把 MP3 / M4A 拖进来或点「加入文件」" % APP_VER)
        self.log("提示：输出默认 64 kbps MP3；不勾「删除源文件」时原文件绝不动。")
        if not _HAS_DND:
            self.log("（拖拽功能不可用：未装 tkinterdnd2，用按钮加入即可）")

    # ------------------------------------------------------------------ 基础
    def _set_icon(self):
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    def _load_cfg(self):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _save_cfg(self):
        try:
            with open(CFG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _init_vars(self):
        c = self.cfg
        self.v_bitrate = tk.StringVar(value=str(c.get("bitrate", C.DEFAULT_BITRATE)))
        self.v_chan = tk.StringVar(value=c.get("chan", "0"))
        self.v_rate = tk.StringVar(value=c.get("rate", "0"))
        self.v_same = tk.StringVar(value=c.get("same", C.SAME_RENAME))
        self.v_custom_out = tk.BooleanVar(value=bool(c.get("custom_out", False)))
        self.v_outdir = tk.StringVar(value=c.get("outdir", ""))
        self.v_keep_tree = tk.BooleanVar(value=bool(c.get("keep_tree", True)))
        self.v_tags = tk.BooleanVar(value=bool(c.get("tags", True)))
        self.v_openout = tk.BooleanVar(value=bool(c.get("openout", True)))
        self.v_delsrc = tk.BooleanVar(value=False)
        self.v_jobs = tk.StringVar(value=str(c.get("jobs", 2)))
        self.status_var = tk.StringVar(value="就绪")
        self.count_var = tk.StringVar(value="队列 0 个文件")
        self.pct_var = tk.StringVar(value="0%")

    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                     foreground=FG, rowheight=24, font=(FONT, 9), borderwidth=0)
        st.configure("Treeview.Heading", background="#E4E4E4", foreground=FG,
                     font=(FONT, 9, "bold"), relief="flat")
        st.map("Treeview", background=[("selected", "#BBDEFB")], foreground=[("selected", "#0D47A1")])
        st.configure("Slim.Horizontal.TProgressbar", troughcolor="#DCDCDC",
                     background=GREEN, bordercolor="#DCDCDC", lightcolor=GREEN, darkcolor=GREEN)
        st.configure("TCheckbutton", background=CARD, foreground=FG, font=(FONT, 9))
        st.configure("TCombobox", font=(FONT, 9))
        st.configure("TLabelframe", background=CARD)
        st.configure("TLabelframe.Label", background=CARD, foreground=FG2, font=(FONT, 9, "bold"))

    # ------------------------------------------------------------------ 菜单
    def _menu(self):
        m = tk.Menu(self.root, font=(FONT, 9))
        f = tk.Menu(m, tearoff=0, font=(FONT, 9))
        f.add_command(label="加入文件…", accelerator="Ctrl+O", command=self.add_files)
        f.add_command(label="加入文件夹…", accelerator="Ctrl+D", command=self.add_folder)
        f.add_separator()
        f.add_command(label="移除选中", command=self.remove_sel)
        f.add_command(label="清空列表", accelerator="Ctrl+L", command=self.clear_all)
        f.add_separator()
        f.add_command(label="退出", command=self.on_close)
        m.add_cascade(label="文件", menu=f)

        s = tk.Menu(m, tearoff=0, font=(FONT, 9))
        s.add_command(label="打开输出目录", command=self.open_outdir_maybe)
        s.add_separator()
        s.add_command(label="恢复默认设置", command=self.reset_settings)
        m.add_cascade(label="设置", menu=s)

        h = tk.Menu(m, tearoff=0, font=(FONT, 9))
        h.add_command(label="使用说明", command=lambda: self.text_win("使用说明", HELP_TEXT, 760, 640))
        h.add_command(label="免责声明", command=lambda: self.text_win("免责声明", DISCLAIMER, 720, 560))
        h.add_separator()
        h.add_command(label="关于 瘦音 SlimTone", command=self.about)
        m.add_cascade(label="帮助", menu=h)
        self.root.config(menu=m)

        self.root.bind("<Control-o>", lambda e: self.add_files())
        self.root.bind("<Control-d>", lambda e: self.add_folder())
        self.root.bind("<Control-l>", lambda e: self.clear_all())
        self.root.bind("<F5>", lambda e: self.start())
        self.root.bind("<Delete>", lambda e: self.remove_sel())

    def text_win(self, title, body, w, h):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=BG)
        win.geometry("%dx%d" % (w, h))
        win.transient(self.root)
        box = tk.Frame(win, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        box.pack(fill="both", expand=True, padx=10, pady=10)
        t = tk.Text(box, wrap="word", font=(FONT, 9), bg=CARD, fg=FG,
                    relief="flat", width=30, height=10, padx=12, pady=10)
        t.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(box, orient="vertical", command=t.yview)
        sb.pack(side="right", fill="y")
        t.config(yscrollcommand=sb.set)
        t.insert("1.0", body)
        t.config(state="disabled")

    def about(self):
        messagebox.showinfo(
            "关于 瘦音 SlimTone",
            "%s %s\n\n把 MP3 / M4A 批量转成目标码率 MP3（默认 64 kbps）。\n"
            "全程本地离线，不联网、不上传。\n\n"
            "解码：PyAV（内置 FFmpeg）\n编码：libmp3lame CBR\n标签：mutagen\n\n"
            "%s\nLanlan Eternal" % (APP_NAME, APP_VER, AUTHOR),
            parent=self.root)

    # ------------------------------------------------------------------ 布局
    def _build(self):
        # 顶部标题条
        tb = tk.Frame(self.root, bg="#37474F", height=34)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="🗜️  瘦音 SlimTone", font=(FONT, 11, "bold"),
                 bg="#37474F", fg="white").pack(side="left", padx=12)
        tk.Label(tb, text="MP3 / M4A → %s kbps MP3" % self.v_bitrate.get(),
                 font=(FONT, 8), bg="#37474F", fg="#B0BEC5").pack(side="left")
        tk.Label(tb, text=AUTHOR, font=(FONT, 8), bg="#37474F", fg="#B0BEC5").pack(side="right", padx=12)
        self.tb_sub = tb

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=10, pady=(8, 4))

        # ---- 工具条（先 pack，避免被 Treeview 挤扁）----
        bar = tk.Frame(main, bg=BG)
        bar.pack(fill="x", pady=(0, 6))
        self.b_addf = self._btn(bar, "＋ 加入文件", self.add_files, BLUE)
        self.b_addd = self._btn(bar, "📁 加入文件夹", self.add_folder, BLUE)
        self.b_rm = self._btn(bar, "－ 移除选中", self.remove_sel, GREY)
        self.b_clr = self._btn(bar, "🗑 清空列表", self.clear_all, GREY)
        tk.Label(bar, textvariable=self.count_var, bg=BG, fg=FG2, font=(FONT, 9)).pack(side="right", padx=6)

        # ---- 设置区（左：输入输出，右：转换参数）----
        cfgwrap = tk.Frame(main, bg=BG)
        cfgwrap.pack(fill="x", pady=(0, 6))
        left = tk.LabelFrame(cfgwrap, text=" 输出位置 ", bg=CARD, fg=FG2,
                             font=(FONT, 9, "bold"), bd=1, relief="solid",
                             highlightbackground=LINE, labelanchor="nw")
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = tk.LabelFrame(cfgwrap, text=" 转换设置 ", bg=CARD, fg=FG2,
                              font=(FONT, 9, "bold"), bd=1, relief="solid",
                              highlightbackground=LINE, labelanchor="nw")
        right.pack(side="right", fill="both", expand=True)
        self._build_out(left)
        self._build_opts(right)

        # ---- 队列表：必须关进独立 Frame ----
        twrap = tk.Frame(main, bg=BG)
        twrap.pack(fill="both", expand=True)
        tframe = tk.Frame(twrap, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        tframe.pack(fill="both", expand=True)
        cols = ("idx", "name", "dur", "src", "dst", "status", "prog")
        self.tv = ttk.Treeview(tframe, columns=cols, show="headings", selectmode="extended")
        heads = (("idx", "#", 46, "center"), ("name", "文件名", 340, "w"),
                 ("dur", "时长", 78, "center"), ("src", "原始", 120, "center"),
                 ("dst", "目标", 96, "center"), ("status", "状态", 96, "center"),
                 ("prog", "进度", 74, "center"))
        for cid, txt, w, anc in heads:
            self.tv.heading(cid, text=txt)
            self.tv.column(cid, width=w, anchor=anc, stretch=(cid == "name"))
        vs = ttk.Scrollbar(tframe, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tv.pack(side="left", fill="both", expand=True)
        self.tv.tag_configure("ok", foreground="#1B5E20")
        self.tv.tag_configure("err", foreground="#B71C1C")
        self.tv.tag_configure("skip", foreground="#9E9E9E")
        self.tv.tag_configure("run", foreground="#0D47A1")
        self.tv.bind("<Double-1>", self._on_dbl)

        if _HAS_DND:
            try:
                self.tv.drop_target_register(DND_FILES)
                self.tv.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        # ---- 日志：固定高度，独立帧 ----
        lf = tk.LabelFrame(main, text=" 运行日志 ", bg=CARD, fg=FG2,
                           font=(FONT, 9, "bold"), bd=1, relief="solid",
                           highlightbackground=LINE, labelanchor="nw", height=132)
        lf.pack(fill="x", pady=(6, 0))
        lf.pack_propagate(False)
        self.log_txt = tk.Text(lf, wrap="none", font=("Consolas", 9), bg="#FBFBFB",
                               fg="#424242", relief="flat", width=30, height=6, padx=8, pady=4)
        lsb = ttk.Scrollbar(lf, orient="vertical", command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self.log_txt.pack(side="left", fill="both", expand=True)

        # ---- 底部：操作 + 进度 ----
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill="x", padx=10, pady=(0, 8))
        self.b_go = tk.Button(foot, text="▶  开始转换", command=self.start,
                              font=(FONT, 11, "bold"), bg=GREEN, fg="white",
                              activebackground="#388E3C", activeforeground="white",
                              relief="flat", bd=0, padx=18, pady=7, cursor="hand2")
        self.b_go.pack(side="left")
        self.b_stop = tk.Button(foot, text="■  停止", command=self.stop,
                                font=(FONT, 11, "bold"), bg=RED, fg="white",
                                activebackground="#C62828", activeforeground="white",
                                relief="flat", bd=0, padx=18, pady=7, cursor="hand2",
                                state="disabled")
        self.b_stop.pack(side="left", padx=8)

        pf = tk.Frame(foot, bg=BG)
        pf.pack(side="right", fill="x", expand=True, padx=(14, 0))
        self.pb = ttk.Progressbar(pf, style="Slim.Horizontal.TProgressbar",
                                  orient="horizontal", mode="determinate", maximum=1000)
        self.pb.pack(fill="x", pady=(4, 2))
        tk.Label(pf, textvariable=self.status_var, bg=BG, fg=FG,
                 font=(FONT, 9), anchor="w").pack(fill="x")
        tk.Label(foot, textvariable=self.pct_var, bg=BG, fg=FG,
                 font=(FONT, 13, "bold")).pack(side="right", padx=(10, 0))

    def _btn(self, parent, text, cmd, color):
        b = tk.Button(parent, text=text, command=cmd, font=(FONT, 9, "bold"),
                      bg=color, fg="white", activebackground=color, activeforeground="white",
                      relief="flat", bd=0, padx=12, pady=5, cursor="hand2")
        b.pack(side="left", padx=(0, 6))
        return b

    def _lbl(self, parent, text):
        return tk.Label(parent, text=text, bg=CARD, fg=FG, font=(FONT, 9))

    def _build_out(self, f):
        r1 = tk.Frame(f, bg=CARD)
        r1.pack(fill="x", padx=10, pady=(8, 2))
        ttk.Radiobutton(r1, text="与源文件同目录", variable=self.v_custom_out,
                        value=False, command=self._sync_out_state).pack(side="left")
        ttk.Radiobutton(r1, text="自定义输出目录", variable=self.v_custom_out,
                        value=True, command=self._sync_out_state).pack(side="left", padx=(14, 0))
        r2 = tk.Frame(f, bg=CARD)
        r2.pack(fill="x", padx=10, pady=(2, 2))
        self.e_out = tk.Entry(r2, textvariable=self.v_outdir, font=(FONT, 9), bg="white",
                              relief="solid", bd=1)
        self.e_out.pack(side="left", fill="x", expand=True, ipady=3)
        self.b_browse = tk.Button(r2, text="浏览…", command=self.pick_outdir, font=(FONT, 9),
                                  bg=BLUE, fg="white", relief="flat", bd=0, padx=10, pady=2,
                                  cursor="hand2")
        self.b_browse.pack(side="left", padx=(6, 0))
        r3 = tk.Frame(f, bg=CARD)
        r3.pack(fill="x", padx=10, pady=(4, 8))
        self.cb_tree = ttk.Checkbutton(r3, text="保留子目录结构（按加入时的目录层级还原）",
                                       variable=self.v_keep_tree)
        self.cb_tree.pack(side="left")
        self._sync_out_state()

    def _build_opts(self, f):
        r1 = tk.Frame(f, bg=CARD)
        r1.pack(fill="x", padx=10, pady=(8, 2))
        self._lbl(r1, "目标码率").pack(side="left")
        cb1 = ttk.Combobox(r1, textvariable=self.v_bitrate, width=9, state="readonly",
                           values=["%d kbps" % b for b in C.BITRATES])
        cb1.pack(side="left", padx=(6, 14))
        self.v_bitrate.set("%s kbps" % self.v_bitrate.get())
        cb1.bind("<<ComboboxSelected>>", lambda e: self._bitrate_changed())
        self._lbl(r1, "声道").pack(side="left")
        ttk.Combobox(r1, textvariable=self.v_chan, width=10, state="readonly",
                     values=["保持原样", "单声道", "立体声"]).pack(side="left", padx=(6, 0))
        self.v_chan.set({0: "保持原样", 1: "单声道", 2: "立体声"}.get(int(self.v_chan.get() or 0), "保持原样"))

        r2 = tk.Frame(f, bg=CARD)
        r2.pack(fill="x", padx=10, pady=(4, 2))
        self._lbl(r2, "采样率").pack(side="left")
        ttk.Combobox(r2, textvariable=self.v_rate, width=12, state="readonly",
                     values=["保持原样", "22050", "32000", "44100", "48000"]).pack(side="left", padx=(6, 14))
        self.v_rate.set("保持原样" if str(self.v_rate.get()) in ("0", "") else self.v_rate.get())
        self._lbl(r2, "同名文件").pack(side="left")
        ttk.Combobox(r2, textvariable=self.v_same, width=12, state="readonly",
                     values=["自动改名", "跳过", "覆盖"]).pack(side="left", padx=(6, 0))
        self.v_same.set({"rename": "自动改名", "skip": "跳过",
                         "overwrite": "覆盖"}.get(self.v_same.get(), "自动改名"))

        r3 = tk.Frame(f, bg=CARD)
        r3.pack(fill="x", padx=10, pady=(4, 0))
        r4 = tk.Frame(f, bg=CARD)
        r4.pack(fill="x", padx=10, pady=(2, 8))
        self._lbl(r3, "并发数").pack(side="left")
        ttk.Combobox(r3, textvariable=self.v_jobs, width=4, state="readonly",
                     values=["1", "2", "3", "4", "6", "8"]).pack(side="left", padx=(6, 14))
        self._lbl(r3, "（越大越快，吃 CPU）").pack(side="left")
        ttk.Checkbutton(r4, text="保留标签与封面", variable=self.v_tags).pack(side="left")
        ttk.Checkbutton(r4, text="完成后打开输出目录", variable=self.v_openout).pack(side="left", padx=(12, 0))
        r5 = tk.Frame(f, bg=CARD)
        r5.pack(fill="x", padx=10, pady=(0, 8))
        self.cb_del = tk.Checkbutton(
            r5, text="⚠ 转换成功后把源文件移入回收站（危险）", variable=self.v_delsrc,
            bg=CARD, fg="#B71C1C", activebackground=CARD, font=(FONT, 9),
            command=self._confirm_delsrc)
        self.cb_del.pack(side="left")

    def _bitrate_changed(self):
        br = self._get_bitrate()
        try:
            self.tb_sub.winfo_children()[1].config(text="MP3 / M4A → %d kbps MP3" % br)
        except Exception:
            pass

    def _sync_out_state(self):
        on = bool(self.v_custom_out.get())
        self.e_out.config(state="normal" if on else "disabled",
                          bg="white" if on else "#EDEDED")
        self.b_browse.config(state="normal" if on else "disabled",
                             bg=BLUE if on else "#BDBDBD")
        if hasattr(self, "cb_tree"):
            self.cb_tree.config(state="normal" if on else "disabled")
            if not on:
                self.v_keep_tree.set(False)
            elif not self.v_keep_tree.get():
                self.v_keep_tree.set(True)

    def _confirm_delsrc(self):
        if self.v_delsrc.get():
            if not messagebox.askyesno(
                    "确认危险操作",
                    "勾选后，每个转换成功的源文件都会被移入回收站。\n\n"
                    "请确认你已经备份好原始文件。\n\n确定要开启吗？", parent=self.root):
                self.v_delsrc.set(False)

    # ------------------------------------------------------------------ 取值
    def _get_bitrate(self) -> int:
        s = str(self.v_bitrate.get())
        try:
            return int("".join(ch for ch in s if ch.isdigit()) or C.DEFAULT_BITRATE)
        except Exception:
            return C.DEFAULT_BITRATE

    def _get_chan(self) -> int:
        return {"保持原样": 0, "单声道": 1, "立体声": 2}.get(str(self.v_chan.get()), 0)

    def _get_rate(self) -> int:
        s = str(self.v_rate.get())
        return int(s) if s.isdigit() else 0

    def _get_same(self) -> str:
        return {"自动改名": C.SAME_RENAME, "跳过": C.SAME_SKIP,
                "覆盖": C.SAME_OVERWRITE}.get(str(self.v_same.get()), C.SAME_RENAME)

    def _settings(self) -> dict:
        """主线程预取全部设置 —— worker 线程绝不读 tk 变量。"""
        return {
            "bitrate": self._get_bitrate(),
            "chan": self._get_chan(),
            "rate": self._get_rate(),
            "same": self._get_same(),
            "custom_out": bool(self.v_custom_out.get()),
            "outdir": self.v_outdir.get().strip(),
            "keep_tree": bool(self.v_keep_tree.get()),
            "tags": bool(self.v_tags.get()),
            "openout": bool(self.v_openout.get()),
            "delsrc": bool(self.v_delsrc.get()),
            "jobs": max(1, int(self.v_jobs.get() or 2)),
        }

    # ------------------------------------------------------------------ 加入
    def _add_paths(self, paths):
        exist = {r["path"] for r in self.rows}
        added = 0
        for p in paths:
            p = os.path.abspath(p)
            if os.path.isdir(p):
                for f in C.scan_folder(p, True):
                    if f not in exist:
                        exist.add(f)
                        self._append(f, p)
                        added += 1
                continue
            if not os.path.isfile(p):
                continue
            if not C.is_audio(p):
                continue
            if p in exist:
                continue
            exist.add(p)
            self._append(p, os.path.dirname(p))
            added += 1
        if added:
            self.log("加入 %d 个音频文件" % added)
        else:
            self.log("没有新增文件（可能已在队列里，或不是支持的音频格式）")
        self._refresh_count()

    def _append(self, path, base_root):
        iid = "r%d" % (len(self.rows) + 1)
        while iid in self.by_iid:
            iid += "x"
        info = C.probe(path)
        row = {"path": path, "iid": iid, "info": info, "root": base_root or os.path.dirname(path)}
        self.rows.append(row)
        self.by_iid[iid] = row
        src = "%s %s" % (info["codec"], ("%dk" % round(info["br"] / 1000)) if info["br"] else "-")
        self.tv.insert("", "end", iid=iid, values=(
            len(self.rows), os.path.basename(path), C.fmt_dur(info["dur"]),
            src, "MP3 %dk" % self._get_bitrate(), "等待", ""))
        if info["err"]:
            self.tv.item(iid, tags=("err",))
            self.tv.set(iid, "status", "异常")

    def add_files(self):
        if self.busy:
            return
        fps = filedialog.askopenfilenames(
            title="选择音频文件",
            filetypes=[("音频文件", "*.mp3 *.m4a *.m4b *.aac *.mp4 *.wav *.flac *.ogg *.opus *.wma"),
                       ("MP3", "*.mp3"), ("M4A", "*.m4a"), ("全部文件", "*.*")],
            parent=self.root)
        if fps:
            self._add_paths(list(fps))

    def add_folder(self):
        if self.busy:
            return
        d = filedialog.askdirectory(title="选择要扫描的文件夹（含子目录）", parent=self.root)
        if d:
            self._add_paths([d])

    def _on_drop(self, event):
        if self.busy:
            return
        try:
            items = self.root.tk.splitlist(event.data)
        except Exception:
            items = [event.data]
        self._add_paths([i for i in items if i])

    def remove_sel(self):
        if self.busy:
            return
        sel = list(self.tv.selection())
        if not sel:
            return
        for iid in sel:
            row = self.by_iid.pop(iid, None)
            if row in self.rows:
                self.rows.remove(row)
            self.tv.delete(iid)
        self._renumber()
        self.log("移除 %d 项" % len(sel))
        self._refresh_count()

    def clear_all(self):
        if self.busy:
            return
        if self.rows and not messagebox.askyesno("清空列表", "确定要清空全部 %d 项吗？" % len(self.rows),
                                                parent=self.root):
            return
        self.tv.delete(*self.tv.get_children())
        self.rows.clear()
        self.by_iid.clear()
        self.pb["value"] = 0
        self.pct_var.set("0%")
        self.status_var.set("就绪")
        self._refresh_count()
        self.log("列表已清空")

    def _renumber(self):
        for i, r in enumerate(self.rows, 1):
            try:
                self.tv.set(r["iid"], "idx", i)
            except Exception:
                pass

    def _refresh_count(self):
        n = len(self.rows)
        secs = sum((r["info"].get("dur") or 0) for r in self.rows)
        mb = sum((r["info"].get("size") or 0) for r in self.rows) / 1048576.0
        self.count_var.set("队列 %d 个 · 时长 %s · 原始 %s" % (n, C.fmt_dur(secs), C.human_size(mb)))

    def _on_dbl(self, _e):
        sel = self.tv.selection()
        if sel and sel[0] in self.by_iid:
            open_in_explorer(self.by_iid[sel[0]]["path"])

    def pick_outdir(self):
        d = filedialog.askdirectory(title="选择输出目录", parent=self.root)
        if d:
            self.v_outdir.set(os.path.normpath(d))

    def open_outdir_maybe(self):
        s = self._settings()
        d = s["outdir"] if s["custom_out"] and s["outdir"] else ""
        if not d:
            d = os.path.dirname(self.rows[0]["path"]) if self.rows else ""
        if d and os.path.isdir(d):
            os.startfile(d)  # noqa: S606
        else:
            messagebox.showinfo("打开输出目录", "还没有可打开的输出目录。", parent=self.root)

    def reset_settings(self):
        self.v_bitrate.set("%d kbps" % C.DEFAULT_BITRATE)
        self.v_chan.set("保持原样")
        self.v_rate.set("保持原样")
        self.v_same.set("自动改名")
        self.v_custom_out.set(False)
        self.v_keep_tree.set(True)
        self.v_tags.set(True)
        self.v_openout.set(True)
        self.v_delsrc.set(False)
        self.v_jobs.set("2")
        self._sync_out_state()
        self._bitrate_changed()
        self.log("设置已恢复默认")

    # ------------------------------------------------------------------ 日志
    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        try:
            self.log_txt.insert("end", "[%s] %s\n" % (ts, msg))
            self.log_txt.see("end")
            if int(self.log_txt.index("end-1c").split(".")[0]) > 800:
                self.log_txt.delete("1.0", "200.0")
        except Exception:
            pass

    # ------------------------------------------------------------------ 开始
    def start(self):
        if self.busy:
            return
        if not self.rows:
            messagebox.showinfo("没有文件", "先加入要转换的 MP3 / M4A 文件吧。", parent=self.root)
            return
        s = self._settings()
        if s["custom_out"]:
            if not s["outdir"]:
                messagebox.showwarning("缺少输出目录", "勾了「自定义输出目录」，但还没选目录。", parent=self.root)
                return
            try:
                os.makedirs(s["outdir"], exist_ok=True)
            except Exception as e:
                messagebox.showerror("输出目录不可用", str(e), parent=self.root)
                return
        if s["delsrc"] and not messagebox.askyesno(
                "最后确认",
                "已开启「转换成功后把源文件移入回收站」。\n\n确定继续吗？", parent=self.root):
            return

        for r in self.rows:
            self.tv.item(r["iid"], tags=())
            self.tv.set(r["iid"], "status", "等待")
            self.tv.set(r["iid"], "prog", "")
        self._stop.clear()
        self._prog_last.clear()
        self._done = self._fail = self._skip = 0
        self._total = len(self.rows)
        self._t_start = time.time()
        self.busy = True
        self.b_go.config(state="disabled", bg="#A5D6A7")
        self.b_stop.config(state="normal")
        for b in (self.b_addf, self.b_addd, self.b_rm, self.b_clr):
            b.config(state="disabled")
        self.pb["value"] = 0
        self.pct_var.set("0%")
        self.log("开始转换 %d 个文件 · 目标 %d kbps · 并发 %d"
                 % (self._total, s["bitrate"], s["jobs"]))

        items = [dict(path=r["path"], iid=r["iid"], root=r["root"]) for r in self.rows]
        th = threading.Thread(target=self._worker_entry, args=(items, s), daemon=True)
        th.start()

    def stop(self):
        if not self.busy:
            return
        self._stop.set()
        self.log("已请求停止 —— 当前文件收尾后中断")
        self.b_stop.config(state="disabled")

    def _worker_entry(self, items, s):
        """线程调度：N 个 worker 抢同一个索引。所有 UI 交互一律走 self.q。"""
        idx = {"n": 0}
        lock = threading.Lock()

        def take():
            with lock:
                i = idx["n"]
                if i >= len(items):
                    return None
                idx["n"] = i + 1
                return items[i]

        def run_one(it):
            src = it["path"]
            iid = it["iid"]
            if self._stop.is_set():
                self.q.put(("status", iid, "已取消", "skip"))
                self.q.put(("skip", iid, 1, 2))
                return
            # 自定义输出目录才谈「保留子目录结构」；否则一律就地输出
            src_size = os.path.getsize(src) if os.path.exists(src) else 0
            if s["custom_out"] and s["outdir"]:
                out_dir = s["outdir"]
                base = it["root"] if s["keep_tree"] else ""
            else:
                out_dir = os.path.dirname(src)
                base = ""
            dst = C.plan_output(src, out_dir, base, s["keep_tree"], s["bitrate"], s["same"])
            inplace = os.path.normcase(os.path.abspath(dst)) == os.path.normcase(os.path.abspath(src))
            if s["same"] == C.SAME_SKIP and not inplace and os.path.exists(dst):
                self.q.put(("status", iid, "已存在·跳过", "skip"))
                self.q.put(("skip", iid, 1, 2))
                return
            if s["same"] == C.SAME_RENAME and not inplace and os.path.exists(dst):
                dst = C.unique_path(dst)

            self.q.put(("status", iid, "转换中…", "run"))

            def prog(f):
                k = int(f * 100)
                if k - self._prog_last.get(iid, -1) >= 1:
                    self._prog_last[iid] = k
                    self.q.put(("prog", iid, k))

            r = C.convert_file(src, dst, bitrate=s["bitrate"], channels=s["chan"],
                               sample_rate=s["rate"], copy_meta=s["tags"],
                               progress=prog, should_stop=self._stop.is_set)
            if r["ok"]:
                note = ""
                if s["delsrc"] and not inplace:
                    note = " · 源已入回收站" if recycle(src) else " · 源删除失败"
                elif s["delsrc"] and inplace:
                    note = " · 就地覆盖，未删源"
                self.q.put(("status", iid, "完成", "ok"))
                self.q.put(("prog", iid, 100))
                self.q.put(("log", None, "✅ %s → %s（%s → %s，%.1fs）%s" % (
                    os.path.basename(src), os.path.basename(dst),
                    C.human_size(src_size), C.human_size(r["size"]), r["elapsed"], note)))
                self.q.put(("done", iid, 1, 0))
            else:
                if self._stop.is_set():
                    self.q.put(("status", iid, "已取消", "skip"))
                    self.q.put(("skip", iid, 1, 2))
                else:
                    self.q.put(("status", iid, "失败", "err"))
                    self.q.put(("log", None, "❌ %s ：%s" % (os.path.basename(src), r["err"])))
                    self.q.put(("fail", iid, 1, 3))

        def worker():
            while True:
                it = take()
                if it is None:
                    break
                try:
                    run_one(it)
                except Exception as e:  # worker 绝不能静默死掉
                    self.q.put(("status", it["iid"], "失败", "err"))
                    self.q.put(("log", None, "❌ %s ：%s" % (os.path.basename(it["path"]), e)))
                    self.q.put(("fail", it["iid"], 1, 3))

        n = max(1, int(s["jobs"]))
        n = min(n, max(1, len(items)))
        threads = [threading.Thread(target=worker, daemon=True) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.q.put(("finish", None, s))

    # ------------------------------------------------------------------ 轮询
    def _pump(self):
        try:
            while True:
                ev = self.q.get_nowait()
                self._apply(ev)
        except queue.Empty:
            pass
        except Exception:
            pass
        self.root.after(90, self._pump)

    def _apply(self, ev):
        kind = ev[0]
        if kind == "prog":
            iid, k = ev[1], ev[2]
            if iid in self.by_iid:
                self.tv.set(iid, "prog", "%d%%" % k)
        elif kind == "status":
            iid, txt, tag = ev[1], ev[2], ev[3]
            if iid in self.by_iid:
                self.tv.set(iid, "status", txt)
                try:
                    self.tv.item(iid, tags=(tag,))
                except Exception:
                    pass
        elif kind == "log":
            self.log(ev[2])
        elif kind in ("done", "fail", "skip"):
            if kind == "done":
                self._done += 1
            elif kind == "fail":
                self._fail += 1
            else:
                self._skip += 1
            self._tick()
        elif kind == "finish":
            self._finish()

    def _tick(self):
        if self._total <= 0:
            return
        frac = (self._done + self._fail + self._skip) / float(self._total)
        self.pb["value"] = max(0, min(1000, frac * 1000))
        p = int(frac * 100)
        self.pct_var.set("%d%%" % p)
        self.status_var.set("已完成 %d / %d（失败 %d · 跳过 %d）"
                            % (self._done + self._fail + self._skip, self._total,
                               self._fail, self._skip))

    def _finish(self):
        self.busy = False
        self.b_go.config(state="normal", bg=GREEN)
        self.b_stop.config(state="disabled")
        for b in (self.b_addf, self.b_addd, self.b_rm, self.b_clr):
            b.config(state="normal")
        self.pb["value"] = 1000 if self._done else 0
        self.pct_var.set("%d%%" % (int(self._done / float(max(1, self._total)) * 100)))
        el = time.time() - self._t_start
        self.status_var.set("完成 %d · 失败 %d · 跳过 %d · 用时 %.1fs"
                            % (self._done, self._fail, self._skip, el))
        self.log("—— 结束：成功 %d，失败 %d，跳过 %d，用时 %.1fs ——"
                 % (self._done, self._fail, self._skip, el))
        s = self._settings()
        if self._done and s["openout"]:
            d = s["outdir"] if (s["custom_out"] and s["outdir"]) \
                else (os.path.dirname(self.rows[0]["path"]) if self.rows else "")
            if d and os.path.isdir(d):
                try:
                    os.startfile(d)  # noqa: S606
                except Exception:
                    pass
        try:
            self.root.bell()
        except Exception:
            pass

    # ------------------------------------------------------------------ 关闭
    def on_close(self):
        if self.busy:
            if not messagebox.askyesno("正在转换", "还在转换中，确定要退出吗？", parent=self.root):
                return
            self._stop.set()
        s = self._settings()
        self.cfg.update({
            "bitrate": s["bitrate"], "chan": s["chan"], "rate": s["rate"], "same": s["same"],
            "custom_out": s["custom_out"], "outdir": s["outdir"], "keep_tree": s["keep_tree"],
            "tags": s["tags"], "openout": s["openout"], "jobs": s["jobs"],
        })
        self._save_cfg()
        try:
            self.root.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
#  无头自检：--selftest 生成音频并走一遍转换，验证打包后依赖完整
# ---------------------------------------------------------------------------
def selftest():
    """无头自检：--selftest 生成音频并走一遍转换，验证依赖完整。

    windowed 版 EXE 没有控制台，print 无处可去 —— 所以同时写一份日志到
    %TEMP%\\slimtone_selftest.txt，用退出码给调用方判成败。
    """
    import math

    log_path = os.path.join(os.environ.get("TEMP", "."), "slimtone_selftest.txt")
    lines = []

    def say(msg):
        lines.append(msg)
        try:
            if sys.stdout is not None:
                print(msg)
        except Exception:
            pass

    def flush_log():
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception:
            pass

    say("SlimTone selftest  %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    say("frozen = %s" % getattr(sys, "frozen", False))
    try:
        import av
        say("  av         : %s" % av.__version__)
        say("  libmp3lame : %s" % ("libmp3lame" in av.codecs_available))
        aac_ok = "aac" in av.codecs_available
        say("  aac 解码器  : %s" % aac_ok)
    except Exception as e:
        say("  av 导入失败 : %s: %s" % (type(e).__name__, e))
        flush_log()
        return 1
    try:
        import mutagen
        from mutagen.mp3 import MP3
        say("  mutagen    : %s" % getattr(mutagen, "version_string", "?"))
    except Exception as e:
        say("  mutagen 导入失败 : %s: %s" % (type(e).__name__, e))
        flush_log()
        return 1
    try:
        import tkinter
        say("  tkinter    : %s" % tkinter.TkVersion)
    except Exception as e:
        say("  tkinter 导入失败 : %s: %s" % (type(e).__name__, e))
        flush_log()
        return 1
    try:
        import tkinterdnd2  # noqa: F401
        say("  tkinterdnd2: OK")
    except Exception as e:
        say("  tkinterdnd2: 不可用（拖拽关闭） %s" % e)

    tmp = os.path.join(os.environ.get("TEMP", "."), "slimtone_selftest_%d" % time.time())
    os.makedirs(tmp, exist_ok=True)
    src = os.path.join(tmp, "t.m4a")
    rate, secs = 48000, 1.5
    try:
        out = av.open(src, "w", format="ipod")
        st = out.add_stream("aac", rate=rate)
        st.layout = "stereo"
        rs = av.AudioResampler(format="fltp", layout="stereo", rate=rate)
        total, pos, step = int(rate * secs), 0, 1024
        from fractions import Fraction
        while pos < total:
            n = min(step, total - pos)
            fr = av.AudioFrame(format="fltp", layout="stereo", samples=n)
            fr.sample_rate = rate
            for pi, pl in enumerate(fr.planes):
                arr = memoryview(pl).cast("f")
                for k in range(n):
                    arr[k] = 0.2 * math.sin(2 * math.pi * 440 * (pos + k) / rate)
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
    except Exception as e:
        say("  造样本失败 : %s: %s" % (type(e).__name__, e))
        flush_log()
        return 1

    dst = os.path.join(tmp, "t_64k.mp3")
    try:
        r = C.convert_file(src, dst, bitrate=64)
    except Exception as e:
        say("  转码抛异常 : %s: %s" % (type(e).__name__, e))
        flush_log()
        return 1
    if not r["ok"]:
        say("  转码失败   : %s" % r["err"])
        flush_log()
        return 1
    br = round(MP3(dst).info.bitrate / 1000)
    ok = abs(br - 64) <= 2
    say("  m4a → 64k  : %s  %.0f B → %.0f B  实测 %dk"
        % ("OK" if ok else "FAIL", os.path.getsize(src), r["size"], br))
    say("SELFTEST %s   log=%s" % ("PASS" if ok else "FAIL", log_path))
    flush_log()
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        hard_exit(selftest())
    if "--convert" in sys.argv:
        i = sys.argv.index("--convert")
        src, dst = sys.argv[i + 1], sys.argv[i + 2]
        br = int(sys.argv[i + 3]) if len(sys.argv) > i + 3 else 64
        r = C.convert_file(src, dst, bitrate=br)
        try:
            if sys.stdout is not None:
                print("OK" if r["ok"] else "FAIL", r)
        except Exception:
            pass
        hard_exit(0 if r["ok"] else 1)

    root = TkinterDnD.Tk() if _HAS_DND else tk.Tk()
    App(root)
    root.mainloop()
    hard_exit(0)


if __name__ == "__main__":
    main()
