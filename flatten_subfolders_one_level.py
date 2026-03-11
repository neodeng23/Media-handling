"""脚本说明：将根目录下一层文件夹中的子文件夹提升到根目录，并清理空父目录。"""

import os
import shutil
from pathlib import Path


def get_unique_target_path(target_dir: Path, name: str) -> Path:
    """
    如果目标目录下已存在同名文件夹，则自动生成不冲突的新名字
    例如 x -> x_1 -> x_2
    """
    candidate = target_dir / name
    if not candidate.exists():
        return candidate

    index = 1
    while True:
        candidate = target_dir / f"{name}_{index}"
        if not candidate.exists():
            return candidate
        index += 1


def flatten_one_level(root_path: str):
    root = Path(root_path).resolve()

    if not root.exists():
        print(f"[错误] 路径不存在: {root}")
        return

    if not root.is_dir():
        print(f"[错误] 输入的不是文件夹: {root}")
        return

    print(f"开始扫描根目录: {root}")
    print("-" * 60)

    # 只扫描 root 下一层的文件夹
    for item in root.iterdir():
        if not item.is_dir():
            continue

        print(f"\n检查文件夹: {item.name}")

        try:
            children = list(item.iterdir())
        except PermissionError:
            print(f"  [跳过] 无权限访问: {item}")
            continue
        except Exception as e:
            print(f"  [跳过] 读取失败: {item}, 原因: {e}")
            continue

        subdirs = [x for x in children if x.is_dir()]
        files = [x for x in children if x.is_file()]
        others = [x for x in children if not x.is_dir() and not x.is_file()]

        if files or others:
            print("  [不处理] 该文件夹中存在非文件夹内容。")
            if files:
                print("    普通文件:")
                for f in files:
                    print(f"      - {f.name}")
            if others:
                print("    其他类型内容:")
                for o in others:
                    print(f"      - {o.name}")
            continue

        if not subdirs:
            print("  [不处理] 该文件夹是空的，没有子文件夹可移动。")
            continue

        print("  [处理] 该文件夹中只有子文件夹，准备移动到根目录下：")
        moved_count = 0

        for subdir in subdirs:
            target = get_unique_target_path(root, subdir.name)
            try:
                shutil.move(str(subdir), str(target))
                print(f"    已移动: {subdir.name}  ->  {target.name}")
                moved_count += 1
            except Exception as e:
                print(f"    [失败] 移动 {subdir.name} 时出错: {e}")

        # 移动完成后，若当前父文件夹已为空，则自动删除
        try:
            remaining = list(item.iterdir())
            if not remaining:
                item.rmdir()
                print(f"  [已删除] 空文件夹已删除: {item.name}")
            else:
                print(f"  [保留] 文件夹未清空，未删除: {item.name}")
        except Exception as e:
            print(f"  [警告] 检查或删除空文件夹失败: {item.name}, 原因: {e}")

    print("\n处理完成。")


if __name__ == "__main__":
    user_input = input("请输入要扫描的根路径: ").strip().strip('"')
    flatten_one_level(user_input)
