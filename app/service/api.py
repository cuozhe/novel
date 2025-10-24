from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from app.core.engine import CoreEngine
from app.core.models import BookItem, ChapterItem
from app.manager.source_manager import SourceManager
from .rate_limiter import TokenBucketLimiter

BASE_DIR = Path(__file__).resolve().parents[2]
SOURCES_DIR = BASE_DIR / "sources"

app = FastAPI(title="Novel Aggregation Framework", version="0.1.0")
app.add_middleware(TokenBucketLimiter, capacity=60, refill_rate=1.0)


manager = SourceManager(SOURCES_DIR, hot_reload=True)


@app.on_event("startup")
async def _on_startup():
    manager.start()


@app.on_event("shutdown")
async def _on_shutdown():
    manager.stop()


def get_engine() -> CoreEngine:
    return manager.engine


@app.get("/sources")
async def list_sources():
    return [
        {
            "site": s.site.name,
            "base_url": s.site.base_url,
            "priority": s.priority,
            "version": s.version,
            "backend": s.parser_backend,
        }
        for s in manager.list_sources()
    ]


@app.get("/search", response_model=List[BookItem])
async def search(keyword: str = Query(..., description="search keyword"), site: Optional[str] = None, engine: CoreEngine = Depends(get_engine)):
    try:
        return engine.search(keyword=keyword, site=site)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/books/{book_id}", response_model=BookItem)
async def get_book(book_id: str, engine: CoreEngine = Depends(get_engine)):
    try:
        return engine.get_book_info(book_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="book not found")


@app.get("/books/{book_id}/chapters", response_model=List[ChapterItem])
async def get_chapters(book_id: str, engine: CoreEngine = Depends(get_engine)):
    try:
        return engine.get_chapters(book_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="book not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chapters/{chapter_id}/content")
async def get_content(chapter_id: str, engine: CoreEngine = Depends(get_engine)):
    try:
        content = engine.get_content(chapter_id)
        return {"chapter_id": chapter_id, "content": content}
    except KeyError:
        raise HTTPException(status_code=404, detail="chapter not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/export/txt/{book_id}")
async def export_txt(book_id: str, engine: CoreEngine = Depends(get_engine)):
    try:
        book = engine.get_book_info(book_id)
        chapters = engine.get_chapters(book_id)
        parts = [f"{book.title} - {book.author or ''}".strip(), ""]
        for ch in chapters:
            parts.append(ch.title)
            parts.append("")
            parts.append(engine.get_content(ch.id))
            parts.append("")
        content = "\n".join(parts)
        return PlainTextResponse(content, media_type="text/plain; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            try:
                payload = json.loads(data)
            except Exception:
                await ws.send_json({"event": "error", "message": "invalid json"})
                continue
            action = payload.get("action")
            if action == "search":
                keyword = payload.get("keyword")
                site = payload.get("site")
                await ws.send_json({"event": "progress", "message": "searching"})
                try:
                    items = manager.engine.search(keyword, site)
                    await ws.send_json({"event": "result", "items": [i.dict() for i in items]})
                except Exception as e:
                    await ws.send_json({"event": "error", "message": str(e)})
            else:
                await ws.send_json({"event": "error", "message": "unknown action"})
    except WebSocketDisconnect:
        return
