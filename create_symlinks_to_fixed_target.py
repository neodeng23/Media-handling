"""脚本说明：编辑脚本开头常量，在固定目标目录中为多个源文件创建软链接。"""

import os
import sys
import ctypes
import subprocess

# 固定目标目录
TARGET_DIR = r"F:\P\link"

# 在这里填写需要创建软链接的源文件路径
SOURCE_PATHS = [
    r"W:\P\J\kin8\kin8-3449-4K.mp4",
]

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def relaunch_as_admin():
    script_path = os.path.abspath(sys.argv[0])
    cmdline = subprocess.list2cmdline([script_path])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        cmdline,
        os.getcwd(),
        1,
    )
    return result > 32

def main():
    if not SOURCE_PATHS:
        print("错误: SOURCE_PATHS 为空，请先在脚本开头填写至少一个源文件路径。")
        sys.exit(1)

    if not is_admin():
        print("检测到当前不是管理员权限，正在请求 UAC 提权...")
        if relaunch_as_admin():
            print("已发起管理员重启请求，请在弹出的 UAC 窗口中确认。")
            sys.exit(0)

        print("错误: 未能获取管理员权限，已取消执行。")
        sys.exit(1)

    # 确保目标目录存在
    if not os.path.exists(TARGET_DIR):
        try:
            os.makedirs(TARGET_DIR)
            print(f"已创建目标目录: {TARGET_DIR}")
        except Exception as e:
            print(f"错误: 无法创建目标目录 {TARGET_DIR}: {e}")
            sys.exit(1)

    success_count = 0
    for source_path in SOURCE_PATHS:
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

    print(f"\n完成。成功创建: {success_count}/{len(SOURCE_PATHS)}")

if __name__ == "__main__":
    main()
