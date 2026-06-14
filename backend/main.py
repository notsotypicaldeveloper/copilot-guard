"""
CopilotGuard — FastAPI backend

Routes:
  GET  /                    → serves the single-page console
  GET  /api/state           → current file list + risk score
  POST /api/ask             → Copilot RAG answerer
  GET  /api/scan            → SSE stream: runs the 4-agent swarm live
  POST /api/reset           → resets tenant to initial state
"""
import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.tenant.data import get_adapter
from backend.copilot.answerer import ask_copilot
from backend.agents.swarm import run_swarm

app = FastAPI(title="CopilotGuard", version="1.0.0")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


# ── Serve UI ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    index = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=index.read_text(), status_code=200)


# ── State ─────────────────────────────────────────────────────────────────────

@app.get("/api/state")
async def get_state():
    adapter = get_adapter()
    items = adapter.list_items()

    # Risk score: count of CRITICAL + everyone-scoped files
    critical_exposed = sum(
        1 for i in items
        if i["scope"] == "everyone" and i.get("sensitivity") == "CRITICAL"
    )
    everyone_exposed = sum(1 for i in items if i["scope"] == "everyone")

    # Initial state (no scan yet): score based on exposure count
    if all(i.get("sensitivity") is None for i in items):
        risk_score = min(95, everyone_exposed * 20)
    else:
        risk_score = min(95, critical_exposed * 25 + (everyone_exposed - critical_exposed) * 5)

    return JSONResponse({
        "files": items,
        "risk_score": risk_score,
        "stats": {
            "total": len(items),
            "exposed": everyone_exposed,
            "critical": critical_exposed,
            "safe": len(items) - everyone_exposed,
        },
    })


# ── Copilot answerer ─────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    identity: str = "intern"


@app.post("/api/ask")
async def ask(req: AskRequest):
    result = ask_copilot(req.question, req.identity)
    return JSONResponse(result)


# ── Agent swarm — SSE stream ─────────────────────────────────────────────────

@app.get("/api/scan")
async def scan(request: Request):
    async def event_generator() -> AsyncGenerator[dict, None]:
        loop = asyncio.get_event_loop()

        def _run_sync():
            return list(run_swarm())

        # Run blocking swarm in thread pool so we don't block the event loop
        events = await loop.run_in_executor(None, _run_sync)

        for event in events:
            if await request.is_disconnected():
                break
            yield {"data": json.dumps(event)}
            await asyncio.sleep(0.05)  # tiny pause so UI can render each event

    return EventSourceResponse(event_generator())


# ── Reset ─────────────────────────────────────────────────────────────────────

@app.post("/api/reset")
async def reset():
    get_adapter().reset()
    return JSONResponse({"status": "reset", "message": "Tenant restored to initial state."})
