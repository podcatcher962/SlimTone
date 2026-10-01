# 瘦音 SlimTone v1.0

**把 MP3 / M4A 批量转成 64 kbps MP3 的桌面工具**（码率可选 32~192k），类似「格式工厂」但只做这一件事。

© 永远的兰兰 / Lanlan Eternal

---

## 一句话

扔进来一堆 MP3/M4A → 统一压成 64k MP3，用来塞车载 U 盘、老播放器、内存卡；
全程离线，原文件默认一个都不动。

## 功能

| 分类 | 能力 |
|---|---|
| 加入方式 | ＋ 加入文件（可多选）、📁 加入文件夹（递归扫子目录）、**拖拽文件/文件夹进列表**、双击行定位文件 |
| 输出位置 | 与源文件同目录（默认）／自定义输出目录；可**保留子目录结构** |
| 目标码率 | 32 / 48 / **64** / 96 / 128 / 160 / 192 kbps（CBR，libmp3lame） |
| 音频处理 | 声道：保持原样 / 单声道 / 立体声；采样率：保持原样 / 22050 / 32000 / 44100 / 48000 |
| 同名策略 | 自动改名（加 `_64k`，默认）／ 跳过已转换过的 ／ 覆盖（走临时文件，安全） |
| 标签 | 保留标题 / 歌手 / 专辑 / 封面（MP3 的 ID3 直搬；M4A 的 iTunes 原子映射成 ID3） |
| 批量控制 | 并发数 1~8、实时单行进度%、总进度条、可用「■ 停止」中断 |
| 安全 | 转换中先写 `.slimtone.part` 再原子替换；失败/取消不留残片；源文件默认不删 |
| 可选危险项 | ⚠ 转换成功后把源文件移入**回收站**（默认关闭，开启需二次确认；就地覆盖时不删） |
| 其他 | 菜单栏齐全（文件/设置/帮助→使用说明·免责声明·关于）、日志区、设置自动记忆 |

## 支持的输入格式

主用 **MP3 / M4A**。顺带能吃：M4B、AAC、MP4、M4V、MOV、WAV、FLAC、OGG、OGA、OPUS、WMA、AIF/AIFF、APE、MKA、AMR、3GP、WV。
输出统一为 `.mp3`（MP3 只支持单声道/立体声，多声道源会自动下混成立体声）。

## 体积与音质

输出体积 ≈ 原体积 × (目标码率 ÷ 原码率)。320k 的 MP3 降到 64k 约为 **1/5**。

重新编码是**有损**的：64k 对人声播客/有声书足够，音乐细节会有损失。重要原始文件请先备份。

## 技术

| 环节 | 用什么 |
|---|---|
| 解码 | PyAV 19（自带 FFmpeg，纯 wheel 安装，无需外部 ffmpeg.exe） |
| 编码 | libmp3lame（PyAV 内置），CBR，`quality` 默认 |
| 标签 | mutagen（ID3 / MP4 atoms） |
| 界面 | tkinter（系统 Python 3.12，`clam` 主题 + 自定义配色） |
| 打包 | PyInstaller `--onefile --windowed`，单文件 EXE，无需装 Python |

> 为什么不用 miniaudio + lameenc？因为 **miniaudio 解不了 M4A/AAC**（只支持 MP3/WAV/FLAC/Vorbis），
> 而 M4A 是本次的核心需求。PyAV 一个库同时搞定 MP3 + M4A 解码，还省掉外部 ffmpeg 依赖。

## 目录

```
SlimTone/
  slimcore.py            # 逻辑层：探测 / 扫描 / 路径规划 / 转码 / 标签（不 import tkinter）
  SlimTone_Desktop.py    # 界面层：UI + 线程调度；--selftest / --convert 无头入口
  _tonegen.py            # 测试用音频样本生成器
  _hardexit.py           # 64 位 TerminateProcess 硬退出（绕开 Tcl DllMain 卡死）
  _test_core.py          # 逻辑层自测
  _test_ui.py            # 布局探测（控件尺寸 / 联动 / 设置读写）
  _test_flow.py          # 端到端真实线程流程测试
  dist/SlimTone.exe      # 成品
```

## 命令行

```bash
python SlimTone_Desktop.py --selftest                      # 无头自检（打包后也能跑，验依赖）
python SlimTone_Desktop.py --convert in.m4a out.mp3 64     # 单文件转码
SlimTone.exe --selftest                                    # 验证 EXE 依赖完整（退出码 0 = 通过）
```

## 免责声明

1. 纯本地离线工具，不联网、不上传、不采集任何数据。
2. 音频重编码有损，音质必然下降；请先小批量试听，重要文件自行备份。
3. 勾选「删除源文件」后原文件移入回收站，开发者不对任何数据丢失负责。
4. 请仅对你有合法权利的文件使用本工具，遵守所在地法律法规与平台服务条款。
5. 本软件按 **AS-IS** 提供，不提供任何明示或暗示担保。
6. 仅供个人学习与工作效率提升使用。

© 永远的兰兰 / Lanlan Eternal
