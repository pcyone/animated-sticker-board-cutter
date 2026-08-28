# Animated Sticker Board Cutter

一套可复用的 Codex Skill：从角色参考图或现成 4×2 图板出发，整理 Gemini 约 10 秒动画提示词，并把返回的视频在本地切割成透明 APNG、GIF、预览图与 ZIP 表情包。

整个切割阶段在本地运行，不依赖 StickerFaster，不购买点数，也不会上传源视频。

## 能做什么

- 规划身份一致的 4×2、8 格静态角色图板。
- 生成严格限制位置、镜头和两段动作的 Gemini 视频提示词。
- 自动识别 4×2 视频中的深色格线；无格线时自动等分。
- 只移除与格子边缘连通的白色背景，保护眼睛、衬衫和浅色外壳。
- 输出透明 APNG、聊天兼容 GIF、静态预览、质量报告和 ZIP。
- 支持分别截取 `0–2 秒` 与 `5–7 秒`，把两组动作扩展为 16 个表情。

## 仓库结构

```text
.
├── README.md
├── docs/
│   └── INSTALLATION.md
└── skills/
    └── animated-sticker-board-cutter/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/usage.md
        └── scripts/export_sticker_board.py
```

## 快速安装

推荐在 Codex 中直接说：

```text
使用 $skill-installer，从 GitHub 仓库
https://github.com/pcyone/animated-sticker-board-cutter/tree/main/skills/animated-sticker-board-cutter
安装 animated-sticker-board-cutter。
```

也可以运行安装器：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo pcyone/animated-sticker-board-cutter \
  --path skills/animated-sticker-board-cutter
```

安装后，在下一次 Codex 对话中使用 `$animated-sticker-board-cutter`。

完整的 macOS、Linux、Windows、私有仓库和依赖安装步骤见 [安装说明](docs/INSTALLATION.md)。

## 最简单的使用方式

上传角色参考图后发送：

```text
使用 $animated-sticker-board-cutter，基于我上传的角色图制作一套 4×2、8 格动态表情包。

保持角色身份、关键特征和服装一致。先制作静态图板，并提供 Gemini 约 10 秒的视频提示词；
我把生成的视频上传回来后，再本地切割成透明 APNG 和 GIF 表情包。
```

如果已经有视频，可直接发送：

```text
使用 $animated-sticker-board-cutter，把这个 4×2 视频图板切成 8 个透明动态表情。
使用前 2 秒，名称依次为：爆笑、震惊、疑惑、委屈、得意、翻白眼、无语、愤怒。
```

完整工作流、Gemini 提示词模板、命令参数和故障排查见 [详细使用说明](skills/animated-sticker-board-cutter/references/usage.md)。

## 直接运行切割脚本

依赖：FFmpeg、FFprobe、Python 3、Pillow。

```bash
python3 skills/animated-sticker-board-cutter/scripts/export_sticker_board.py \
  "/absolute/path/input.mp4" \
  --output "/absolute/path/new-output-folder" \
  --columns 4 \
  --rows 2 \
  --start 0 \
  --duration 2 \
  --labels "爆笑,震惊,疑惑,委屈,得意,翻白眼,无语,愤怒"
```

输出目录必须是新目录或空目录，脚本不会清空已有文件。

## 默认输出

```text
输出目录/
├── APNG_透明高清/
├── GIF_聊天兼容/
├── 预览_4x2_透明表情.png
├── 导出报告.json
├── 动态表情_APNG透明高清.zip
├── 动态表情_GIF聊天兼容.zip
└── 动态表情_全部格式.zip
```

- APNG：默认 `320×320`、24 fps、透明背景、无限循环。
- GIF：默认 `240×240`、12 fps、透明背景、无限循环。
- 默认截取：`0–2 秒`。
- 默认白底阈值：`235`。

## 已验证场景

- 1280×720、24 fps、10 秒的真实 4×2 掌机角色视频。
- 自动识别 5 条竖线与 3 条横线。
- 8 个 APNG、8 个 GIF、预览图、报告和 3 个 ZIP 全部通过。
- 无格线视频自动回退到等分模式并通过导出检查。
- 检查项包括尺寸、帧数、时长、唯一帧、四角透明和 ZIP 完整性。

## 适用边界

适合固定镜头、固定格位、白色或近白色背景的视频。不适合复杂场景、角色跨格、镜头移动、频繁切镜或背景持续变色的视频。
