"""脚本说明：提供媒体文件名清洗和垃圾文件识别的公共能力。"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_RULES_FILE = Path(__file__).with_name("media_cleanup_rules.json")


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
