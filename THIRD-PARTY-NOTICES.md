# 第三方组件说明 / Third-Party Notices

本项目的自有代码以 MIT 许可发布（见 LICENSE）。以下第三方组件按其自身许可使用，
**不在 MIT 覆盖范围内**。

## PyAV

- 位置：打包进 `SlimTone.exe` / 桌面版依赖
- 许可：BSD 3-Clause
- 项目：https://github.com/PyAV-Org/PyAV
- 说明：音频解码封装。

## FFmpeg

- 位置：由 PyAV 自带（wheel 内动态库）
- 许可：LGPL 2.1 or later（本项目未启用 GPL 组件）
- 项目：https://ffmpeg.org/
- 说明：音视频编解码引擎。LGPL 要求：分发时保留其许可声明；若替换该动态库，
  用户应具备替换能力。
- 注意：本项目**不包含**任何 GPL-only 组件（如 x264、x265），仅使用 LGPL 部分。

## 用户音频文件

本工具处理的是用户自行提供的音频文件，其版权归原权利人所有。本工具仅做格式
转换，不改变、不传播内容。
