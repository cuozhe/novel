from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Dict, List, Tuple

from .models import SourceConfig

SCHEMA_VERSION = "1.0"
CACHE_FILE = Path(__file__).resolve().parents[2] / ".cache" / "sources_cache.pkl"


def _validate_with_jsonschema(config: dict) -> None:
    try:
        import jsonschema
    except Exception:
        # Fallback: minimal shape checks
        required_top = ["site", "search", "chapters", "content"]
        for key in required_top:
            if key not in config:
                raise ValueError(f"Missing required field: {key}")
        return

    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "source.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(instance=config, schema=schema)


def _check_version(version: str) -> None:
    # very light compatibility check: major must match
    want_major = SCHEMA_VERSION.split(".")[0]
    got_major = version.split(".")[0]
    if want_major != got_major:
        raise ValueError(
            f"Incompatible schema version: expected {SCHEMA_VERSION}.*, got {version}"
        )


def load_source_file(path: Path) -> SourceConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    version = str(raw.get("version", SCHEMA_VERSION))
    _check_version(version)
    _validate_with_jsonschema(raw)
    return SourceConfig(**raw)


def _cache_key(paths: List[Path]) -> Tuple[str, float]:
    latest_mtime = 0.0
    joined = []
    for p in sorted(paths):
        if p.exists():
            m = p.stat().st_mtime
            latest_mtime = max(latest_mtime, m)
            joined.append(str(p))
    return ("|".join(joined), latest_mtime)


def load_sources(directory: Path) -> List[SourceConfig]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = list(directory.glob("*.json"))

    key, latest = _cache_key(paths)
    # try cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
            if cache.get("key") == key and cache.get("latest") == latest:
                return cache.get("sources", [])
        except Exception:
            pass

    sources: List[SourceConfig] = []
    for p in paths:
        try:
            sources.append(load_source_file(p))
        except Exception as e:
            # Skip invalid source files
            print(f"[source] skip {p.name}: {e}")
            continue

    # update cache
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump({"key": key, "latest": latest, "sources": sources}, f)
    except Exception:
        pass
    return sources
