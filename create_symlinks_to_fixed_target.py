"""脚本说明：接收多个源文件路径，并在固定目标目录中创建软链接。"""

import os
import sys
import ctypes

# 固定目标目录
TARGET_DIR = r"F:\P\link"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    if len(sys.argv) < 2:
        print("用法: python create_symlinks_to_fixed_target.py <源文件路径1> [源文件路径2] ...")
        print("示例: python create_symlinks_to_fixed_target.py \"W:\\Video\\A.mp4\" \"W:\\Video\\B.mkv\"")
        sys.exit(1)

    if not is_admin():
        print("警告: 未以管理员身份运行，创建符号链接可能会失败。")
        print("请尝试右键终端/脚本 -> '以管理员身份运行'。")

    # 确保目标目录存在
    if not os.path.exists(TARGET_DIR):
        try:
            os.makedirs(TARGET_DIR)
            print(f"已创建目标目录: {TARGET_DIR}")
        except Exception as e:
            print(f"错误: 无法创建目标目录 {TARGET_DIR}: {e}")
            sys.exit(1)

    success_count = 0
    for source_path in sys.argv[1:]:
        source_path = os.path.abspath(source_path) # 转为绝对路径
        
        if not os.path.exists(source_path):
            print(f"跳过: 源文件不存在 -> {source_path}")
            continue

        filename = os.path.basename(source_path)
        link_path = os.path.join(TARGET_DIR, filename)

        try:
            if os.path.exists(link_path) or os.path.islink(link_path):
                print(f"跳过: 链接已存在 -> {link_path}")
                continue
            
            os.symlink(source_path, link_path)
            print(f"成功: {filename}")
            success_count += 1
        except OSError as e:
            print(f"失败: {filename} - {e}")

    print(f"\n完成。成功创建: {success_count}/{len(sys.argv)-1}")

if __name__ == "__main__":
    main()
