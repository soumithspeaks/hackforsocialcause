"""
AVRA Backend - Mode Router
Decides reasoning depth: Direct, Verify, Tool, or Deep.
"""
import logging
from typing import Dict

logger = logging.getLogger("avra.router")


class ReasoningMode:
    DIRECT = "direct"     # Low risk, stable → issue short instruction
    VERIFY = "verify"     # Medium risk or new obstacle → check across frames
    TOOL = "tool"         # Need geometry, counting, OCR → call deterministic tool
    DEEP = "deep"         # Complex scene, conflicting signals → full VLM reasoning


def select_mode(scene_risk: dict, memory_state: dict, settings: dict = None) -> dict:
    """
    Select the reasoning mode based on risk level, scene stability, and compute budget.
    
    Rule-based initially; can be replaced with a learned policy later.
    """
    settings = settings or {}
    risk_level = scene_risk.get("scene_risk_level", "low")
    risk_score = scene_risk.get("scene_risk_score", 0.0)
    hazard_count = scene_risk.get("hazard_count", {})
    
    # Memory-based stability
    scene_stable = memory_state.get("scene_stable", True)
    new_objects = memory_state.get("new_objects_count", 0)
    frames_since_change = memory_state.get("frames_since_change", 10)
    
    # Forced deep mode for debugging
    if settings.get("force_deep_mode", False):
        return {"mode": ReasoningMode.DEEP, "reason": "Forced deep mode by settings."}

    # ── Critical risk → always verify or deep ──────────────────────
    if risk_level == "critical":
        if not scene_stable or new_objects > 0:
            return {
                "mode": ReasoningMode.DEEP,
                "reason": f"Critical risk ({risk_score:.2f}) with unstable scene. Full analysis required.",
            }
        return {
            "mode": ReasoningMode.VERIFY,
            "reason": f"Critical risk ({risk_score:.2f}). Verifying across frames.",
        }

    # ── High risk → verify, or deep if unstable ───────────────────
    if risk_level == "high":
        if new_objects > 2 or not scene_stable:
            return {
                "mode": ReasoningMode.DEEP,
                "reason": f"High risk with {new_objects} new objects. Deep analysis.",
            }
        return {
            "mode": ReasoningMode.VERIFY,
            "reason": f"High risk ({risk_score:.2f}). Frame verification needed.",
        }

    # ── Medium risk → verify if new, direct if stable ─────────────
    if risk_level == "medium":
        if new_objects > 0:
            return {
                "mode": ReasoningMode.VERIFY,
                "reason": f"Medium risk with new detections. Verifying.",
            }
        if frames_since_change > 5:
            return {
                "mode": ReasoningMode.DIRECT,
                "reason": "Medium risk but stable scene. Direct response.",
            }
        return {
            "mode": ReasoningMode.VERIFY,
            "reason": "Medium risk, recent changes. Verifying.",
        }

    # ── Low risk → direct ─────────────────────────────────────────
    if scene_stable and frames_since_change > 3:
        return {
            "mode": ReasoningMode.DIRECT,
            "reason": "Low risk, stable scene. Direct instruction.",
        }

    return {
        "mode": ReasoningMode.DIRECT,
        "reason": "Default: low risk. Direct instruction.",
    }


def should_speak(mode: str, last_speech_frame: int, current_frame: int, urgency: str) -> bool:
    """
    Decide if the system should produce audio output for this frame.
    Prevents excessive repetitive warnings.
    """
    frames_since_speech = current_frame - last_speech_frame

    if urgency == "critical":
        return frames_since_speech >= 2  # Speak almost every time
    elif urgency == "warning":
        return frames_since_speech >= 5
    elif urgency == "alert":
        return frames_since_speech >= 10
    else:  # routine
        return frames_since_speech >= 20
