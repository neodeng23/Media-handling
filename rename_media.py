import os
from pathlib import Path

# 可按需增减视频扩展名
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v",
    ".ts", ".mts", ".m2ts", ".webm", ".rmvb", ".rm", ".3gp"
}

# 需要清洗掉的前缀列表
# 例如：489155.com@EBWH-302-C.mp4 -> EBWH-302-C.mp4
PREFIXES_TO_REMOVE = [
    "489155.com@",
    "hhd800.com@",
]


def is_video_file(file_path: Path) -> bool:
    try:
        return file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS
    except Exception:
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


def remove_known_prefix(filename: str):
    """
    如果文件名以 PREFIXES_TO_REMOVE 中某个前缀开头，则去掉该前缀
    返回: (matched_prefix, new_name)
    如果未命中，则 matched_prefix 为 None
    """
    for prefix in PREFIXES_TO_REMOVE:
        if filename.startswith(prefix):
            return prefix, filename[len(prefix):]
    return None, filename


def rename_files_in_root(root_dir: str):
    root = Path(os.path.abspath(root_dir))

    if not root.exists():
        print(f"[错误] 路径不存在: {root}")
        return

    if not root.is_dir():
        print(f"[错误] 输入的不是文件夹: {root}")
        return

    renamed_count = 0
    skipped_count = 0
    failed_count = 0

    print(f"[信息] 开始处理目录: {root}\n")

    for item in root.iterdir():
        try:
            if not is_video_file(item):
                continue

            matched_prefix, new_name = remove_known_prefix(item.name)

            if not matched_prefix:
                skipped_count += 1
                print(f"[跳过] 未命中前缀: {item.name}")
                continue

            if not new_name.strip():
                failed_count += 1
                print(f"[失败] 去前缀后文件名为空: {item.name}")
                continue

            target_path = root / new_name
            target_path = get_unique_target_path(target_path)

            if item == target_path:
                skipped_count += 1
                print(f"[跳过] 文件名无需修改: {item.name}")
                continue

            item.rename(target_path)
            renamed_count += 1
            print(f"[已重命名] {item.name} -> {target_path.name}")

        except Exception as e:
            failed_count += 1
            print(f"[重命名失败] {item}，原因: {e}")

    print("\n=== 处理完成 ===")
    print(f"成功重命名: {renamed_count}")
    print(f"跳过数量: {skipped_count}")
    print(f"失败数量: {failed_count}")


if __name__ == "__main__":
    folder_path = input("请输入要处理的目录: ").strip().strip('"')
    rename_files_in_root(folder_path)