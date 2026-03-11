"""脚本说明：递归扫描目录下的媒体文件，并在目标目录批量创建软链接。"""

import ctypes
import os
import sys
from pathlib import Path

# Default link destination directory.
TARGET_DIR = r"F:\P\link"

MEDIA_EXTENSIONS = {
    # Video
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v",
    ".ts", ".mts", ".m2ts", ".webm", ".rmvb", ".rm", ".3gp",
    # Audio
    ".mp3", ".flac", ".aac", ".wav", ".m4a", ".ogg", ".wma",
    # Image
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff",
}


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def normalize_path(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def is_media_file(file_path: Path) -> bool:
    try:
        return (
            file_path.is_file()
            and not file_path.is_symlink()
            and file_path.suffix.lower() in MEDIA_EXTENSIONS
        )
    except Exception:
        return False


def iter_media_files(source_dir: Path, target_dir: Path):
    target_dir_norm = normalize_path(target_dir)

    for current_root, dirs, files in os.walk(str(source_dir)):
        current_root_path = Path(current_root)

        # If target folder is inside source folder, skip walking into it.
        dirs[:] = [
            d for d in dirs
            if normalize_path(current_root_path / d) != target_dir_norm
        ]

        # Defensive check in case current root resolves to target dir.
        if normalize_path(current_root_path) == target_dir_norm:
            continue

        for file_name in files:
            file_path = current_root_path / file_name
            if is_media_file(file_path):
                yield file_path


def is_same_symlink_target(link_path: Path, source_path: Path) -> bool:
    if not link_path.is_symlink():
        return False

    try:
        linked_target = os.readlink(str(link_path))
        if not os.path.isabs(linked_target):
            linked_target = os.path.join(str(link_path.parent), linked_target)

        return normalize_path(Path(linked_target)) == normalize_path(source_path)
    except Exception:
        return False


def get_unique_link_path(target_dir: Path, source_name: str) -> Path:
    base = Path(source_name).stem
    suffix = Path(source_name).suffix
    candidate = target_dir / source_name

    if not candidate.exists() and not candidate.is_symlink():
        return candidate

    index = 1
    while True:
        candidate = target_dir / f"{base}({index}){suffix}"
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        index += 1


def main():
    if len(sys.argv) < 2:
        print("Usage: python create_media_symlinks_recursive.py <source_dir> [target_dir]")
        print("Example: python create_media_symlinks_recursive.py \"W:\\Video\"")
        print("Example: python create_media_symlinks_recursive.py \"W:\\Video\" \"F:\\P\\link\"")
        sys.exit(1)

    source_dir = Path(os.path.abspath(sys.argv[1].strip().strip('"')))
    target_dir = Path(os.path.abspath(sys.argv[2].strip().strip('"'))) if len(sys.argv) > 2 else Path(TARGET_DIR)

    if not source_dir.exists() or not source_dir.is_dir():
        print(f"Error: source directory not found or invalid -> {source_dir}")
        sys.exit(1)

    if not is_admin():
        print("Warning: not running as Administrator. Symlink creation may fail.")

    if not target_dir.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created target directory: {target_dir}")
        except Exception as exc:
            print(f"Error: failed to create target directory {target_dir}: {exc}")
            sys.exit(1)

    media_files = sorted(iter_media_files(source_dir, target_dir), key=lambda p: str(p).lower())
    total_media = len(media_files)

    if total_media == 0:
        print(f"No media files found under: {source_dir}")
        return

    success_count = 0
    skip_count = 0
    fail_count = 0

    for source_path in media_files:
        preferred_link_path = target_dir / source_path.name
        link_path = preferred_link_path

        if preferred_link_path.exists() or preferred_link_path.is_symlink():
            if is_same_symlink_target(preferred_link_path, source_path):
                print(f"Skip (already linked): {preferred_link_path.name}")
                skip_count += 1
                continue
            link_path = get_unique_link_path(target_dir, source_path.name)

        try:
            os.symlink(str(source_path), str(link_path))
            print(f"OK: {source_path} -> {link_path.name}")
            success_count += 1
        except OSError as exc:
            print(f"Fail: {source_path} ({exc})")
            fail_count += 1

    print("\nDone.")
    print(f"Total media files found: {total_media}")
    print(f"Created links: {success_count}")
    print(f"Skipped existing links: {skip_count}")
    print(f"Failed: {fail_count}")


if __name__ == "__main__":
    main()
