from __future__ import annotations

import re
from typing import List, Optional, Any

from .models import SelectorSpec

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

try:
    from lxml import etree  # type: ignore
except Exception:  # pragma: no cover
    etree = None  # type: ignore


class Parser:
    def __init__(self, backend: str = "bs4") -> None:
        self.backend = backend

    def _soup(self, html: str) -> Any:
        if BeautifulSoup is None:
            raise RuntimeError("BeautifulSoup4 is required for bs4 backend")
        return BeautifulSoup(html, "html.parser")

    def _lxml(self, html: str) -> Any:
        if etree is None:
            raise RuntimeError("lxml is required for lxml backend")
        return etree.HTML(html)

    def select_nodes(self, html_or_node: Any, spec: SelectorSpec) -> List[Any]:
        nodes: List[Any] = []
        if self.backend == "bs4":
            if isinstance(html_or_node, str):
                node = self._soup(html_or_node)
            else:
                node = html_or_node
            if spec.css:
                nodes = list(node.select(spec.css))
        elif self.backend == "lxml":
            node = self._lxml(html_or_node) if isinstance(html_or_node, str) else html_or_node
            if spec.css:
                # lxml doesn't support CSS by default; fallback to xpath via cssselect if available
                try:
                    from lxml.cssselect import CSSSelector  # type: ignore

                    sel = CSSSelector(spec.css)
                    nodes = sel(node)
                except Exception:
                    nodes = []
            if not nodes and spec.xpath:
                try:
                    nodes = node.xpath(spec.xpath)
                except Exception:
                    nodes = []
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

        # regex fallback on full HTML/text
        if not nodes and spec.regex:
            text = (
                html_or_node if isinstance(html_or_node, str) else str(getattr(html_or_node, "text", ""))
            )
            matches = re.findall(spec.regex, text, re.S)
            nodes = matches  # type: ignore
        return nodes

    def extract(self, element: Any, spec: SelectorSpec) -> Optional[str]:
        # When element is string (from regex), just return it
        if isinstance(element, str):
            return element
        attr = (spec.attr or "text").lower()
        if self.backend == "bs4":
            if attr == "text":
                return element.get_text(strip=True)
            else:
                return element.get(attr)
        elif self.backend == "lxml":
            if attr == "text":
                return element.text if hasattr(element, "text") else None
            else:
                try:
                    return element.attrib.get(attr)
                except Exception:
                    return None
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def select_and_extract(self, html_or_node: Any, spec: SelectorSpec) -> List[str]:
        nodes = self.select_nodes(html_or_node, spec)
        if spec.index is not None:
            nodes = nodes[spec.index : spec.index + 1]
        results: List[str] = []
        for n in nodes:
            v = self.extract(n, spec)
            if v is not None:
                results.append(v)
        return results
