"""
AVRA Backend - Scene Memory Module
Rolling memory for object tracking and temporal consistency.
"""
import time
import logging
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger("avra.memory")


class SceneMemory:
    """
    Maintains a rolling memory of detected objects over recent frames.
    Used for:
    - Frame-to-frame consistency (verify objects persist)
    - Staleness detection (don't re-alert for old stable objects)
    - New object detection (alert on newly appearing hazards)
    - Scene stability assessment
    """

    def __init__(self, memory_window_s: float = 5.0, max_tracks: int = 50):
        self.memory_window_s = memory_window_s
        self.max_tracks = max_tracks
        self.tracks: Dict[str, dict] = {}  # track_id -> track data
        self.frame_count = 0
        self.last_change_frame = 0
        self._track_counter = 0

    def update(self, objects: List[dict], timestamp: Optional[float] = None) -> dict:
        """
        Update memory with new frame detections.
        Returns a summary of what changed.
        """
        ts = timestamp or time.time()
        self.frame_count += 1

        # Expire old tracks
        self._expire_stale_tracks(ts)

        # Match new detections to existing tracks
        matched = set()
        new_objects = []
        continuing_objects = []

        for obj in objects:
            track_id = self._find_matching_track(obj)
            if track_id:
                # Update existing track
                self.tracks[track_id]["last_seen"] = ts
                self.tracks[track_id]["last_frame"] = self.frame_count
                self.tracks[track_id]["hit_count"] += 1
                self.tracks[track_id]["latest_data"] = obj
                matched.add(track_id)
                continuing_objects.append(obj)
            else:
                # New object
                new_id = self._create_track(obj, ts)
                new_objects.append(obj)
                self.last_change_frame = self.frame_count

        # Mark any unmatched tracks as potentially disappeared
        disappeared = []
        for tid, track in self.tracks.items():
            if tid not in matched and track["last_frame"] == self.frame_count - 1:
                track["miss_count"] = track.get("miss_count", 0) + 1
                if track["miss_count"] > 3:
                    disappeared.append(track["latest_data"].get("label", "unknown"))

        # Assess scene stability
        scene_stable = len(new_objects) == 0 and len(disappeared) == 0
        frames_since_change = self.frame_count - self.last_change_frame

        if new_objects:
            self.last_change_frame = self.frame_count

        return {
            "new_objects": new_objects,
            "new_objects_count": len(new_objects),
            "continuing_objects_count": len(continuing_objects),
            "disappeared_objects": disappeared,
            "total_tracked": len(self.tracks),
            "scene_stable": scene_stable,
            "frames_since_change": frames_since_change,
            "frame_number": self.frame_count,
        }

    def get_stable_objects(self, min_hits: int = 2) -> List[dict]:
        """Return objects that have been seen in at least `min_hits` frames."""
        return [
            t["latest_data"] for t in self.tracks.values()
            if t["hit_count"] >= min_hits
        ]

    def get_state(self) -> dict:
        """Return current memory state for the router."""
        return {
            "total_tracked": len(self.tracks),
            "scene_stable": (self.frame_count - self.last_change_frame) > 3,
            "frames_since_change": self.frame_count - self.last_change_frame,
            "new_objects_count": 0,  # Updated during self.update()
            "frame_number": self.frame_count,
        }

    def _find_matching_track(self, obj: dict) -> Optional[str]:
        """Simple matching: same label and similar direction."""
        label = obj.get("label", "").lower()
        direction = obj.get("direction", "")

        for tid, track in self.tracks.items():
            t_label = track["latest_data"].get("label", "").lower()
            t_direction = track["latest_data"].get("direction", "")
            if t_label == label and t_direction == direction:
                return tid
        return None

    def _create_track(self, obj: dict, timestamp: float) -> str:
        """Create a new track for an object."""
        self._track_counter += 1
        track_id = f"track_{self._track_counter}"
        self.tracks[track_id] = {
            "first_seen": timestamp,
            "last_seen": timestamp,
            "first_frame": self.frame_count,
            "last_frame": self.frame_count,
            "hit_count": 1,
            "miss_count": 0,
            "latest_data": obj,
        }
        return track_id

    def _expire_stale_tracks(self, current_time: float):
        """Remove tracks not seen within the memory window."""
        expired = [
            tid for tid, track in self.tracks.items()
            if current_time - track["last_seen"] > self.memory_window_s
        ]
        for tid in expired:
            del self.tracks[tid]

    def reset(self):
        """Clear all memory."""
        self.tracks.clear()
        self.frame_count = 0
        self.last_change_frame = 0
