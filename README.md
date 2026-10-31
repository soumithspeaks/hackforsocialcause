# AVRA — Adaptive Visual-Reasoning Agent

> Safety-critical assistive navigation system with VLM, GVS, and 3D simulation.

## Quick Start

### 1. Run the Simulation (Frontend Only — Demo Mode)

```powershell
cd simulation
npm install
npm run dev
```

Open http://localhost:5173 in your browser.
- **WASD** to move, **Mouse** to look (click viewport first to lock cursor)
- Runs in **Demo Mode** when backend is not connected — cycles through realistic scenarios
- All panels (risk, objects, GVS, router, evidence log) update in real-time

### 2. Run with Backend (Full Pipeline)

#### Install Python dependencies:
```powershell
cd backend
pip install -r requirements.txt
```

#### Start the backend server:
```powershell
# Mock VLM mode (no GPU needed, for testing):
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload

# Real VLM mode (requires GPU + Qwen2.5-VL 3B):
$env:AVRA_USE_REAL_VLM="true"
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

#### Start the frontend (in another terminal):
```powershell
cd simulation
npm run dev
```

The frontend automatically connects to the backend via WebSocket at `ws://localhost:8000/ws/frames`.

### 3. VLM Setup (Qwen2.5-VL 3B)

The VLM model downloads automatically on first run when `AVRA_USE_REAL_VLM=true`.
It uses 4-bit quantization to fit on RTX 3050 (4GB VRAM).

If you want to pre-download:
```python
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
Qwen2_5_VLForConditionalGeneration.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct")
AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct")
```

---

## Architecture

```
Camera/Simulation Frame
        │
        ▼
┌─────────────────┐
│   VLM Engine     │  ← Qwen2.5-VL 3B (4-bit quantized)
│   (vlm.py)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Spatial Reasoning│  ← Direction, distance, path intersection
│   (spatial.py)   │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Risk Scoring    │  ← Per-object + scene-level risk
│   (risk.py)      │
└────────┬────────┘
         ▼
┌────────┴────────┐
│  Memory + Router │  ← Scene stability, mode selection
│ (memory/router)  │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Safety Verifier  │  ← Grounding, contradiction, confidence
│  (verifier.py)   │
└───┬─────────┬───┘
    ▼         ▼
┌───────┐ ┌───────┐
│ Audio │ │  GVS  │
│ (TTS) │ │ Stim  │
└───────┘ └───────┘
```

## Project Structure

```
avra/
├── backend/                 # Python FastAPI backend
│   ├── server.py            # FastAPI + WebSocket server
│   ├── pipeline.py          # Main orchestrator
│   ├── vlm.py               # Qwen2.5-VL 3B + MockVLM
│   ├── spatial.py           # Direction/distance/path analysis
│   ├── risk.py              # Risk scoring engine
│   ├── router.py            # Mode router (Direct/Verify/Tool/Deep)
│   ├── memory.py            # Scene memory
│   ├── verifier.py          # Safety verification
│   ├── gvs.py               # GVS command generator
│   ├── audio.py             # TTS guidance
│   └── logger.py            # JSONL evidence logging
│
├── simulation/              # Vite + Three.js frontend
│   ├── src/
│   │   ├── main.js          # App entry + UI logic
│   │   ├── simulation/
│   │   │   └── Scene.js     # 3D environment + controls
│   │   └── styles/
│   │       └── index.css    # Dark glassmorphic design
│   ├── index.html           # Full layout
│   └── package.json
│
└── logs/                    # Runtime evidence logs (JSONL)
```

## Simulation Scenes

| Scene | Description |
|-------|-------------|
| Indoor Corridor | Corridor with poles, chairs, tables, people, barriers, stairs |
| Outdoor Sidewalk | Street with vehicles, poles, pedestrians, benches, cones |
| Complex Scene | Dense environment with many overlapping obstacles |

## GVS Integration

The GVS module translates spatial reasoning into vestibular stimulation commands:

| Detection | GVS Response |
|-----------|-------------|
| Obstacle ahead-left | Rightward stimulation (body veers right) |
| Obstacle ahead-right | Leftward stimulation (body veers left) |
| Obstacle directly ahead | Bilateral STOP signal |
| Urgent hazard | Sharp high-intensity pulse |

The simulation dashboard visualizes electrode activation, body lean, and directional arrows.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AVRA_USE_REAL_VLM` | `false` | Enable real Qwen2.5-VL inference |
| `AVRA_VLM_MODEL` | `Qwen/Qwen2.5-VL-3B-Instruct` | VLM model name |
| `AVRA_USE_TTS` | `false` | Enable text-to-speech output |

## Sample Data and Tests

Representative simulation metadata and expected mock-VLM outputs are in
`backend/tests/data/sample_scenes.json`. They cover a clear corridor, a close
pole in the walking path, and a vehicle hazard. Run the backend tests from the
project root with:

```powershell
python -m pytest backend/tests
```

These are synthetic simulation examples for development and smoke testing; they
are not clinical or real-world safety validation data.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
