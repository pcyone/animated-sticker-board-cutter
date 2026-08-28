#!/usr/bin/env python3
"""Split a white-background fixed-grid video board into transparent APNG/GIF stickers."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

try:
    from PIL import Image, ImageSequence
except ImportError as exc:  # pragma: no cover - dependency error path
    raise SystemExit("缺少 Pillow。请先安装 Python 的 PIL/Pillow 模块。") from exc


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def probe_video(path: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate:format=duration",
        "-of",
        "json",
        str(path),
    ]
    payload = json.loads(subprocess.check_output(command, text=True))
    stream = payload["streams"][0]
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "frame_rate": stream.get("r_frame_rate", "0/0"),
        "duration": float(payload["format"]["duration"]),
    }


def extract_sample(video: Path, at_seconds: float, destination: Path) -> None:
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{at_seconds:.6f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-y",
            str(destination),
        ]
    )


def group_runs(values: list[int]) -> list[tuple[int, int]]:
    groups: list[list[int]] = []
    for value in values:
        if not groups or value > groups[-1][-1] + 1:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [(group[0], group[-1]) for group in groups]


def select_regular_runs(
    runs: list[tuple[int, int]], expected: int, dimension: int
) -> list[tuple[int, int]] | None:
    if len(runs) < expected or len(runs) > 24:
        return None
    best: tuple[float, tuple[tuple[int, int], ...]] | None = None
    for choice in itertools.combinations(runs, expected):
        centers = [(start + end) / 2 for start, end in choice]
        gaps = [b - a for a, b in zip(centers, centers[1:])]
        mean_gap = sum(gaps) / len(gaps)
        if mean_gap <= 0:
            continue
        if min(gaps) < mean_gap * 0.65 or max(gaps) > mean_gap * 1.35:
            continue
        span = centers[-1] - centers[0]
        if span < dimension * 0.60:
            continue
        regularity = sum(abs(gap - mean_gap) for gap in gaps) / (mean_gap * len(gaps))
        margin_balance = abs(centers[0] - (dimension - 1 - centers[-1])) / dimension
        score = regularity + margin_balance * 0.25 - (span / dimension) * 0.02
        if best is None or score < best[0]:
            best = (score, choice)
    return list(best[1]) if best else None


def detect_grid_runs(
    image: Image.Image,
    axis: str,
    expected: int,
    darkness_threshold: int,
    coverage: float,
) -> list[tuple[int, int]] | None:
    rgb = image.convert("RGB")
    pixels = rgb.load()
    if axis == "vertical":
        candidates = []
        minimum = int(rgb.height * coverage)
        for x in range(rgb.width):
            dark = sum(1 for y in range(rgb.height) if max(pixels[x, y]) < darkness_threshold)
            if dark >= minimum:
                candidates.append(x)
        return select_regular_runs(group_runs(candidates), expected, rgb.width)
    candidates = []
    minimum = int(rgb.width * coverage)
    for y in range(rgb.height):
        dark = sum(1 for x in range(rgb.width) if max(pixels[x, y]) < darkness_threshold)
        if dark >= minimum:
            candidates.append(y)
    return select_regular_runs(group_runs(candidates), expected, rgb.height)


def parse_coordinates(value: str | None, expected: int, label: str) -> list[tuple[int, int]] | None:
    if not value:
        return None
    numbers = [int(item.strip()) for item in value.split(",") if item.strip()]
    if len(numbers) != expected:
        raise ValueError(f"{label}需要 {expected} 个坐标，实际收到 {len(numbers)} 个。")
    if numbers != sorted(numbers) or len(set(numbers)) != len(numbers):
        raise ValueError(f"{label}必须严格递增且不能重复。")
    return [(number, number) for number in numbers]


def cells_from_lines(
    vertical: list[tuple[int, int]],
    horizontal: list[tuple[int, int]],
    padding: int,
) -> list[dict]:
    cells = []
    for row in range(len(horizontal) - 1):
        for column in range(len(vertical) - 1):
            x0 = vertical[column][1] + 1 + padding
            x1 = vertical[column + 1][0] - padding
            y0 = horizontal[row][1] + 1 + padding
            y1 = horizontal[row + 1][0] - padding
            if x1 - x0 < 32 or y1 - y0 < 32:
                raise ValueError("格线间距过小，无法生成有效裁切区域。")
            cells.append({"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
    return cells


def equal_cells(width: int, height: int, columns: int, rows: int, inset: int) -> list[dict]:
    cells = []
    for row in range(rows):
        for column in range(columns):
            x0 = round(column * width / columns) + inset
            x1 = round((column + 1) * width / columns) - inset
            y0 = round(row * height / rows) + inset
            y1 = round((row + 1) * height / rows) - inset
            cells.append({"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
    return cells


def safe_label(label: str, fallback: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "-", label).strip(" .-")
    return cleaned or fallback


def background_filter(cell: dict, threshold: int) -> str:
    width = cell["width"]
    height = cell["height"]
    inset = max(4, min(width, height) // 28)
    seeds = [
        (inset, inset),
        (width - 1 - inset, inset),
        (inset, height - 1 - inset),
        (width - 1 - inset, height - 1 - inset),
        (width // 2, inset),
        (width // 2, height - 1 - inset),
        (inset, height // 2),
        (width - 1 - inset, height // 2),
    ]
    normalize = (
        f"lutrgb=r='if(gte(val,{threshold}),255,val)'"
        f":g='if(gte(val,{threshold}),255,val)'"
        f":b='if(gte(val,{threshold}),255,val)'"
    )
    floods = []
    for x, y in seeds:
        floods.append(
            "floodfill="
            f"x={x}:y={y}:"
            "s0=255:s1=255:s2=255:s3=255:"
            "d0=255:d1=255:d2=255:d3=0"
        )
    return ",".join([normalize, *floods])


def render_apng(
    ffmpeg: str,
    source: Path,
    output: Path,
    cell: dict,
    start: float,
    duration: float,
    fps: int,
    canvas: int,
    threshold: int,
    compression: int,
) -> None:
    inner = canvas - 16
    key_filter = background_filter(cell, threshold)
    graph = (
        f"[0:v]fps={fps},crop={cell['width']}:{cell['height']}:{cell['x']}:{cell['y']},split[o][k];"
        f"[k]format=rgba,{key_filter},format=rgba,alphaextract,format=gray[m];"
        "[o]format=rgb24[org];"
        f"[org][m]alphamerge,format=rgba,scale={inner}:{inner}:"
        "force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={canvas}:{canvas}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,format=rgba[out]"
    )
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-t",
            str(duration),
            "-an",
            "-filter_complex",
            graph,
            "-map",
            "[out]",
            "-plays",
            "0",
            "-compression_level",
            str(compression),
            "-f",
            "apng",
            "-y",
            str(output),
        ]
    )


def render_gif(
    ffmpeg: str,
    apng: Path,
    output: Path,
    duration: float,
    fps: int,
    canvas: int,
) -> None:
    graph = (
        f"[0:v]fps={fps},scale={canvas}:{canvas}:flags=lanczos,split[g0][g1];"
        "[g0]palettegen=reserve_transparent=1:transparency_color=ffffff[p];"
        "[g1][p]paletteuse=alpha_threshold=64:dither=bayer:bayer_scale=3"
    )
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ignore_loop",
            "1",
            "-i",
            str(apng),
            "-t",
            str(duration),
            "-filter_complex",
            graph,
            "-loop",
            "0",
            "-y",
            str(output),
        ]
    )


def render_preview(
    ffmpeg: str,
    apngs: list[Path],
    output: Path,
    columns: int,
    canvas: int,
    sample_time: float,
) -> None:
    command = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    for apng in apngs:
        command.extend(["-ignore_loop", "1", "-ss", str(sample_time), "-i", str(apng)])
    if len(apngs) == 1:
        command.extend(["-frames:v", "1", "-y", str(output)])
        run(command)
        return
    layout = []
    for index in range(len(apngs)):
        x = (index % columns) * canvas
        y = (index // columns) * canvas
        layout.append(f"{x}_{y}")
    inputs = "".join(f"[{index}:v]" for index in range(len(apngs)))
    graph = (
        f"{inputs}xstack=inputs={len(apngs)}:layout={'|'.join(layout)}:"
        "fill=0x00000000,format=rgba[out]"
    )
    command.extend(
        ["-filter_complex", graph, "-map", "[out]", "-frames:v", "1", "-y", str(output)]
    )
    run(command)


def inspect_animation(path: Path, expected_duration: float, expected_fps: int) -> dict:
    image = Image.open(path)
    hashes = []
    durations = []
    corners_transparent = True
    for frame in ImageSequence.Iterator(image):
        rgba = frame.convert("RGBA")
        hashes.append(hashlib.md5(rgba.tobytes()).hexdigest())
        durations.append(float(frame.info.get("duration", image.info.get("duration", 0))))
        width, height = rgba.size
        corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
        corners_transparent = corners_transparent and all(
            rgba.getpixel(point)[3] == 0 for point in corners
        )
    total_ms = sum(durations)
    expected_frames = max(2, round(expected_duration * expected_fps))
    duration_ok = abs(total_ms - expected_duration * 1000) <= max(120, 2000 / expected_fps)
    frames_ok = len(hashes) >= expected_frames - 1
    return {
        "file": str(path),
        "size": list(image.size),
        "frames": len(hashes),
        "duration_ms": total_ms,
        "unique_frames": len(set(hashes)),
        "corners_transparent": corners_transparent,
        "bytes": path.stat().st_size,
        "passed": duration_ok and frames_ok and len(set(hashes)) > 1 and corners_transparent,
    }


def create_zip(destination: Path, items: list[Path], root: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in items:
            if item.is_dir():
                for file in sorted(item.rglob("*")):
                    if file.is_file():
                        archive.write(file, file.relative_to(root))
            elif item.is_file():
                archive.write(item, item.relative_to(root))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把白色背景固定网格视频切割为透明 APNG 和 GIF 动态表情。"
    )
    parser.add_argument("input", type=Path, help="输入视频的绝对路径")
    parser.add_argument("--output", type=Path, required=True, help="新的或空的输出目录")
    parser.add_argument("--columns", type=int, default=4, help="列数，默认 4")
    parser.add_argument("--rows", type=int, default=2, help="行数，默认 2")
    parser.add_argument("--start", type=float, default=0.0, help="截取起点秒数，默认 0")
    parser.add_argument("--duration", type=float, default=2.0, help="截取时长，默认 2 秒")
    parser.add_argument("--labels", help="按阅读顺序排列的逗号分隔名称")
    parser.add_argument(
        "--grid-mode", choices=["auto", "lines", "equal"], default="auto", help="网格模式"
    )
    parser.add_argument("--vertical-lines", help="竖线中心 x 坐标，逗号分隔")
    parser.add_argument("--horizontal-lines", help="横线中心 y 坐标，逗号分隔")
    parser.add_argument("--line-threshold", type=int, default=120, help="格线深色阈值")
    parser.add_argument("--line-coverage", type=float, default=0.55, help="格线贯穿比例")
    parser.add_argument("--line-padding", type=int, default=2, help="格线内侧额外留白")
    parser.add_argument("--equal-inset", type=int, default=2, help="等分模式每格内缩像素")
    parser.add_argument("--white-threshold", type=int, default=235, help="近白背景阈值")
    parser.add_argument("--apng-size", type=int, default=320, help="APNG 正方形尺寸")
    parser.add_argument("--gif-size", type=int, default=240, help="GIF 正方形尺寸")
    parser.add_argument("--apng-fps", type=int, default=24, help="APNG 帧率")
    parser.add_argument("--gif-fps", type=int, default=12, help="GIF 帧率")
    parser.add_argument("--compression-level", type=int, default=7, choices=range(10))
    parser.add_argument("--limit", type=int, help="仅处理前 N 格，供快速测试")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SystemExit("需要 ffmpeg 和 ffprobe，但当前环境未找到。")
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"输入视频不存在：{source}")
    if args.columns < 1 or args.rows < 1:
        raise SystemExit("行列数必须大于 0。")
    if args.duration <= 0 or args.start < 0:
        raise SystemExit("start 必须不小于 0，duration 必须大于 0。")
    if not 0 <= args.white_threshold <= 255:
        raise SystemExit("white-threshold 必须位于 0–255。")
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"输出目录不是空目录，请换一个新目录：{output}")
    output.mkdir(parents=True, exist_ok=True)
    apng_dir = output / "APNG_透明高清"
    gif_dir = output / "GIF_聊天兼容"
    apng_dir.mkdir()
    gif_dir.mkdir()

    metadata = probe_video(source)
    if args.start + args.duration > metadata["duration"] + 0.05:
        raise SystemExit(
            f"截取范围超过视频时长：{args.start}+{args.duration}>{metadata['duration']:.3f}"
        )

    sample_at = args.start + min(0.5, args.duration / 2)
    with tempfile.TemporaryDirectory(prefix="animated-sticker-board-") as temp_dir:
        sample_path = Path(temp_dir) / "sample.png"
        extract_sample(source, sample_at, sample_path)
        sample = Image.open(sample_path)

        try:
            explicit_vertical = parse_coordinates(
                args.vertical_lines, args.columns + 1, "vertical-lines"
            )
            explicit_horizontal = parse_coordinates(
                args.horizontal_lines, args.rows + 1, "horizontal-lines"
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

        detected_vertical = None
        detected_horizontal = None
        grid_used = args.grid_mode
        if args.grid_mode in {"auto", "lines"}:
            detected_vertical = explicit_vertical or detect_grid_runs(
                sample,
                "vertical",
                args.columns + 1,
                args.line_threshold,
                args.line_coverage,
            )
            detected_horizontal = explicit_horizontal or detect_grid_runs(
                sample,
                "horizontal",
                args.rows + 1,
                args.line_threshold,
                args.line_coverage,
            )
        if detected_vertical and detected_horizontal:
            cells = cells_from_lines(
                detected_vertical, detected_horizontal, args.line_padding
            )
            grid_used = "lines"
        elif args.grid_mode == "lines":
            raise SystemExit(
                "未检测到所需数量的规则格线。请提供 vertical-lines/horizontal-lines，或改用 equal。"
            )
        else:
            cells = equal_cells(
                metadata["width"],
                metadata["height"],
                args.columns,
                args.rows,
                args.equal_inset,
            )
            grid_used = "equal"

    total_cells = args.columns * args.rows
    if len(cells) != total_cells:
        raise SystemExit(f"内部错误：预期 {total_cells} 格，实际得到 {len(cells)} 格。")
    count = min(args.limit or total_cells, total_cells)
    cells = cells[:count]
    if args.labels:
        raw_labels = [item.strip() for item in args.labels.split(",")]
        if len(raw_labels) != total_cells:
            raise SystemExit(f"labels 需要 {total_cells} 个名称，实际收到 {len(raw_labels)} 个。")
        labels = raw_labels[:count]
    else:
        labels = [f"表情-{index:02d}" for index in range(1, count + 1)]

    apngs: list[Path] = []
    gifs: list[Path] = []
    for index, (cell, label) in enumerate(zip(cells, labels), start=1):
        file_label = safe_label(label, f"表情-{index:02d}")
        stem = f"{index:02d}-{file_label}"
        apng = apng_dir / f"{stem}.png"
        gif = gif_dir / f"{stem}.gif"
        print(f"[{index}/{count}] 导出 {stem}", flush=True)
        render_apng(
            ffmpeg,
            source,
            apng,
            cell,
            args.start,
            args.duration,
            args.apng_fps,
            args.apng_size,
            args.white_threshold,
            args.compression_level,
        )
        render_gif(ffmpeg, apng, gif, args.duration, args.gif_fps, args.gif_size)
        apngs.append(apng)
        gifs.append(gif)

    preview = output / f"预览_{args.columns}x{args.rows}_透明表情.png"
    render_preview(
        ffmpeg,
        apngs,
        preview,
        args.columns,
        args.apng_size,
        min(args.duration / 2, max(0, args.duration - 0.05)),
    )

    apng_qa = [inspect_animation(path, args.duration, args.apng_fps) for path in apngs]
    gif_qa = [inspect_animation(path, args.duration, args.gif_fps) for path in gifs]
    passed = all(item["passed"] for item in [*apng_qa, *gif_qa])
    report = {
        "input": str(source),
        "output": str(output),
        "video": metadata,
        "segment": {"start": args.start, "duration": args.duration},
        "grid": {
            "requested_mode": args.grid_mode,
            "used_mode": grid_used,
            "columns": args.columns,
            "rows": args.rows,
            "vertical_runs": detected_vertical,
            "horizontal_runs": detected_horizontal,
            "cells": cells,
        },
        "settings": {
            "white_threshold": args.white_threshold,
            "apng_size": args.apng_size,
            "gif_size": args.gif_size,
            "apng_fps": args.apng_fps,
            "gif_fps": args.gif_fps,
        },
        "qa": {"passed": passed, "apng": apng_qa, "gif": gif_qa},
    }
    report_path = output / "导出报告.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not passed:
        raise SystemExit(f"质量检查未通过，请查看：{report_path}")

    apng_zip = output / "动态表情_APNG透明高清.zip"
    gif_zip = output / "动态表情_GIF聊天兼容.zip"
    all_zip = output / "动态表情_全部格式.zip"
    create_zip(apng_zip, [apng_dir], output)
    create_zip(gif_zip, [gif_dir], output)
    create_zip(all_zip, [apng_dir, gif_dir, preview, report_path], output)

    print(
        json.dumps(
            {
                "passed": True,
                "output": str(output),
                "all_zip": str(all_zip),
                "apng_zip": str(apng_zip),
                "gif_zip": str(gif_zip),
                "preview": str(preview),
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"媒体处理命令失败，退出码：{exc.returncode}") from exc
