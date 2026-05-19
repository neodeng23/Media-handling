"""媒体文件统一处理脚本：先筛选视频移除垃圾，再递归清洗媒体文件名。"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from media_common import (
    DEFAULT_RULES_FILE,
    MEDIA_EXTENSIONS,
    VIDEO_EXTENSIONS,
    collect_all_dirs,
    get_unique_target_path,
    is_media_file,
    is_video_file,
    load_cleanup_config,
    load_cleanup_tokens,
    normalize_path_str,
    remove_empty_dirs_once,
    remove_empty_dirs_with_retry,
    strip_tokens_from_edges,
    try_list_dir_items,
    walk_error_handler,
)
from media_common import is_garbage_file, is_garbage_file_by_name

# ==================== 配置常量 ====================
DEFAULT_ROOT_DIR = r"W:\new"


# ==================== 阶段1：筛选视频、移除垃圾 ====================

def collect_video_files(root: Path):
    video_files = []
    root_norm = normalize_path_str(root)

    for current_root, dirs, files in os.walk(str(root)):
        current_path = Path(current_root)

        if normalize_path_str(current_path) == root_norm:
            continue

        for file_name in files:
            file_path = current_path / file_name
            try:
                if is_video_file(file_path):
                    video_files.append(file_path)
            except Exception as e:
                print(f"[跳过异常文件] {file_path}，原因: {e}")

    return video_files


def collect_all_files_in_subdirs(root: Path):
    file_list = []
    root_norm = normalize_path_str(root)

    for current_root, dirs, files in os.walk(str(root)):
        current_path = Path(current_root)

        if normalize_path_str(current_path) == root_norm:
            continue

        for file_name in files:
            file_list.append(current_path / file_name)

    return file_list


def delete_garbage_files(root: Path, rules_file: Path, cleanup_config):
    deleted_name_matched_count = 0
    deleted_garbage_file_count = 0
    failed_count = 0

    all_files = collect_all_files_in_subdirs(root)
    if not all_files:
        print("[提示] 没有扫描到子目录文件，无需删除垃圾文件。")
        return 0, 0, 0

    print(f"[信息] 共扫描到 {len(all_files)} 个子目录文件。")
    print(f"[信息] 垃圾规则配置: {rules_file}")
    print(f"[信息] 垃圾文件名关键字: {len(cleanup_config.junk_name_keywords)}")
    print(f"[信息] 垃圾文件规则: 名称 {len(cleanup_config.junk_files.exact_names)} / 关键字 {len(cleanup_config.junk_files.name_keywords)} / 扩展名 {len(cleanup_config.junk_files.extensions)}\n")

    for src_file in all_files:
        try:
            if not src_file.exists():
                print(f"[跳过] 文件已不存在: {src_file}")
                continue

            if is_garbage_file_by_name(src_file, cleanup_config.junk_name_keywords):
                src_file.unlink()
                deleted_name_matched_count += 1
                print(f"[已删除关键字垃圾文件] {src_file}")
                continue

            if is_garbage_file(src_file, cleanup_config.junk_files):
                src_file.unlink()
                deleted_garbage_file_count += 1
                print(f"[已删除垃圾文件] {src_file}")

        except FileNotFoundError:
            print(f"[跳过] 文件已不存在: {src_file}")
        except Exception as e:
            failed_count += 1
            print(f"[删除垃圾文件失败] {src_file}，原因: {e}")

    return deleted_name_matched_count, deleted_garbage_file_count, failed_count


# ==================== 阶段2：递归清洗媒体文件名 ====================

def iter_media_files(root: Path, recursive: bool):
    entries = root.rglob("*") if recursive else root.iterdir()
    media_files = [p for p in entries if is_media_file(p)]
    media_files.sort(key=lambda p: str(p).lower())
    return media_files


# ==================== 主流程 ====================

def main() -> int:
    root = Path(DEFAULT_ROOT_DIR)

    if not root.exists() or not root.is_dir():
        print(f"[错误] 路径不存在或不是文件夹: {root}")
        return 2

    # ---------- 阶段1：筛选视频、移除垃圾 ----------
    print("=" * 60)
    print("[阶段1] 筛选视频、移除垃圾文件")
    print("=" * 60)

    try:
        rules_file, cleanup_config = load_cleanup_config(str(DEFAULT_RULES_FILE))
    except ValueError as exc:
        print(f"[错误] {exc}")
        return 2

    deleted_name_matched_count, deleted_garbage_file_count, delete_failed_count = (
        delete_garbage_files(root, rules_file, cleanup_config)
    )

    video_files = collect_video_files(root)

    if not video_files:
        print("[提示] 没有找到需要处理的视频文件。")
    else:
        print(f"[信息] 共找到 {len(video_files)} 个视频文件，准备处理...\n")

    moved_count = 0
    extra_deleted_name = 0
    failed_count = delete_failed_count

    for src_file in video_files:
        try:
            if not src_file.exists():
                print(f"[跳过] 文件已不存在: {src_file}")
                continue

            if is_garbage_file_by_name(src_file, cleanup_config.junk_name_keywords):
                try:
                    src_file.unlink()
                    extra_deleted_name += 1
                    print(f"[已删除关键字垃圾文件] {src_file}")
                except FileNotFoundError:
                    print(f"[跳过] 关键字垃圾文件已不存在: {src_file}")
                except Exception as e:
                    failed_count += 1
                    print(f"[删除关键字垃圾文件失败] {src_file}，原因: {e}")
                continue

            target_file = root / src_file.name
            target_file = get_unique_target_path(target_file)

            shutil.move(str(src_file), str(target_file))
            moved_count += 1
            print(f"[已移动] {src_file} -> {target_file}")

        except Exception as e:
            failed_count += 1
            print(f"[处理失败] {src_file}，原因: {e}")

    total_deleted_name = deleted_name_matched_count + extra_deleted_name

    print("\n[信息] 文件处理完成，等待目录状态刷新...\n")
    time.sleep(2.0)

    print("[信息] 开始删除空文件夹...\n")
    removed_dir_count, skipped_missing_count = remove_empty_dirs_with_retry(
        root, max_rounds=5, delay_sec=1.5
    )

    # ---------- 阶段2：递归清洗媒体文件名 ----------
    print("\n" + "=" * 60)
    print("[阶段2] 递归清洗媒体文件名")
    print("=" * 60)

    try:
        _, tokens = load_cleanup_tokens(str(DEFAULT_RULES_FILE))
    except ValueError as exc:
        print(f"[错误] {exc}")
        return 2

    if not tokens:
        print("[错误] 未加载到文件名清洗规则")
        return 2

    media_files = iter_media_files(root, recursive=True)

    if not media_files:
        print("[信息] 未找到媒体文件。")
    else:
        print(f"[信息] 根目录: {root}")
        print(f"[信息] 递归模式: True")
        print(f"[信息] 清洗配置: {rules_file}")
        print(f"[信息] 加载规则: {len(tokens)}")
        print(f"[信息] 媒体文件数量: {len(media_files)}\n")

    renamed_count = 0
    skipped_count = 0
    rename_failed_count = 0

    for src in media_files:
        new_stem, matches = strip_tokens_from_edges(src.stem, tokens)

        if not matches:
            skipped_count += 1
            continue

        if not new_stem:
            rename_failed_count += 1
            print(f"[失败] 清洗后文件名为空: {src}")
            continue

        dst = get_unique_target_path(src, new_stem=new_stem)
        if normalize_path_str(dst) == normalize_path_str(src):
            skipped_count += 1
            continue

        print(f"[计划] {src.name} -> {dst.name} (规则: {', '.join(matches)})")

        try:
            src.rename(dst)
            renamed_count += 1
        except Exception as exc:
            rename_failed_count += 1
            print(f"[失败] 重命名失败: {src} ({exc})")

    # ---------- 汇总报告 ----------
    print("\n" + "=" * 60)
    print("[汇总] 处理完成")
    print("=" * 60)
    print(f"\n--- 阶段1：筛选与清理 ---")
    print(f"成功移动视频: {moved_count}")
    print(f"已删除关键字垃圾文件: {total_deleted_name}")
    print(f"已删除垃圾文件(扩展名/名称): {deleted_garbage_file_count}")
    print(f"删除空文件夹: {removed_dir_count}")
    print(f"跳过已不存在目录: {skipped_missing_count}")
    print(f"阶段1 失败数量: {failed_count}")
    print(f"\n--- 阶段2：文件名清洗 ---")
    print(f"已重命名: {renamed_count}")
    print(f"已跳过: {skipped_count}")
    print(f"阶段2 失败数量: {rename_failed_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
