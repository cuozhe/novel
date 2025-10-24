from __future__ import annotations

from typing import Callable, Dict, Optional

# Very lightweight plugin registry

_parsers: Dict[str, Callable] = {}
_exporters: Dict[str, Callable] = {}
_filters: Dict[str, Callable] = {}


def register_parser(name: str, factory: Callable) -> None:
    _parsers[name] = factory


def get_parser_factory(name: str) -> Optional[Callable]:
    return _parsers.get(name)


def register_exporter(name: str, func: Callable) -> None:
    _exporters[name] = func


def get_exporter(name: str) -> Optional[Callable]:
    return _exporters.get(name)


def register_filter(name: str, func: Callable) -> None:
    _filters[name] = func


def get_filter(name: str) -> Optional[Callable]:
    return _filters.get(name)
