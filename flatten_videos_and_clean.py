import os
import re
import shutil
import time
from pathlib import Path

# 可按需增减视频扩展名
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v",
    ".ts", ".mts", ".m2ts", ".webm", ".rmvb", ".rm", ".3gp"
}

# =========================
# 不需要移动、直接删除的垃圾媒体关键字
# 规则：
# 1) 这里只匹配“文件名”，不看路径
# 2) 会自动忽略大小写、空格、以及结尾的 (1) (2) 这种重复编号
# 3) 你后续只需要往这里继续加
# =========================
GARBAGE_MEDIA_KEYWORDS = [
    "x u u 6 2 . c o m",
    "台湾uu美少女直播 20年信誉保证服务全球",
    "社 區 最 新 情 報",
    "18+游戏大全(996gg.cc)-七龍珠H版-三國志H版-三國群淫傳等",
]

# 如果你还想按更泛的域名/广告词去命中，也可以继续加
# 比如：
# "996gg.cc",
# "uu美少女直播",
# "最新地址获取",
# 但泛匹配越多，误删风险越高


def normalize_path_str(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def is_video_file(file_path: Path) -> bool:
    try:
        return file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS
    except Exception:
        return False


def normalize_media_name_for_match(name: str) -> str:
    """
    用于匹配垃圾媒体文件名：
    - 转小写
    - 去掉扩展名
    - 去掉末尾的 (1) (2) (3) ...
    - 去掉所有空白字符
    """
    stem = Path(name).stem.lower()

    # 去掉末尾重复编号，例如 xxx(1) / xxx(2)
    stem = re.sub(r"\(\d+\)$", "", stem)

    # 去掉所有空白字符
    stem = re.sub(r"\s+", "", stem)

    return stem


def is_garbage_media_file(file_path: Path) -> bool:
    """
    判断一个视频文件是否属于“垃圾媒体”
    命中后直接删除，不移动
    """
    normalized_name = normalize_media_name_for_match(file_path.name)

    for keyword in GARBAGE_MEDIA_KEYWORDS:
        normalized_keyword = normalize_media_name_for_match(keyword)
        if normalized_keyword and normalized_keyword in normalized_name:
            return True

    return False


def get_unique_target_path(target_path: Path) -> Path:
    """
    如果目标文件已存在，则自动生成:
    xxx(1).mp4 / xxx(2).mp4 / xxx(3).mp4 ...
    """
    if not target_path.exists():
        return target_path

    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent

    index = 1
    while True:
        new_path = parent / f"{stem}({index}){suffix}"
        if not new_path.exists():
            return new_path
        index += 1


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


def try_list_dir_items(path: Path):
    """
    尝试列出目录内容，用于调试为什么删不掉
    """
    try:
        if not path.exists():
            return ["<目录已不存在>"]
        return [p.name for p in path.iterdir()]
    except Exception as e:
        return [f"<无法读取目录内容: {e}>"]


def walk_error_handler(err):
    print(f"[扫描目录失败] {err}")


def collect_all_dirs(root: Path):
    """
    先完整收集 root 下所有目录（不含 root 自身）
    再按深度从深到浅排序
    """
    dir_list = []
    root_norm = normalize_path_str(root)

    for current_root, dirs, files in os.walk(str(root), topdown=True, onerror=walk_error_handler):
        current_path = Path(current_root)

        if normalize_path_str(current_path) != root_norm:
            dir_list.append(current_path)

        for d in dirs:
            subdir = current_path / d
            subdir_norm = normalize_path_str(subdir)
            if subdir_norm != root_norm:
                dir_list.append(subdir)

    # 去重
    unique_dirs = {}
    for d in dir_list:
        unique_dirs[normalize_path_str(d)] = d

    dir_list = list(unique_dirs.values())

    # 深层目录优先删除
    dir_list.sort(key=lambda p: len(p.parts), reverse=True)
    return dir_list


def remove_empty_dirs_once(root: Path):
    """
    尝试删除空目录。
    直接 rmdir()，失败就打印原因。
    修复 WebDAV 下“扫描到但实际已不存在”的情况。
    """
    removed_count = 0
    skipped_missing_count = 0
    dir_list = collect_all_dirs(root)

    print(f"[信息] 本轮扫描到目录数量: {len(dir_list)}")

    if not dir_list:
        print("[提示] 没有扫描到任何子目录。")
        return 0, 0

    for current_path in dir_list:
        try:
            # WebDAV 下可能扫描到旧目录，但实际已不存在
            if not current_path.exists():
                skipped_missing_count += 1
                print(f"[跳过已不存在目录] {current_path}")
                continue

            if not current_path.is_dir():
                continue

            try:
                if current_path.is_symlink():
                    print(f"[跳过符号链接目录] {current_path}")
                    continue
            except Exception:
                pass

            try:
                current_path.rmdir()
                removed_count += 1
                print(f"[已删除空文件夹] {current_path}")
            except FileNotFoundError:
                # 刚准备删时又消失了，WebDAV 上可能出现
                skipped_missing_count += 1
                print(f"[跳过已不存在目录] {current_path}")
            except OSError as e:
                items = try_list_dir_items(current_path)
                print(f"[未删除] {current_path}，原因: {e}，目录内容: {items}")
            except Exception as e:
                items = try_list_dir_items(current_path)
                print(f"[删除失败] {current_path}，原因: {e}，目录内容: {items}")

        except Exception as e:
            print(f"[处理目录异常] {current_path}，原因: {e}")

    return removed_count, skipped_missing_count


def remove_empty_dirs_with_retry(root: Path, max_rounds: int = 5, delay_sec: float = 1.5):
    """
    针对 WebDAV / 网络盘，目录状态可能有延迟刷新
    多尝试几轮删除空目录
    """
    total_removed = 0
    total_skipped_missing = 0

    for round_index in range(1, max_rounds + 1):
        print(f"\n[信息] 第 {round_index} 轮删除空文件夹开始...\n")
        removed_this_round, skipped_missing_this_round = remove_empty_dirs_once(root)
        total_removed += removed_this_round
        total_skipped_missing += skipped_missing_this_round

        print(f"\n[信息] 第 {round_index} 轮删除完成，本轮删除: {removed_this_round}，跳过已不存在目录: {skipped_missing_this_round}")

        if removed_this_round == 0:
            if round_index < max_rounds:
                print(f"[信息] 等待 {delay_sec} 秒后继续重试...\n")
                time.sleep(delay_sec)
            else:
                break
        else:
            if round_index < max_rounds:
                time.sleep(delay_sec)

    return total_removed, total_skipped_missing


def move_all_videos_to_root(root_dir: str):
    # 不使用 resolve()，避免 WebDAV / 映射盘报错
    root = Path(os.path.abspath(root_dir))

    if not root.exists():
        print(f"[错误] 路径不存在: {root}")
        return

    if not root.is_dir():
        print(f"[错误] 输入的不是文件夹: {root}")
        return

    moved_count = 0
    deleted_garbage_count = 0
    failed_count = 0

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

            # 垃圾媒体：直接删除，不移动
            if is_garbage_media_file(src_file):
                try:
                    src_file.unlink()
                    deleted_garbage_count += 1
                    print(f"[已删除垃圾媒体] {src_file}")
                except FileNotFoundError:
                    print(f"[跳过] 垃圾媒体已不存在: {src_file}")
                except Exception as e:
                    failed_count += 1
                    print(f"[删除垃圾媒体失败] {src_file}，原因: {e}")
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
    print(f"已删除垃圾媒体: {deleted_garbage_count}")
    print(f"处理失败数量: {failed_count}")
    print(f"删除空文件夹: {removed_count}")
    print(f"跳过已不存在目录: {skipped_missing_count}")


if __name__ == "__main__":
    folder_path = input("请输入要处理的根路径: ").strip().strip('"')
    move_all_videos_to_root(folder_path)