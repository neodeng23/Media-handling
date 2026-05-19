"""脚本说明：将子目录视频移动到根目录，并清理垃圾文件与空目录。"""

import os
import shutil
import time
from pathlib import Path

from media_common import (
    VIDEO_EXTENSIONS,
    collect_all_dirs,
    get_unique_target_path,
    is_video_file,
    load_cleanup_config,
    normalize_path_str,
    remove_empty_dirs_once,
    remove_empty_dirs_with_retry,
    try_list_dir_items,
    walk_error_handler,
)
from media_common import is_garbage_file, is_garbage_file_by_name

DEFAULT_ROOT_DIR = r"W:\new"


def collect_video_files(root: Path):
    """
    收集根目录下所有子目录中的视频文件
    根目录自身已有的视频文件不处理
    """
    video_files = []
    root_norm = normalize_path_str(root)

    for current_root, dirs, files in os.walk(str(root)):
        current_path = Path(current_root)

        # 跳过根目录本身，只处理子目录
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
    """
    收集根目录下所有子目录中的文件。
    根目录自身的文件不处理。
    """
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


def move_all_videos_to_root(root_dir: str, rules_file: str | Path | None = None):
    # 不使用 resolve()，避免 WebDAV / 映射盘报错
    root = Path(os.path.abspath(root_dir))

    if not root.exists():
        print(f"[错误] 路径不存在: {root}")
        return

    if not root.is_dir():
        print(f"[错误] 输入的不是文件夹: {root}")
        return

    try:
        resolved_rules_file, cleanup_config = load_cleanup_config(rules_file)
    except ValueError as exc:
        print(f"[错误] {exc}")
        return

    moved_count = 0
    deleted_name_matched_count = 0
    deleted_garbage_file_count = 0
    failed_count = 0

    (
        deleted_name_matched_count,
        deleted_garbage_file_count,
        delete_failed_count,
    ) = delete_garbage_files(root, resolved_rules_file, cleanup_config)
    failed_count += delete_failed_count

    video_files = collect_video_files(root)

    if not video_files:
        print("[提示] 没有找到需要处理的视频文件。")
    else:
        print(f"[信息] 共找到 {len(video_files)} 个视频文件，准备处理...\n")

    for src_file in video_files:
        try:
            if not src_file.exists():
                print(f"[跳过] 文件已不存在: {src_file}")
                continue

            # 关键字垃圾文件：直接删除，不移动
            if is_garbage_file_by_name(src_file, cleanup_config.junk_name_keywords):
                try:
                    src_file.unlink()
                    deleted_name_matched_count += 1
                    print(f"[已删除关键字垃圾文件] {src_file}")
                except FileNotFoundError:
                    print(f"[跳过] 关键字垃圾文件已不存在: {src_file}")
                except Exception as e:
                    failed_count += 1
                    print(f"[删除关键字垃圾文件失败] {src_file}，原因: {e}")
                continue

            # 正常视频：移动到根目录
            target_file = root / src_file.name
            target_file = get_unique_target_path(target_file)

            shutil.move(str(src_file), str(target_file))
            moved_count += 1
            print(f"[已移动] {src_file} -> {target_file}")

        except Exception as e:
            failed_count += 1
            print(f"[处理失败] {src_file}，原因: {e}")

    print("\n[信息] 文件处理完成，等待目录状态刷新...\n")
    time.sleep(2.0)

    print("[信息] 开始删除空文件夹...\n")
    removed_count, skipped_missing_count = remove_empty_dirs_with_retry(root, max_rounds=5, delay_sec=1.5)

    print("\n=== 处理完成 ===")
    print(f"成功移动视频: {moved_count}")
    print(f"已删除关键字垃圾文件: {deleted_name_matched_count}")
    print(f"已删除垃圾文件: {deleted_garbage_file_count}")
    print(f"处理失败数量: {failed_count}")
    print(f"删除空文件夹: {removed_count}")
    print(f"跳过已不存在目录: {skipped_missing_count}")


if __name__ == "__main__":
    folder_path = (
        input(f"请输入要处理的根路径（直接回车使用默认路径: {DEFAULT_ROOT_DIR}）: ")
        .strip()
        .strip('"')
        or DEFAULT_ROOT_DIR
    )
    move_all_videos_to_root(folder_path)
