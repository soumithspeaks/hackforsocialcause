"""
AVRA Backend - FastAPI Server with WebSocket
Serves the AVRA pipeline via HTTP and WebSocket endpoints.
"""
import asyncio
import base64
import io
import json
import logging
import time
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .pipeline import AVRAPipeline
from .gvs import GVSMode

# ── Logging setup ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("avra.server")

# ── App setup ──────────────────────────────────────────────────────
app = FastAPI(
    title="AVRA - Adaptive Visual-Reasoning Agent",
    description="Safety-critical assistive navigation system with VLM and GVS integration",
    version="0.1.0",
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pipeline instance ─────────────────────────────────────────────
# Default to real Qwen VLM (set AVRA_USE_REAL_VLM=false for mock mode)
USE_REAL_VLM = os.environ.get("AVRA_USE_REAL_VLM", "true").lower() == "true"
VLM_MODEL = os.environ.get("AVRA_VLM_MODEL", "Qwen/Qwen2.5-VL-3B-Instruct")
USE_TTS = os.environ.get("AVRA_USE_TTS", "false").lower() == "true"

pipeline = AVRAPipeline(
    use_real_vlm=USE_REAL_VLM,
    vlm_model=VLM_MODEL,
    gvs_mode=GVSMode.SIMULATION,
    use_tts=USE_TTS,
    verbosity="normal",
    log_dir=str(Path(__file__).parent.parent / "logs"),
)

# Frame-dropping flag: when True, incoming WS frames are silently dropped
_processing = False


# ── Startup ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting AVRA server (real_vlm={USE_REAL_VLM})...")
    pipeline.initialize()
    logger.info("AVRA pipeline ready.")


# ── HTTP Endpoints ─────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    """Get pipeline health status."""
    return pipeline.get_status()


class SettingsUpdate(BaseModel):
    verbosity: Optional[str] = None
    gvs_max_intensity: Optional[float] = None


@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    """Update pipeline settings."""
    pipeline.update_settings(settings.dict(exclude_none=True))
    return {"status": "ok"}


class FrameRequest(BaseModel):
    image_base64: str
    metadata: Optional[dict] = None


@app.post("/api/analyze")
async def analyze_frame(request: FrameRequest):
    """Analyze a single frame (HTTP endpoint for non-realtime use)."""
    result = pipeline.process_frame_from_base64(request.image_base64, request.metadata)
    return result


# ── WebSocket for real-time frame processing ──────────────────────
@app.websocket("/ws/frames")
async def websocket_frames(websocket: WebSocket):
    global _processing
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            # Receive text data (JSON) containing image_base64 and metadata
            data_str = await websocket.receive_text()

            # ── Frame-drop logic ──────────────────────────────────
            # If pipeline is still processing the previous frame,
            # silently drop this one to avoid thread pile-ups.
            if _processing:
                logger.debug("Dropping frame — pipeline still busy")
                continue

            data = json.loads(data_str)
            image_base64 = data.get("image_base64")
            metadata = data.get("metadata", {})

            if image_base64:
                _processing = True
                try:
                    # Run blocking inference in a background thread
                    result = await asyncio.to_thread(
                        pipeline.process_frame_from_base64, image_base64, metadata
                    )
                    await websocket.send_json(result)
                finally:
                    _processing = False
            else:
                await websocket.send_json({"error": "No image provided"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        _processing = False


# ── Serve static files (simulation frontend) ─────────────────────
SIMULATION_DIR = Path(__file__).parent.parent / "simulation" / "dist"
if SIMULATION_DIR.exists():
    app.mount("/", StaticFiles(directory=str(SIMULATION_DIR), html=True), name="simulation")


# ── Run with: python -m uvicorn backend.server:app --reload ───────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
