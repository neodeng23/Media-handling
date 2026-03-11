import os
import shutil
import time
from pathlib import Path

# 你可按需增减视频扩展名
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v",
    ".ts", ".mts", ".m2ts", ".webm", ".rmvb", ".rm", ".3gp"
}


def normalize_path_str(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def is_video_file(file_path: Path) -> bool:
    try:
        return file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS
    except Exception:
        return False


def has_any_video_under(folder: Path) -> bool:
    """
    判断 folder 目录下（包含所有子目录）是否存在任意视频文件
    """
    try:
        for current_root, dirs, files in os.walk(str(folder), topdown=True):
            for file_name in files:
                file_path = Path(current_root) / file_name
                if is_video_file(file_path):
                    return True
        return False
    except Exception as e:
        print(f"[检查失败] {folder}，原因: {e}")
        return True
        # 返回 True 是为了保守处理：检查异常时不删


def collect_all_subdirs(root: Path):
    """
    收集 root 下所有子目录（不含 root 本身）
    并按深度从深到浅排序
    """
    subdirs = []
    root_norm = normalize_path_str(root)

    try:
        for current_root, dirs, files in os.walk(str(root), topdown=True):
            current_path = Path(current_root)

            if normalize_path_str(current_path) != root_norm:
                subdirs.append(current_path)

            for d in dirs:
                subdir = current_path / d
                if normalize_path_str(subdir) != root_norm:
                    subdirs.append(subdir)
    except Exception as e:
        print(f"[扫描目录失败] {root}，原因: {e}")

    # 去重
    unique_map = {}
    for d in subdirs:
        unique_map[normalize_path_str(d)] = d

    result = list(unique_map.values())

    # 深层目录优先
    result.sort(key=lambda p: len(p.parts), reverse=True)
    return result


def delete_dir_force(folder: Path) -> bool:
    """
    强制删除整个目录（包含里面所有内容）
    """
    try:
        shutil.rmtree(str(folder))
        print(f"[已删除] {folder}")
        return True
    except Exception as e:
        print(f"[删除失败] {folder}，原因: {e}")
        return False


def remove_dirs_without_video(root: Path, max_rounds: int = 3, delay_sec: float = 1.5):
    """
    多轮扫描并删除：
    只要某个目录下完全没有视频文件，就删除该目录
    """
    total_deleted = 0
    root_norm = normalize_path_str(root)

    for round_index in range(1, max_rounds + 1):
        print(f"\n[信息] 第 {round_index} 轮开始扫描...\n")

        subdirs = collect_all_subdirs(root)
        print(f"[信息] 本轮扫描到目录数量: {len(subdirs)}")

        deleted_this_round = 0

        for folder in subdirs:
            try:
                if normalize_path_str(folder) == root_norm:
                    continue

                if not folder.exists():
                    continue

                if not folder.is_dir():
                    continue

                try:
                    if folder.is_symlink():
                        print(f"[跳过符号链接目录] {folder}")
                        continue
                except Exception:
                    pass

                has_video = has_any_video_under(folder)

                if has_video:
                    print(f"[保留] {folder}（存在视频文件）")
                else:
                    if delete_dir_force(folder):
                        deleted_this_round += 1

            except Exception as e:
                print(f"[处理异常] {folder}，原因: {e}")

        total_deleted += deleted_this_round

        print(f"\n[信息] 第 {round_index} 轮完成，本轮删除: {deleted_this_round}")

        if deleted_this_round == 0:
            break

        if round_index < max_rounds:
            print(f"[信息] 等待 {delay_sec} 秒后继续下一轮...\n")
            time.sleep(delay_sec)

    return total_deleted


def main():
    folder_path = input("请输入要处理的根路径: ").strip().strip('"')
    root = Path(os.path.abspath(folder_path))

    if not root.exists():
        print(f"[错误] 路径不存在: {root}")
        return

    if not root.is_dir():
        print(f"[错误] 输入的不是文件夹: {root}")
        return

    print(f"[信息] 开始处理: {root}")
    print("[规则] 扫描所有子文件夹；只要该文件夹及其所有子目录中都没有视频文件，就删除整个文件夹。")

    deleted_count = remove_dirs_without_video(root, max_rounds=3, delay_sec=1.5)

    print("\n=== 处理完成 ===")
    print(f"删除文件夹数量: {deleted_count}")


if __name__ == "__main__":
    main()