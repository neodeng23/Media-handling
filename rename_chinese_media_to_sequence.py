#!/usr/bin/env python3
"""
脚本说明：将文件名中包含中文的媒体文件重命名为连续编号。

示例：
  python rename_chinese_media_to_sequence.py "D:\\media"
  python rename_chinese_media_to_sequence.py "D:\\media" --prefix travel
  python rename_chinese_media_to_sequence.py "D:\\media" --prefix travel --delay 0.6
  python rename_chinese_media_to_sequence.py "\\\\nas\\share\\album" --recursive
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path


MEDIA_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".heic",
    ".heif",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wmv",
    ".flv",
    ".m4v",
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".m4a",
    ".ogg",
    ".wma",
    ".opus",
}

CHINESE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将包含汉字的媒体文件重命名为数字序号（可选前缀）。"
    )
    parser.add_argument("path", help="目标目录路径（Windows/网盘路径都可）")
    parser.add_argument(
        "--prefix",
        default="",
        help='前缀，例如 "trip" 后会命名为 trip-1、trip-2 ...',
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="每次重命名后等待秒数，默认 0.35（网盘建议保留）",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="递归处理子目录（默认仅处理当前目录）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印计划，不实际重命名",
    )
    return parser.parse_args()


def is_media_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS


def contains_chinese(text: str) -> bool:
    return CHINESE_RE.search(text) is not None


def compile_number_pattern(prefix: str) -> re.Pattern[str]:
    if prefix:
        return re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    return re.compile(r"^(\d+)$")


def next_available_number(used_numbers: set[int], start: int) -> int:
    n = start
    while n in used_numbers:
        n += 1
    return n


def build_target_stem(prefix: str, number: int) -> str:
    if prefix:
        return f"{prefix}-{number}"
    return str(number)


def main() -> int:
    args = parse_args()

    if args.delay < 0:
        print("错误: --delay 不能为负数")
        return 2

    root = Path(args.path)
    if not root.exists() or not root.is_dir():
        print(f"错误: 目录不存在或不是目录: {root}")
        return 2

    entries = root.rglob("*") if args.recursive else root.iterdir()
    media_files = [p for p in entries if is_media_file(p)]

    if not media_files:
        print("未找到媒体文件，无需处理。")
        return 0

    number_pattern = compile_number_pattern(args.prefix)
    used_numbers: set[int] = set()
    for p in media_files:
        match = number_pattern.match(p.stem)
        if match:
            used_numbers.add(int(match.group(1)))

    to_rename = [
        p
        for p in media_files
        if contains_chinese(p.stem) and not number_pattern.match(p.stem)
    ]
    to_rename.sort(key=lambda p: p.name.lower())

    if not to_rename:
        print("未找到文件名包含汉字的媒体文件，无需重命名。")
        return 0

    print(
        f"找到 {len(to_rename)} 个待重命名文件，路径: {root}，"
        f"模式: {'prefix-' if args.prefix else ''}数字，"
        f"每次操作延时: {args.delay:.2f}s"
    )

    renamed_count = 0
    current = 1
    for src in to_rename:
        current = next_available_number(used_numbers, current)

        while True:
            target_stem = build_target_stem(args.prefix, current)
            dst = src.with_name(f"{target_stem}{src.suffix}")
            if not dst.exists():
                break
            used_numbers.add(current)
            current += 1
            current = next_available_number(used_numbers, current)

        print(f"[PLAN] {src.name} -> {dst.name}")
        if not args.dry_run:
            try:
                src.rename(dst)
            except OSError as exc:
                print(f"[SKIP] 重命名失败: {src} -> {dst} ({exc})")
                current += 1
                continue
            renamed_count += 1
            time.sleep(args.delay)

        used_numbers.add(current)
        current += 1

    if args.dry_run:
        print("dry-run 完成，未实际修改文件。")
    else:
        print(f"完成: 成功重命名 {renamed_count} 个文件。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
