from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config_loader import load_sources
from app.core.engine import CoreEngine
from app.core.models import SourceConfig


class SourceManager:
    def __init__(self, sources_dir: Path, hot_reload: bool = True, scan_interval: float = 2.0) -> None:
        self.sources_dir = Path(sources_dir)
        self.hot_reload = hot_reload
        self.scan_interval = scan_interval
        self._mtimes: Dict[Path, float] = {}
        self._sources: List[SourceConfig] = []
        self._prev_sources: List[SourceConfig] = []
        self._engine: Optional[CoreEngine] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.reload()
        if self.hot_reload and self._thread is None:
            self._thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def _watch_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._has_changes():
                    self.reload()
            except Exception as e:
                print(f"[source-manager] watch error: {e}")
            finally:
                time.sleep(self.scan_interval)

    def _has_changes(self) -> bool:
        changed = False
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        for p in self.sources_dir.glob("*.json"):
            m = p.stat().st_mtime
            if p not in self._mtimes or self._mtimes[p] != m:
                self._mtimes[p] = m
                changed = True
        # detect deleted files
        keys = list(self._mtimes.keys())
        for k in keys:
            if not k.exists():
                del self._mtimes[k]
                changed = True
        return changed

    def reload(self) -> None:
        self._prev_sources = self._sources
        self._sources = load_sources(self.sources_dir)
        # priority already handled by engine
        self._engine = CoreEngine(self._sources)
        print(f"[source-manager] loaded {len(self._sources)} sources")

    def rollback(self) -> None:
        if self._prev_sources:
            self._sources, self._prev_sources = self._prev_sources, self._sources
            self._engine = CoreEngine(self._sources)
            print("[source-manager] rollback applied")

    @property
    def engine(self) -> CoreEngine:
        if self._engine is None:
            self.reload()
        assert self._engine is not None
        return self._engine

    def list_sources(self) -> List[SourceConfig]:
        return list(self._sources)

    def get_source_by_site(self, site: str) -> Optional[SourceConfig]:
        for s in self._sources:
            if s.site.name == site:
                return s
        return None
