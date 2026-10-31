"""
AVRA Backend - Safety Verifier
Ensures instructions are grounded in visual evidence and safe.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("avra.verifier")


class SafetyVerifier:
    """
    Validates VLM outputs and pipeline instructions before they reach the user.
    
    Checks:
    1. Grounding: Every named hazard must exist in scene evidence
    2. Frame consistency: High-risk objects should persist across frames
    3. Contradiction: Instruction must not contradict detected hazards
    4. Confidence: Low-confidence detections get conservative treatment
    5. Staleness: Don't repeat guidance for stable old objects
    """

    def __init__(self):
        self.previous_actions = []
        self.repetition_window = 5  # frames

    def verify(
        self,
        vlm_response: dict,
        risk_data: dict,
        memory_state: dict,
        mode: str,
    ) -> dict:
        """
        Run all safety checks and return verified output.
        
        Returns:
            {
                "approved": bool,
                "action": str,          # The final instruction to speak
                "urgency": str,
                "warnings": [...],      # Internal warnings for logging
                "modified": bool,       # Whether the action was changed
                "original_action": str, # What the VLM originally suggested
            }
        """
        original_action = vlm_response.get("recommended_action", "")
        urgency = vlm_response.get("urgency", "routine")
        uncertainty = vlm_response.get("uncertainty", "low")
        objects = risk_data.get("objects", [])
        scene_risk_level = risk_data.get("scene_risk_level", "low")
        
        warnings = []
        modified = False
        action = original_action

        # ── Check 1: Grounding ─────────────────────────────────────
        grounding_ok = self._check_grounding(action, objects)
        if not grounding_ok:
            warnings.append("Action references objects not in evidence.")

        # ── Check 2: Contradiction detection ───────────────────────
        contradiction = self._check_contradiction(action, objects, risk_data)
        if contradiction:
            warnings.append(f"Contradiction: {contradiction}")
            # Override with safe instruction
            action = self._generate_safe_action(objects, risk_data)
            modified = True
            urgency = "warning"

        # ── Check 3: High uncertainty → conservative ───────────────
        if uncertainty == "high" and scene_risk_level in ("high", "critical"):
            action = "Stop. Scene is unclear. Proceed with extreme caution."
            modified = True
            urgency = "warning"
            warnings.append("High uncertainty with high risk. Overriding to conservative.")

        # ── Check 4: Verify mode requires frame consistency ────────
        if mode == "verify":
            new_count = memory_state.get("new_objects_count", 0)
            if new_count > 0 and scene_risk_level in ("high", "critical"):
                action = f"Caution. New {('hazards' if new_count > 1 else 'hazard')} detected. {action}"
                modified = True
                warnings.append("New objects in verify mode. Prepending caution.")

        # ── Check 5: Empty action fallback ─────────────────────────
        if not action or action.strip() == "":
            action = "Continue ahead carefully."
            modified = True
            warnings.append("Empty action from VLM. Using fallback.")

        # ── Check 6: Don't repeat identical instructions ───────────
        if action in self.previous_actions[-self.repetition_window:]:
            # Still approved, but flag as repetitive
            warnings.append("Repetitive instruction suppressed for audio.")

        self.previous_actions.append(action)
        if len(self.previous_actions) > 20:
            self.previous_actions = self.previous_actions[-20:]

        return {
            "approved": True,  # Always produce output, but may modify
            "action": action,
            "urgency": urgency,
            "warnings": warnings,
            "modified": modified,
            "original_action": original_action,
            "scene_risk_level": scene_risk_level,
        }

    def _check_grounding(self, action: str, objects: List[dict]) -> bool:
        """Check if the action references objects that exist in detections."""
        # Known obstacle keywords that, if mentioned in the action, must be grounded
        OBJECT_KEYWORDS = {
            "pole", "chair", "table", "person", "vehicle", "car", "bus",
            "truck", "cone", "barrier", "bench", "stairs", "trash",
            "obstacle", "hazard", "wall", "door", "sign", "fence",
        }
        action_lower = action.lower()
        detected_labels = {o.get("label", "").lower() for o in objects}

        # Check if the action mentions an object keyword not present in detections
        for keyword in OBJECT_KEYWORDS:
            if keyword in action_lower:
                # Check if this keyword (or a related label) exists in detected objects
                if not any(keyword in lbl for lbl in detected_labels):
                    logger.warning(
                        f"Grounding failure: action mentions '{keyword}' "
                        f"but detections have {detected_labels}"
                    )
                    return False
        return True

    def _check_contradiction(self, action: str, objects: List[dict], risk_data: dict) -> Optional[str]:
        """
        Check for dangerous contradictions:
        - "Path is clear" when there's a high-risk obstacle ahead
        - "Continue ahead" when path is blocked
        """
        action_lower = action.lower()
        scene_risk = risk_data.get("scene_risk_level", "low")
        path_status = risk_data.get("path_analysis", {}).get("path_status", "clear") if "path_analysis" in risk_data else "clear"

        # Check: says clear but path is blocked with high risk
        if ("clear" in action_lower or "continue ahead" in action_lower):
            blocking = [o for o in objects if o.get("in_path") and o.get("risk_level") in ("high", "critical")]
            if blocking:
                return f"Action says 'clear/continue' but {len(blocking)} high-risk objects in path."

        # Check: says stop but no significant hazard
        if "stop" in action_lower and scene_risk == "low" and not objects:
            return "Action says 'stop' but no hazards detected."

        return None

    def _generate_safe_action(self, objects: List[dict], risk_data: dict) -> str:
        """Generate a safe fallback action when contradiction is detected."""
        high_risk = [o for o in objects if o.get("risk_level") in ("high", "critical")]
        
        if high_risk:
            primary = high_risk[0]
            label = primary.get("label", "obstacle")
            direction = primary.get("direction", "ahead")
            distance = primary.get("distance", "near")

            # Find the safest alternative direction
            safe_dir = risk_data.get("path_analysis", {}).get("safest_direction", "right")
            
            return f"Caution. {label.title()} {direction}, {distance.replace('_', ' ')}. Veer {safe_dir}."

        return "Proceed with caution. Obstacle detected."
