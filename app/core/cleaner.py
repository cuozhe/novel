from __future__ import annotations

import re
from typing import List

WHITESPACE_RE = re.compile(r"[\u00A0\u3000\s]+", re.M)  # \xa0, full-width space, etc.
MULTI_EMPTY_LINES = re.compile(r"\n{3,}")


DEFAULT_AD_KEYWORDS = [
    "请记住本书首发域名",
    "关注公众号",
    "收藏本站",
]


def normalize_whitespace(text: str) -> str:
    text = WHITESPACE_RE.sub(" ", text)
    return text


def remove_ads(text: str, keywords: List[str]) -> str:
    all_keys = set(DEFAULT_AD_KEYWORDS + (keywords or []))
    for k in all_keys:
        if not k:
            continue
        text = text.replace(k, "")
    return text


def restore_paragraphs_from_html(html: str, br_to_newline: bool = True) -> str:
    # Very simple heuristics: convert <br> to \n, wrap </p>, </div>
    # Use regex to avoid heavy parser dependency here.
    t = html
    if br_to_newline:
        t = re.sub(r"<\s*br\s*/?>", "\n", t, flags=re.I)
    # Block-level end tags to newline
    t = re.sub(r"</\s*(p|div|section|article|h\d)\s*>", "\n", t, flags=re.I)
    # Strip tags
    t = re.sub(r"<[^>]+>", "", t)
    return t


def compress_empty_lines(text: str) -> str:
    return MULTI_EMPTY_LINES.sub("\n\n", text)


def clean_text(text: str, filters: List[str], paragraph_strategy: dict) -> str:
    text = normalize_whitespace(text)
    text = remove_ads(text, filters)
    if paragraph_strategy.get("compress_empty_lines", True):
        text = compress_empty_lines(text)
    return text.strip()
