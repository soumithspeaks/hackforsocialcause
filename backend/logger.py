"""
AVRA Backend - Evidence Logger
JSONL logging for all pipeline decisions, enabling evaluation and debugging.
"""
import json
import os
import time
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger("avra.logger")


class EvidenceLogger:
    """
    Logs every pipeline decision as a JSON line for:
    - Debugging and inspection
    - Evaluation metrics computation
    - Training data collection
    - Safety audit trail
    """

    def __init__(self, log_dir: str = "logs", session_id: Optional[str] = None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id or f"session_{int(time.time())}"
        self.log_file = self.log_dir / f"{self.session_id}.jsonl"
        self.event_count = 0

        logger.info(f"Evidence logger writing to: {self.log_file}")

    def log_event(
        self,
        frame_id: int,
        vlm_response: dict,
        spatial_data: dict,
        risk_data: dict,
        router_decision: dict,
        verified_action: dict,
        gvs_command: dict,
        audio_result: dict,
        metadata: Optional[dict] = None,
    ):
        """Log a complete pipeline event."""
        self.event_count += 1

        event = {
            "event_id": self.event_count,
            "session_id": self.session_id,
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "frame_id": frame_id,
            "pipeline": {
                "vlm_response": self._sanitize(vlm_response),
                "spatial_data": self._sanitize(spatial_data),
                "risk_data": self._sanitize_risk(risk_data),
                "router_decision": router_decision,
                "verified_action": verified_action,
                "gvs_command": gvs_command,
                "audio_result": audio_result,
            },
            "metadata": metadata or {},
        }

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write log: {e}")

    def _sanitize(self, data: dict) -> dict:
        """Remove large/binary fields from log data."""
        sanitized = {}
        for k, v in data.items():
            if k.startswith("_") and k not in ("_inference_time_s", "_mock", "_parse_error"):
                continue  # Skip internal fields like _raw_response
            if isinstance(v, bytes):
                continue  # Skip binary data
            sanitized[k] = v
        return sanitized

    def _sanitize_risk(self, risk_data: dict) -> dict:
        """Slim down risk data for logging (remove per-object component details)."""
        sanitized = dict(risk_data)
        if "objects" in sanitized:
            sanitized["objects"] = [
                {
                    "label": o.get("label"),
                    "direction": o.get("direction"),
                    "distance": o.get("distance"),
                    "risk_score": o.get("risk_score"),
                    "risk_level": o.get("risk_level"),
                    "in_path": o.get("in_path"),
                }
                for o in sanitized["objects"]
            ]
        return sanitized

    def get_session_stats(self) -> dict:
        """Return summary statistics for the current session."""
        return {
            "session_id": self.session_id,
            "event_count": self.event_count,
            "log_file": str(self.log_file),
        }
