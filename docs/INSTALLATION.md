# 详细安装说明

## 1. 环境要求

Skill 本体可被 Codex 读取；实际切割脚本还需要：

- Git
- Python 3
- Pillow（`PIL`）
- FFmpeg 与 FFprobe

检查命令：

```bash
git --version
python3 --version
ffmpeg -version
ffprobe -version
python3 -c "from PIL import Image; print(Image.__version__)"
```

### macOS

```bash
brew install git ffmpeg python
python3 -m pip install --user Pillow
```

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y git ffmpeg python3 python3-pip
python3 -m pip install --user Pillow
```

### Windows PowerShell

```powershell
winget install --id Git.Git
winget install --id Gyan.FFmpeg
winget install --id Python.Python.3.12
py -m pip install Pillow
```

安装后重新打开终端，确认 `ffmpeg`、`ffprobe` 和 Python 已进入 PATH。

## 2. 推荐：让 Codex 自动安装

在 Codex 中发送：

```text
使用 $skill-installer，从 GitHub 仓库
https://github.com/pcyone/animated-sticker-board-cutter/tree/main/skills/animated-sticker-board-cutter
安装 animated-sticker-board-cutter。
```

安装完成后，Skill 会出现在：

```text
~/.codex/skills/animated-sticker-board-cutter/
```

Skill 通常从下一次 Codex 对话开始可用。

## 3. 使用 Codex 自带安装脚本

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo pcyone/animated-sticker-board-cutter \
  --path skills/animated-sticker-board-cutter
```

安装器会下载公开仓库；如果遇到权限问题，会尝试 Git 稀疏检出。目标目录已存在时，安装器会停止，不会覆盖原 Skill。

## 4. macOS/Linux 手动安装

先确保目标目录不存在，以防意外合并旧文件：

```bash
test ! -e ~/.codex/skills/animated-sticker-board-cutter
```

然后执行：

```bash
git clone https://github.com/pcyone/animated-sticker-board-cutter.git \
  /tmp/animated-sticker-board-cutter-repo

mkdir -p ~/.codex/skills

cp -R \
  /tmp/animated-sticker-board-cutter-repo/skills/animated-sticker-board-cutter \
  ~/.codex/skills/animated-sticker-board-cutter
```

## 5. Windows PowerShell 手动安装

```powershell
$repoPath = Join-Path $env:TEMP "animated-sticker-board-cutter-repo"
$skillPath = Join-Path $env:USERPROFILE ".codex\skills\animated-sticker-board-cutter"

if (Test-Path $skillPath) {
  throw "Skill 已存在，请先备份旧版本：$skillPath"
}

git clone https://github.com/pcyone/animated-sticker-board-cutter.git $repoPath
New-Item -ItemType Directory -Force (Split-Path $skillPath) | Out-Null
Copy-Item -Recurse "$repoPath\skills\animated-sticker-board-cutter" $skillPath
```

## 6. 私有仓库安装

如果仓库被设为私有，先完成 GitHub 登录：

```bash
gh auth login
gh auth status
```

然后使用第 2 或第 3 种安装方式。安装器下载失败时会回退到已登录的 Git 凭证。

## 7. 验证安装

检查 Skill 文件：

```bash
test -f ~/.codex/skills/animated-sticker-board-cutter/SKILL.md
test -f ~/.codex/skills/animated-sticker-board-cutter/scripts/export_sticker_board.py
```

检查脚本是否可运行：

```bash
python3 -B \
  ~/.codex/skills/animated-sticker-board-cutter/scripts/export_sticker_board.py \
  --help
```

如果本机包含 Codex 的 `skill-creator`，还可以运行结构验证：

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  ~/.codex/skills/animated-sticker-board-cutter
```

看到 `Skill is valid!` 即表示结构有效。

## 8. 调用 Skill

新建或重新打开一个 Codex 对话，然后输入：

```text
使用 $animated-sticker-board-cutter，把我上传的 4×2 动画视频切成透明动态表情包。
```

可以从三种阶段开始：

1. 上传角色参考图：生成 4×2 静态图板、Gemini 提示词和最终表情包。
2. 上传已经完成的 4×2 图板：跳过图板生成，从 Gemini 提示词开始。
3. 上传已经完成的 MP4：直接本地切割并导出。

完整参数与使用案例见：

```text
skills/animated-sticker-board-cutter/references/usage.md
```

## 9. 更新与回退

更新前不要直接覆盖正在使用的 Skill。先把当前目录移动为备份，再重新安装新版本：

```bash
mv ~/.codex/skills/animated-sticker-board-cutter \
  ~/.codex/skills/animated-sticker-board-cutter-backup
```

随后重新执行自动安装或手动复制。新版本确认正常后，再决定是否保留备份。

## 10. 常见安装问题

### 找不到 `$animated-sticker-board-cutter`

- 确认文件位于 `~/.codex/skills/animated-sticker-board-cutter/SKILL.md`。
- 新建一个 Codex 对话，让 Skill 列表重新加载。
- 检查目录名与 `SKILL.md` 中的 `name` 是否一致。

### 找不到 FFmpeg

重新安装 FFmpeg并打开新终端，然后检查：

```bash
command -v ffmpeg
command -v ffprobe
```

### 缺少 Pillow

```bash
python3 -m pip install --user Pillow
```

### 目标 Skill 已存在

安装器会安全停止。先将旧目录移动为备份，不要直接清空不确定来源的目录。
