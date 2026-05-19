"""脚本说明：媒体处理公共库 —— 扩展名/文件检测/路径工具/目录清理/垃圾识别/文件名清洗。"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_RULES_FILE = Path(__file__).with_name("media_cleanup_rules.json")


# ==================== 公共扩展名常量 ====================

VIDEO_EXTENSIONS: set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v",
    ".ts", ".mts", ".m2ts", ".webm", ".rmvb", ".rm", ".3gp",
}

MEDIA_EXTENSIONS: set[str] = {
    # Video
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v",
    ".ts", ".mts", ".m2ts", ".webm", ".rmvb", ".rm", ".3gp",
    # Audio
    ".mp3", ".flac", ".aac", ".wav", ".m4a", ".ogg", ".wma", ".opus",
    # Image
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff",
}


# ==================== 文件类型工具 ====================

def is_media_file(
    file_path: Path,
    extensions: set[str] | None = None,
    *,
    skip_symlinks: bool = False,
) -> bool:
    try:
        if skip_symlinks and file_path.is_symlink():
            return False
        exts = extensions if extensions is not None else MEDIA_EXTENSIONS
        return file_path.is_file() and file_path.suffix.lower() in exts
    except Exception:
        return False


def is_video_file(file_path: Path) -> bool:
    return is_media_file(file_path, VIDEO_EXTENSIONS)


# ==================== 路径 / 重命名工具 ====================


@dataclass(frozen=True)
class JunkFileRules:
    exact_names: tuple[str, ...] = ()
    name_keywords: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class CleanupConfig:
    name_cleanup_tokens: tuple[str, ...] = ()
    junk_name_keywords: tuple[str, ...] = ()
    junk_files: JunkFileRules = field(default_factory=JunkFileRules)


def normalize_path_str(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def get_unique_target_path(
    target_path: Path, *, new_stem: str | None = None
) -> Path:
    if new_stem is not None:
        target = target_path.parent / f"{new_stem}{target_path.suffix}"
    else:
        target = target_path

    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    parent = target.parent

    index = 1
    while True:
        candidate = parent / f"{stem}({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


# ==================== 系统 / 管理员工具 ====================

def is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ==================== 目录扫描 / 删除工具 ====================

def walk_error_handler(err: OSError) -> None:
    print(f"[扫描目录失败] {err}")


def try_list_dir_items(path: Path) -> list[str]:
    try:
        if not path.exists():
            return ["<目录已不存在>"]
        return [p.name for p in path.iterdir()]
    except Exception as e:
        return [f"<无法读取目录内容: {e}>"]


def collect_all_dirs(root: Path) -> list[Path]:
    dir_list: list[Path] = []
    root_norm = normalize_path_str(root)

    for current_root, dirs, _files in os.walk(
        str(root), topdown=True, onerror=walk_error_handler
    ):
        current_path = Path(current_root)

        if normalize_path_str(current_path) != root_norm:
            dir_list.append(current_path)

        for d in dirs:
            subdir = current_path / d
            if normalize_path_str(subdir) != root_norm:
                dir_list.append(subdir)

    unique_dirs: dict[str, Path] = {}
    for d in dir_list:
        unique_dirs[normalize_path_str(d)] = d

    result = list(unique_dirs.values())
    result.sort(key=lambda p: len(p.parts), reverse=True)
    return result


def remove_empty_dirs_once(root: Path) -> tuple[int, int]:
    removed_count = 0
    skipped_missing_count = 0
    dir_list = collect_all_dirs(root)

    print(f"[信息] 本轮扫描到目录数量: {len(dir_list)}")

    if not dir_list:
        print("[提示] 没有扫描到任何子目录。")
        return 0, 0

    for current_path in dir_list:
        try:
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


def remove_empty_dirs_with_retry(
    root: Path, max_rounds: int = 5, delay_sec: float = 1.5
) -> tuple[int, int]:
    total_removed = 0
    total_skipped_missing = 0

    for round_index in range(1, max_rounds + 1):
        print(f"\n[信息] 第 {round_index} 轮删除空文件夹开始...\n")
        removed_this_round, skipped_missing_this_round = remove_empty_dirs_once(root)
        total_removed += removed_this_round
        total_skipped_missing += skipped_missing_this_round

        print(
            f"\n[信息] 第 {round_index} 轮删除完成，"
            f"本轮删除: {removed_this_round}，跳过已不存在目录: {skipped_missing_this_round}"
        )

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


# ==================== 配置 / 规则数据类 ====================


def _ensure_list(path: Path, field_name: str, value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise ValueError(f"{field_name} 必须是数组: {path}")


def _unique_strings(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue

        text = value.strip()
        if not text:
            continue

        normalized = text.casefold()
        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(text)

    return result


def _sorted_tokens(values: Iterable[object]) -> tuple[str, ...]:
    tokens = _unique_strings(values)
    tokens.sort(key=len, reverse=True)
    return tuple(tokens)


def _normalize_extensions(values: Iterable[object]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue

        ext = value.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext in seen:
            continue

        seen.add(ext)
        normalized.append(ext)

    return tuple(normalized)


def _load_legacy_txt_tokens(path: Path) -> CleanupConfig:
    tokens: list[str] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens.append(line)

    return CleanupConfig(name_cleanup_tokens=_sorted_tokens(tokens))


def load_cleanup_config(rules_file: str | Path | None = None) -> tuple[Path, CleanupConfig]:
    path = Path(rules_file).expanduser() if rules_file else DEFAULT_RULES_FILE

    if not path.exists() or not path.is_file():
        return path, CleanupConfig()

    if path.suffix.lower() == ".txt":
        return path, _load_legacy_txt_tokens(path)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件不是合法 JSON: {path} ({exc})") from exc

    if not isinstance(data, dict):
        raise ValueError(f"配置文件顶层必须是对象: {path}")

    name_cleanup_tokens = _ensure_list(path, "name_cleanup_tokens", data.get("name_cleanup_tokens", []))
    top_level_junk_name_keywords = _ensure_list(
        path, "junk_name_keywords", data.get("junk_name_keywords", [])
    )
    legacy_junk_media_keywords = _ensure_list(path, "junk_media_keywords", data.get("junk_media_keywords", []))

    junk_files_data = data.get("junk_files", {})
    if junk_files_data is None:
        junk_files_data = {}
    if not isinstance(junk_files_data, dict):
        raise ValueError(f"junk_files 必须是对象: {path}")

    junk_exact_names = _ensure_list(path, "junk_files.exact_names", junk_files_data.get("exact_names", []))
    junk_file_name_keywords = _ensure_list(
        path, "junk_files.name_keywords", junk_files_data.get("name_keywords", [])
    )
    junk_extensions = _ensure_list(path, "junk_files.extensions", junk_files_data.get("extensions", []))

    config = CleanupConfig(
        name_cleanup_tokens=_sorted_tokens(name_cleanup_tokens),
        junk_name_keywords=_sorted_tokens(
            [*top_level_junk_name_keywords, *legacy_junk_media_keywords]
        ),
        junk_files=JunkFileRules(
            exact_names=tuple(_unique_strings(junk_exact_names)),
            name_keywords=_sorted_tokens(junk_file_name_keywords),
            extensions=_normalize_extensions(junk_extensions),
        ),
    )
    return path, config


def load_cleanup_tokens(rules_file: str | Path | None = None) -> tuple[Path, list[str]]:
    path, config = load_cleanup_config(rules_file)
    return path, list(config.name_cleanup_tokens)


def compress_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_name_for_match(name: str) -> str:
    """
    用于做关键字匹配：
    - 转小写
    - 去掉扩展名
    - 去掉末尾的 (1) (2) (3) ...
    - 去掉所有空白字符
    """
    stem = Path(name).stem.lower()
    stem = re.sub(r"\(\d+\)$", "", stem)
    stem = re.sub(r"\s+", "", stem)
    return stem


def has_matching_name_keyword(name: str, keywords: Iterable[str]) -> bool:
    normalized_name = normalize_name_for_match(name)
    if not normalized_name:
        return False

    for keyword in keywords:
        normalized_keyword = normalize_name_for_match(keyword)
        if normalized_keyword and normalized_keyword in normalized_name:
            return True

    return False


def is_garbage_file_by_name(file_path: Path, keywords: Iterable[str]) -> bool:
    return has_matching_name_keyword(file_path.name, keywords)


def is_garbage_media_file(file_path: Path, keywords: Iterable[str]) -> bool:
    # Backward-compatible alias. The matching is name-based only and ignores extension.
    return is_garbage_file_by_name(file_path, keywords)


def is_garbage_file(file_path: Path, rules: JunkFileRules) -> bool:
    file_name = file_path.name
    file_name_lower = file_name.lower()

    if any(file_name_lower == name.lower() for name in rules.exact_names):
        return True

    if file_path.suffix.lower() in rules.extensions:
        return True

    return has_matching_name_keyword(file_name, rules.name_keywords)


def strip_tokens_from_edges(text: str, tokens: Iterable[str]) -> tuple[str, list[str]]:
    current = compress_spaces(text)
    matches: list[str] = []
    token_list = [t.strip() for t in tokens if t and t.strip()]

    while current:
        changed = False
        current_lower = current.lower()

        for token in token_list:
            token_lower = token.lower()

            if current_lower.startswith(token_lower):
                current = compress_spaces(current[len(token):].strip("._- "))
                matches.append(f"prefix:{token}")
                changed = True
                break

            if current_lower.endswith(token_lower):
                current = compress_spaces(current[:-len(token)].strip("._- "))
                matches.append(f"suffix:{token}")
                changed = True
                break

        if not changed:
            break

    return current, matches
