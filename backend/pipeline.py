"""
AVRA Backend - Main Pipeline Orchestrator
Processes frames through the full perception-to-action pipeline.
"""
import time
import logging
import base64
import io
from typing import Optional
from PIL import Image

from .vlm import VLMEngine, MockVLMEngine
from .spatial import compute_spatial_summary
from .risk import compute_scene_risk
from .router import select_mode, should_speak
from .memory import SceneMemory
from .verifier import SafetyVerifier
from .gvs import GVSController, GVSMode
from .audio import AudioGuidance
from .logger import EvidenceLogger

logger = logging.getLogger("avra.pipeline")


class AVRAPipeline:
    """
    Main AVRA pipeline orchestrator.
    
    Flow: Frame → VLM → Spatial → Risk → Router → Verifier → GVS + Audio → Log
    """

    def __init__(
        self,
        use_real_vlm: bool = False,
        vlm_model: str = "Qwen/Qwen2.5-VL-3B-Instruct",
        gvs_mode: GVSMode = GVSMode.SIMULATION,
        use_tts: bool = False,
        verbosity: str = "normal",
        log_dir: str = "logs",
    ):
        # Initialize components
        if use_real_vlm:
            self.vlm = VLMEngine(model_name=vlm_model)
        else:
            self.vlm = MockVLMEngine()

        self.memory = SceneMemory(memory_window_s=5.0)
        self.verifier = SafetyVerifier()
        self.gvs = GVSController(mode=gvs_mode)
        self.audio = AudioGuidance(verbosity=verbosity, use_tts=use_tts)
        self.logger = EvidenceLogger(log_dir=log_dir)

        self.frame_count = 0
        self.last_speech_frame = -100
        self._initialized = False

        logger.info("AVRA Pipeline initialized.")

    def initialize(self):
        """Load models and prepare pipeline."""
        if not self._initialized:
            self.vlm.load()
            self._initialized = True
            logger.info("Pipeline fully initialized and ready.")

    def process_frame(self, image: Image.Image, metadata: Optional[dict] = None) -> dict:
        """
        Process a single frame through the full AVRA pipeline.
        
        Args:
            image: PIL Image (from camera, simulation, or video)
            metadata: Optional frame metadata (timestamp, source, etc.)
            
        Returns:
            Complete pipeline result with all intermediate data
        """
        start_time = time.time()
        self.frame_count += 1
        metadata = metadata or {}

        # ── Step 1: VLM Scene Analysis ─────────────────────────────
        vlm_response = self.vlm.analyze_frame(image, metadata=metadata)

        # ── Step 2: Spatial Reasoning ──────────────────────────────
        spatial_data = compute_spatial_summary(vlm_response)

        # ── Step 3: Risk Scoring ───────────────────────────────────
        risk_data = compute_scene_risk(
            spatial_data["objects"],
            spatial_data.get("path_analysis", {}),
        )

        # ── Step 4: Memory Update ──────────────────────────────────
        memory_update = self.memory.update(
            risk_data["objects"],
            timestamp=time.time(),
        )

        # ── Step 5: Mode Router ────────────────────────────────────
        memory_state = {**self.memory.get_state(), **memory_update}
        router_decision = select_mode(risk_data, memory_state)

        # ── Step 6: Safety Verification ────────────────────────────
        verified_action = self.verifier.verify(
            vlm_response, risk_data, memory_state, router_decision["mode"],
        )

        # ── Step 7: GVS Command Generation ────────────────────────
        path_analysis = spatial_data.get("path_analysis", {
            "path_status": "unknown",
            "safest_direction": "ahead",
        })
        gvs_command = self.gvs.generate_command(
            risk_data, path_analysis, verified_action,
        )

        # ── Step 8: Audio Guidance ─────────────────────────────────
        urgency = verified_action.get("urgency", "routine")
        speak_now = should_speak(
            router_decision["mode"], self.last_speech_frame,
            self.frame_count, urgency,
        )

        audio_result = {"queued": False, "text": verified_action["action"]}
        if speak_now:
            audio_result = self.audio.speak(verified_action["action"], urgency)
            if audio_result.get("queued"):
                self.last_speech_frame = self.frame_count

        # ── Step 9: Evidence Logging ───────────────────────────────
        self.logger.log_event(
            frame_id=self.frame_count,
            vlm_response=vlm_response,
            spatial_data=spatial_data,
            risk_data=risk_data,
            router_decision=router_decision,
            verified_action=verified_action,
            gvs_command=gvs_command,
            audio_result=audio_result,
            metadata=metadata,
        )

        elapsed = time.time() - start_time

        # ── Build response ─────────────────────────────────────────
        return {
            "frame_id": self.frame_count,
            "timestamp": time.time(),
            "processing_time_ms": round(elapsed * 1000, 1),

            # Scene understanding
            "objects": [
                {
                    "label": o.get("label", "unknown"),
                    "direction": o.get("direction", "ahead"),
                    "distance": o.get("distance", "medium"),
                    "risk_level": o.get("risk_level", "low"),
                    "risk_score": o.get("risk_score", 0),
                    "in_path": o.get("in_path", False),
                    "moving": o.get("moving", False),
                    "confidence": o.get("confidence", 0),
                }
                for o in risk_data.get("objects", [])
            ],

            # Path analysis
            "path_status": path_analysis.get("path_status", "unknown"),
            "safest_direction": path_analysis.get("safest_direction", "ahead"),

            # Risk
            "scene_risk_score": risk_data.get("scene_risk_score", 0),
            "scene_risk_level": risk_data.get("scene_risk_level", "low"),

            # Action
            "action": verified_action.get("action", ""),
            "urgency": urgency,
            "action_modified": verified_action.get("modified", False),

            # Router
            "reasoning_mode": router_decision.get("mode", "direct"),
            "router_reason": router_decision.get("reason", ""),

            # GVS
            "gvs": self.gvs.get_visualization_data(),

            # Memory
            "scene_stable": memory_state.get("scene_stable", True),
            "tracked_objects": memory_state.get("total_tracked", 0),

            # Audio
            "audio_spoken": audio_result.get("queued", False),

            # Scene metadata
            "scene_type": vlm_response.get("scene_type", "unknown"),
            "lighting": vlm_response.get("lighting", "normal"),
            "surface": vlm_response.get("surface", "unknown"),
        }

    def process_frame_from_base64(self, b64_data: str, metadata: Optional[dict] = None) -> dict:
        """Process a base64-encoded frame image."""
        try:
            img_bytes = base64.b64decode(b64_data)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            return self.process_frame(image, metadata)
        except Exception as e:
            logger.error(f"Failed to decode base64 frame: {e}")
            return {
                "frame_id": self.frame_count,
                "error": str(e),
                "action": "System error. Use caution.",
                "urgency": "critical",
            }

    def update_settings(self, settings: dict):
        """Update pipeline settings at runtime."""
        if "verbosity" in settings:
            self.audio.set_verbosity(settings["verbosity"])
        if "gvs_max_intensity" in settings:
            self.gvs.max_intensity = settings["gvs_max_intensity"]

    def get_status(self) -> dict:
        """Return pipeline health status."""
        return {
            "vlm_loaded": self.vlm.is_loaded(),
            "frame_count": self.frame_count,
            "session": self.logger.get_session_stats(),
            "memory_tracks": self.memory.get_state()["total_tracked"],
        }
