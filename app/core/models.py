from __future__ import annotations

import hashlib
from typing import List, Optional, Dict, Any

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - fallback if pydantic isn't installed at import time
    # Minimal fallback to allow static imports in non-runtime contexts
    class BaseModel:  # type: ignore
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)

        def dict(self, *args, **kwargs):  # type: ignore
            return self.__dict__

    def Field(default=None, **kwargs):  # type: ignore
        return default


class SelectorSpec(BaseModel):
    css: Optional[str] = Field(None, description="CSS selector expression")
    xpath: Optional[str] = Field(None, description="XPath expression")
    regex: Optional[str] = Field(None, description="Regex fallback if no nodes selected")
    attr: Optional[str] = Field(
        "text", description="Which attribute to extract, or 'text' for text content"
    )
    index: Optional[int] = Field(None, description="Take the nth match (0-based)")


class SearchSubSelectors(BaseModel):
    title: SelectorSpec
    author: Optional[SelectorSpec] = None
    cover: Optional[SelectorSpec] = None
    detail: SelectorSpec


class SearchRule(BaseModel):
    method: str = Field("get", description="HTTP method: get or post")
    url_template: str = Field(..., description="URL template containing {keyword}")
    keyword_encoding: str = Field(
        "utf-8", description="how to encode keyword: utf-8 | gbk | url-encode"
    )
    list_selector: SelectorSpec
    sub: SearchSubSelectors


class ChapterRule(BaseModel):
    list_selector: SelectorSpec
    title_selector: SelectorSpec
    link_selector: SelectorSpec
    order: str = Field("asc", description="asc or desc")
    dedupe_key: Optional[str] = Field(
        None, description="one of: title | url | both"
    )


class ContentRule(BaseModel):
    block_selector: SelectorSpec
    filters: List[str] = Field(
        default_factory=list, description="advertisement keyword list"
    )
    next_page_selector: Optional[SelectorSpec] = None
    paragraph_strategy: Dict[str, Any] = Field(
        default_factory=lambda: {
            "br_to_newline": True,
            "compress_empty_lines": True,
        }
    )


class SiteInfo(BaseModel):
    name: str
    base_url: str
    encoding: str = "utf-8"


class SourceConfig(BaseModel):
    version: str = "1.0"
    priority: int = 100
    parser_backend: str = Field("bs4", description="bs4|lxml|pyquery")
    site: SiteInfo
    search: SearchRule
    chapters: ChapterRule
    content: ContentRule


class BookItem(BaseModel):
    id: str
    site: str
    title: str
    author: Optional[str] = None
    cover_url: Optional[str] = None
    detail_url: str
    extra: Dict[str, Any] = Field(default_factory=dict)


class ChapterItem(BaseModel):
    id: str
    book_id: str
    index: int
    title: str
    url: str


def stable_id(*parts: str) -> str:
    m = hashlib.sha1()
    for p in parts:
        m.update(p.encode("utf-8", errors="ignore"))
    return m.hexdigest()
