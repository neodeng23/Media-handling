#!/usr/bin/env python3
"""
脚本说明：将视频文件重命名为 VidHub 刮削友好的命名格式。

电影:  {片名}.{年份}.其他信息.扩展名
电视剧: {剧名}.{年份}.S##E##.其他信息.扩展名
花絮:  {剧名}.S00E##.其他信息.扩展名

示例：
  python rename_to_vidhub_format.py "W:\\影视\\国剧\\倚天屠龙记" --title 倚天屠龙记 --year 2003
  python rename_to_vidhub_format.py "D:\\movies" --type movie
  python rename_to_vidhub_format.py "D:\\drama" --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from media_common import VIDEO_EXTENSIONS, is_video_file

SEASON_EPISODE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[.\s_-]S(\d{1,2})E(\d{1,2})", re.IGNORECASE), "se"),
    (re.compile(r"第(\d{1,2})季第?(\d{1,2})集"), "se"),
    (re.compile(r"[.\s_-]SE?(\d{1,2})(?![Ee\d])", re.IGNORECASE), "s_only"),
    (re.compile(r"[.\s_-]E(\d{1,2})", re.IGNORECASE), "e"),
    (re.compile(r"第(\d{1,2})集"), "e"),
    (re.compile(r"[.\s_\-()（）](\d{2,3})$"), "tail"),
]

SEASON_DIR_RE = re.compile(r"^SE?(\d{1,2})$", re.IGNORECASE)

TV_PATH_KEYWORDS = frozenset({
    "国剧", "美剧", "日剧", "韩剧", "港剧", "台剧", "英剧",
    "综艺", "动画", "剧集", "电视剧", "tv", "drama", "anime", "show",
})
MOVIE_PATH_KEYWORDS = frozenset({"电影", "movie", "movies", "film", "films"})

VIDHUB_TV_RE = re.compile(r"\.S\d{2}E\d{2}", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将视频文件重命名为 VidHub 刮削友好的命名格式。"
    )
    parser.add_argument("path", help="目标目录路径")
    parser.add_argument("--title", default="", help="指定片名/剧名（默认从文件名提取）")
    parser.add_argument("--year", default="", help="指定年份（同名影视必须）")
    parser.add_argument(
        "--type",
        choices=["auto", "movie", "tv"],
        default="auto",
        help="类型（默认 auto 自动检测）",
    )
    parser.add_argument("--season", type=int, default=0, help="指定季数（电视剧默认1）")
    parser.add_argument(
        "--delay", type=float, default=0.35, help="每次重命名后等待秒数，默认 0.35"
    )
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划，不实际重命名")
    return parser.parse_args()


def detect_media_type(video_files: list[Path], dir_path: Path) -> str:
    if len(video_files) > 1:
        return "tv"
    path_str = str(dir_path).lower()
    for kw in TV_PATH_KEYWORDS:
        if kw.lower() in path_str:
            return "tv"
    for kw in MOVIE_PATH_KEYWORDS:
        if kw.lower() in path_str:
            return "movie"
    if len(video_files) == 1:
        return "movie"
    return "tv"


def extract_season_episode(stem: str) -> tuple[int | None, int | None, str]:
    season: int | None = None
    episode: int | None = None
    remaining = stem

    for pattern, ptype in SEASON_EPISODE_PATTERNS:
        m = pattern.search(remaining)
        if not m:
            continue
        groups = m.groups()
        if ptype == "se":
            return int(groups[0]), int(groups[1]), remaining[: m.start()]
        if ptype == "s_only":
            season = int(groups[0])
            remaining = remaining[: m.start()] + remaining[m.end():]
            break

    episode_patterns = [
        (re.compile(r"[.\s_-]E(\d{1,2})", re.IGNORECASE), "e"),
        (re.compile(r"第(\d{1,2})集"), "e"),
        (re.compile(r"[.\s_\-()（）](\d{2,3})$"), "tail"),
    ]
    for pattern, ptype in episode_patterns:
        m = pattern.search(remaining)
        if not m:
            continue
        episode = int(m.group(1))
        remaining = remaining[: m.start()] + remaining[m.end():]
        break

    return season, episode, remaining


def detect_season_from_dir(dir_path: Path) -> int | None:
    m = SEASON_DIR_RE.match(dir_path.name)
    if m:
        return int(m.group(1))
    return None


def clean_title(raw: str) -> str:
    t = re.sub(r"[（(][^）)]*[）)]", "", raw)
    t = re.sub(r"[（(]$", "", t)
    t = re.sub(r"[.\s_-]?SE?\d{1,2}(?![Ee\d])", "", t, flags=re.IGNORECASE)
    t = re.sub(r"[.\s_-]?(1080[pP]|720[pP]|480[pP]|2160[pP]|4[Kk]).*$", "", t)
    t = t.rstrip(". -_")
    return t.strip()


def build_vidhub_name(
    title: str,
    year: str,
    media_type: str,
    season: int | None,
    episode: int | None,
    suffix: str,
) -> str:
    parts = [title]
    if year:
        parts.append(year)
    if media_type == "tv":
        s = season if season is not None else 1
        e = episode if episode is not None else 1
        parts.append(f"S{s:02d}E{e:02d}")
    return ".".join(parts) + suffix


def is_already_vidhub_tv(stem: str) -> bool:
    return bool(VIDHUB_TV_RE.search(stem))


def main() -> int:
    args = parse_args()

    if args.delay < 0:
        print("错误: --delay 不能为负数")
        return 2

    root = Path(args.path)
    if not root.exists() or not root.is_dir():
        print(f"错误: 目录不存在或不是目录: {root}")
        return 2

    video_files = sorted(
        [p for p in root.iterdir() if is_video_file(p)],
        key=lambda p: p.name.lower(),
    )
    if not video_files:
        print("未找到视频文件，无需处理。")
        return 0

    media_type = args.type
    if media_type == "auto":
        media_type = detect_media_type(video_files, root)

    dir_season = detect_season_from_dir(root)

    print(f"类型: {media_type.upper()}")
    print(f"文件数量: {len(video_files)}")
    if args.title:
        print(f"指定片名: {args.title}")
    if args.year:
        print(f"指定年份: {args.year}")
    if args.season > 0:
        print(f"指定季数: {args.season}")
    elif dir_season is not None:
        print(f"目录季数: {dir_season}")
    print()

    renamed_count = 0
    skipped_count = 0
    failed_count = 0

    for src in video_files:
        stem = src.stem
        suffix = src.suffix

        if media_type == "tv" and is_already_vidhub_tv(stem):
            skipped_count += 1
            print(f"[跳过] 已符合 VidHub 格式: {src.name}")
            continue

        season, episode, remaining = extract_season_episode(stem)

        title = args.title or clean_title(remaining if (season or episode) else stem)
        year = args.year

        if media_type == "tv":
            if args.season > 0:
                season = args.season
            elif season is not None and episode is None:
                pass
            elif season is None and dir_season is not None:
                season = dir_season
            elif season is None:
                season = 1
            if episode is None:
                skipped_count += 1
                print(f"[跳过] 无法提取集数: {src.name}")
                continue

        new_name = build_vidhub_name(title, year, media_type, season, episode, suffix)
        dst = src.with_name(new_name)

        if dst == src:
            skipped_count += 1
            print(f"[跳过] 无需重命名: {src.name}")
            continue

        if dst.exists():
            idx = 1
            while dst.exists():
                dst = src.with_name(f"{Path(new_name).stem}({idx}){suffix}")
                idx += 1

        print(f"[PLAN] {src.name} -> {dst.name}")

        if not args.dry_run:
            try:
                src.rename(dst)
                renamed_count += 1
                time.sleep(args.delay)
            except OSError as exc:
                print(f"[SKIP] 重命名失败: {src} -> {dst} ({exc})")
                failed_count += 1
                continue

    if args.dry_run:
        print("\ndry-run 完成，未实际修改文件。")
    else:
        print(
            f"\n完成: 成功重命名 {renamed_count} 个，"
            f"跳过 {skipped_count} 个，失败 {failed_count} 个。"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
