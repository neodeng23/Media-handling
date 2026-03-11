"""脚本说明：提供媒体文件名清洗的公共能力（读取规则、路径归一化、前后缀去除）。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

DEFAULT_RULES_FILE = Path(__file__).with_name("media_name_cleanup_rules.txt")


def normalize_path_str(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def load_cleanup_tokens(rules_file: str | Path | None = None) -> tuple[Path, list[str]]:
    path = Path(rules_file).expanduser() if rules_file else DEFAULT_RULES_FILE

    if not path.exists() or not path.is_file():
        return path, []

    tokens: list[str] = []
    seen: set[str] = set()

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line not in seen:
            seen.add(line)
            tokens.append(line)

    # Match longer strings first to avoid partial hits.
    tokens.sort(key=len, reverse=True)
    return path, tokens


def compress_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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
