"""脚本说明：递归清洗媒体文件名，按规则文件删除文件名前后缀字符串。"""

from __future__ import annotations

import argparse
from pathlib import Path

from media_name_cleanup_common import (
    DEFAULT_RULES_FILE,
    load_cleanup_tokens,
    normalize_path_str,
    strip_tokens_from_edges,
)

MEDIA_EXTENSIONS = {
    # Video
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".m4v",
    ".ts",
    ".mts",
    ".m2ts",
    ".webm",
    ".rmvb",
    ".rm",
    ".3gp",
    # Audio
    ".mp3",
    ".flac",
    ".aac",
    ".wav",
    ".m4a",
    ".ogg",
    ".wma",
    ".opus",
    # Image
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".heic",
    ".heif",
    ".tif",
    ".tiff",
}

DEFAULT_TARGET_PATH = r"W:\P\new"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean media file names by removing configured strings from the start or end "
            "of the filename stem."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=DEFAULT_TARGET_PATH,
        help=f"Target directory path (default: {DEFAULT_TARGET_PATH})",
    )
    parser.add_argument(
        "--rules",
        default=str(DEFAULT_RULES_FILE),
        help=f"Rules file path (default: {DEFAULT_RULES_FILE})",
    )
    parser.add_argument(
        "--top-only",
        action="store_true",
        help="Only process files in top directory (default: recursive)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes only; do not rename files",
    )
    return parser.parse_args()


def is_media_file(path: Path) -> bool:
    try:
        return path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    except Exception:
        return False


def iter_media_files(root: Path, recursive: bool):
    entries = root.rglob("*") if recursive else root.iterdir()
    media_files = [p for p in entries if is_media_file(p)]
    media_files.sort(key=lambda p: str(p).lower())
    return media_files


def get_unique_target_path(source: Path, new_stem: str) -> Path:
    candidate = source.with_name(f"{new_stem}{source.suffix}")
    if normalize_path_str(candidate) == normalize_path_str(source):
        return source

    if not candidate.exists():
        return candidate

    index = 1
    while True:
        candidate = source.with_name(f"{new_stem}({index}){source.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def main() -> int:
    args = parse_args()
    root = Path(args.path).expanduser()

    if not root.exists() or not root.is_dir():
        print(f"[Error] Invalid directory: {root}")
        return 2

    rules_file, tokens = load_cleanup_tokens(args.rules)
    if not tokens:
        print(f"[Error] No cleanup tokens loaded from: {rules_file}")
        return 2

    recursive = not args.top_only
    media_files = iter_media_files(root, recursive=recursive)

    if not media_files:
        print("[Info] No media files found.")
        return 0

    renamed_count = 0
    skipped_count = 0
    failed_count = 0

    print(f"[Info] Root: {root}")
    print(f"[Info] Recursive: {recursive}")
    print(f"[Info] Rules file: {rules_file}")
    print(f"[Info] Loaded rules: {len(tokens)}")
    print(f"[Info] Media files found: {len(media_files)}\n")

    for src in media_files:
        new_stem, matches = strip_tokens_from_edges(src.stem, tokens)

        if not matches:
            skipped_count += 1
            continue

        if not new_stem:
            failed_count += 1
            print(f"[Fail] Empty name after cleanup: {src}")
            continue

        dst = get_unique_target_path(src, new_stem)
        if normalize_path_str(dst) == normalize_path_str(src):
            skipped_count += 1
            continue

        print(f"[Plan] {src.name} -> {dst.name} (rules: {', '.join(matches)})")

        if args.dry_run:
            renamed_count += 1
            continue

        try:
            src.rename(dst)
            renamed_count += 1
        except Exception as exc:
            failed_count += 1
            print(f"[Fail] Rename failed: {src} ({exc})")

    print("\n=== Done ===")
    if args.dry_run:
        print("Mode: dry-run")
    print(f"Renamed (or planned in dry-run): {renamed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
