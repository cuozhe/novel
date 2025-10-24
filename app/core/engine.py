from __future__ import annotations

import html
import json
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin, quote

from .cleaner import clean_text, restore_paragraphs_from_html
from .http_client import HttpClient
from .models import BookItem, ChapterItem, SourceConfig, stable_id
from .parser import Parser


def _encode_keyword(keyword: str, rule: str) -> str:
    r = (rule or "utf-8").lower()
    if r in ("gbk", "gb2312"):
        return quote(keyword.encode("gbk"))
    if r in ("utf-8", "utf8"):
        return quote(keyword.encode("utf-8"))
    if r in ("url-encode", "urlencode", "url"):
        return quote(keyword, safe="")
    if r in ("none", "raw"):
        return keyword
    return quote(keyword.encode("utf-8"))


class CoreEngine:
    def __init__(self, sources: List[SourceConfig]) -> None:
        # sort by priority (smaller number => higher priority)
        self.sources = sorted(sources, key=lambda s: s.priority)
        self.http = HttpClient()
        self.parsers: Dict[str, Parser] = {}
        # in-memory registries
        self.books: Dict[str, BookItem] = {}
        self.book_source: Dict[str, SourceConfig] = {}
        self.chapters: Dict[str, ChapterItem] = {}

    def _get_parser(self, backend: str) -> Parser:
        if backend not in self.parsers:
            self.parsers[backend] = Parser(backend=backend)
        return self.parsers[backend]

    def search(self, keyword: str, site: Optional[str] = None) -> List[BookItem]:
        results: List[BookItem] = []
        for src in self.sources:
            if site and src.site.name != site:
                continue
            parser = self._get_parser(src.parser_backend)
            kw = _encode_keyword(keyword, src.search.keyword_encoding)
            url = src.search.url_template.replace("{keyword}", kw)
            status, headers, body = self.http.request(src.search.method, url)
            # choose encoding if provided by site config
            text = body.decode(src.site.encoding or "utf-8", errors="ignore")
            nodes = parser.select_nodes(text, src.search.list_selector)
            idx = 0
            for node in nodes:
                title_vals = parser.select_and_extract(node, src.search.sub.title)
                if not title_vals:
                    continue
                title = title_vals[0]
                author_vals = (
                    parser.select_and_extract(node, src.search.sub.author) if src.search.sub.author else []
                )
                author = author_vals[0] if author_vals else None
                cover_vals = (
                    parser.select_and_extract(node, src.search.sub.cover) if src.search.sub.cover else []
                )
                cover = cover_vals[0] if cover_vals else None
                detail_vals = parser.select_and_extract(node, src.search.sub.detail)
                if not detail_vals:
                    continue
                detail = urljoin(src.site.base_url, detail_vals[0])
                book_id = stable_id(src.site.name, detail)
                item = BookItem(
                    id=book_id,
                    site=src.site.name,
                    title=title,
                    author=author,
                    cover_url=cover,
                    detail_url=detail,
                    extra={"rank": idx},
                )
                self.books[book_id] = item
                self.book_source[book_id] = src
                results.append(item)
                idx += 1
            if site:
                # searching specific site, don't aggregate across others
                break
        return results

    def get_chapters(self, book_id: str) -> List[ChapterItem]:
        if book_id not in self.books:
            raise KeyError(f"Unknown book_id: {book_id}")
        src = self.book_source.get(book_id)
        if not src:
            raise KeyError(f"Source not found for book_id: {book_id}")
        parser = self._get_parser(src.parser_backend)
        detail_url = self.books[book_id].detail_url
        status, headers, body = self.http.request("get", detail_url)
        html_text = body.decode(src.site.encoding or "utf-8", errors="ignore")
        list_nodes = parser.select_nodes(html_text, src.chapters.list_selector)
        chapters: List[ChapterItem] = []
        for idx, node in enumerate(list_nodes):
            title_vals = parser.select_and_extract(node, src.chapters.title_selector)
            link_vals = parser.select_and_extract(node, src.chapters.link_selector)
            if not link_vals:
                continue
            url = urljoin(src.site.base_url, link_vals[0])
            title = title_vals[0] if title_vals else f"Chapter {idx+1}"
            chap_id = stable_id(book_id, url)
            chapter = ChapterItem(id=chap_id, book_id=book_id, index=idx, title=title, url=url)
            self.chapters[chap_id] = chapter
            chapters.append(chapter)
        # sort order
        if src.chapters.order.lower() == "desc":
            chapters = list(reversed(chapters))
        # dedupe if needed
        if src.chapters.dedupe_key:
            seen: set = set()
            key_type = src.chapters.dedupe_key.lower()
            new_list: List[ChapterItem] = []
            for c in chapters:
                key = c.title if key_type == "title" else c.url if key_type == "url" else f"{c.title}|{c.url}"
                if key in seen:
                    continue
                seen.add(key)
                new_list.append(c)
            chapters = new_list
        return chapters

    def get_content(self, chapter_id: str, max_pages: int = 5) -> str:
        if chapter_id not in self.chapters:
            raise KeyError(f"Unknown chapter_id: {chapter_id}")
        chap = self.chapters[chapter_id]
        src = self.book_source.get(chap.book_id)
        if not src:
            raise KeyError(f"Source not found for chapter_id: {chapter_id}")
        parser = self._get_parser(src.parser_backend)
        content_parts: List[str] = []
        next_url: Optional[str] = chap.url
        pages = 0
        while next_url and pages < max_pages:
            pages += 1
            status, headers, body = self.http.request("get", next_url)
            html_text = body.decode(src.site.encoding or "utf-8", errors="ignore")
            # Extract content block as HTML then process paragraphs
            nodes = parser.select_nodes(html_text, src.content.block_selector)
            if not nodes:
                break
            block_html = "".join(str(n) for n in nodes)
            para_html = restore_paragraphs_from_html(block_html, src.content.paragraph_strategy.get("br_to_newline", True))
            content_parts.append(para_html)
            # next page
            if src.content.next_page_selector:
                next_nodes = parser.select_and_extract(html_text, src.content.next_page_selector)
                next_url = urljoin(src.site.base_url, next_nodes[0]) if next_nodes else None
            else:
                next_url = None
        raw = "\n\n".join(content_parts)
        return clean_text(raw, src.content.filters, src.content.paragraph_strategy)

    def get_book_info(self, book_id: str) -> BookItem:
        if book_id not in self.books:
            raise KeyError(f"Unknown book_id: {book_id}")
        return self.books[book_id]
