"""脚本说明：仅处理指定目录顶层的视频文件，按配置文件清洗文件名。"""

from __future__ import annotations

import os
from pathlib import Path

from media_common import (
    DEFAULT_RULES_FILE,
    VIDEO_EXTENSIONS,
    get_unique_target_path,
    is_video_file,
    load_cleanup_tokens,
    normalize_path_str,
    strip_tokens_from_edges,
)


def rename_files_in_root(root_dir: str, rules_file: str | None = None):
    root = Path(os.path.abspath(root_dir))

    if not root.exists():
        print(f"[Error] Path not found: {root}")
        return

    if not root.is_dir():
        print(f"[Error] Not a directory: {root}")
        return

    try:
        resolved_rules_file, tokens = load_cleanup_tokens(rules_file)
    except ValueError as exc:
        print(f"[Error] {exc}")
        return

    if not tokens:
        print(f"[Error] No cleanup tokens found in: {resolved_rules_file}")
        return

    renamed_count = 0
    skipped_count = 0
    failed_count = 0

    print(f"[Info] Start directory: {root}")
    print(f"[Info] Cleanup config: {resolved_rules_file}")
    print(f"[Info] Loaded rules: {len(tokens)}\n")

    for item in root.iterdir():
        try:
            if not is_video_file(item):
                continue

            new_stem, matches = strip_tokens_from_edges(item.stem, tokens)
            if not matches:
                skipped_count += 1
                print(f"[Skip] No match: {item.name}")
                continue

            if not new_stem.strip():
                failed_count += 1
                print(f"[Fail] Empty name after cleanup: {item.name}")
                continue

            new_name = f"{new_stem}{item.suffix}"
            target_path = get_unique_target_path(root / new_name)

            if normalize_path_str(target_path) == normalize_path_str(item):
                skipped_count += 1
                print(f"[Skip] No effective rename: {item.name}")
                continue

            item.rename(target_path)
            renamed_count += 1
            print(
                f"[Renamed] {item.name} -> {target_path.name} "
                f"(rules: {', '.join(matches)})"
            )

        except Exception as exc:
            failed_count += 1
            print(f"[Fail] {item}: {exc}")

    print("\n=== Done ===")
    print(f"Renamed: {renamed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")


if __name__ == "__main__":
    folder_path = input("Input directory path: ").strip().strip('"')
    rules_path = input(
        f"Cleanup config path (enter for default: {DEFAULT_RULES_FILE}): "
    ).strip().strip('"')
    rename_files_in_root(folder_path, rules_path or None)
