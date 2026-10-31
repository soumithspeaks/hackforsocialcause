"""
AVRA Backend - Spatial Reasoning Module
Converts VLM object detections into user-relative spatial data.
"""
import logging
from typing import List, Dict, Optional
from enum import Enum

logger = logging.getLogger("avra.spatial")


class Direction(str, Enum):
    LEFT = "left"
    AHEAD_LEFT = "ahead-left"
    AHEAD = "ahead"
    AHEAD_RIGHT = "ahead-right"
    RIGHT = "right"


class Distance(str, Enum):
    VERY_CLOSE = "very_close"
    NEAR = "near"
    MEDIUM = "medium"
    FAR = "far"


# Central walking corridor: objects in the center ~40% of the frame
CENTRAL_CORRIDOR_LEFT = 0.30
CENTRAL_CORRIDOR_RIGHT = 0.70


def compute_direction_from_position(x_center_normalized: float) -> Direction:
    """
    Estimate direction from the horizontal position in the frame.
    x_center_normalized: 0.0 (left edge) to 1.0 (right edge)
    """
    if x_center_normalized < 0.20:
        return Direction.LEFT
    elif x_center_normalized < 0.40:
        return Direction.AHEAD_LEFT
    elif x_center_normalized < 0.60:
        return Direction.AHEAD
    elif x_center_normalized < 0.80:
        return Direction.AHEAD_RIGHT
    else:
        return Direction.RIGHT


def compute_distance_from_bbox(bbox_height_normalized: float) -> Distance:
    """
    Estimate distance tier from bounding box height (larger = closer).
    This is an approximate heuristic until depth estimation is available.
    """
    if bbox_height_normalized > 0.60:
        return Distance.VERY_CLOSE
    elif bbox_height_normalized > 0.35:
        return Distance.NEAR
    elif bbox_height_normalized > 0.15:
        return Distance.MEDIUM
    else:
        return Distance.FAR


def is_in_walking_path(x_center_normalized: float, bbox_width_normalized: float) -> bool:
    """Check if an object's bounding box overlaps the central walking corridor."""
    obj_left = x_center_normalized - bbox_width_normalized / 2
    obj_right = x_center_normalized + bbox_width_normalized / 2
    return obj_right > CENTRAL_CORRIDOR_LEFT and obj_left < CENTRAL_CORRIDOR_RIGHT


def enrich_object_with_spatial_data(obj: dict, frame_width: int = 640, frame_height: int = 480) -> dict:
    """
    Add spatial reasoning fields to a VLM-detected object.
    If the VLM already provided direction/distance, validate it.
    If bbox data is available, compute from geometry.
    """
    enriched = dict(obj)

    # If we have bounding box data (from YOLO or VLM), compute spatial
    if "bbox" in obj:
        bbox = obj["bbox"]  # [x1, y1, x2, y2] in pixels
        x_center = (bbox[0] + bbox[2]) / 2 / frame_width
        bbox_height = (bbox[3] - bbox[1]) / frame_height
        bbox_width = (bbox[2] - bbox[0]) / frame_width

        enriched["computed_direction"] = compute_direction_from_position(x_center).value
        enriched["computed_distance"] = compute_distance_from_bbox(bbox_height).value
        enriched["computed_in_path"] = is_in_walking_path(x_center, bbox_width)
    
    # Ensure required fields exist (use VLM-provided or computed values)
    if "direction" not in enriched:
        enriched["direction"] = enriched.get("computed_direction", Direction.AHEAD.value)
    if "distance" not in enriched:
        enriched["distance"] = enriched.get("computed_distance", Distance.MEDIUM.value)
    if "in_path" not in enriched:
        enriched["in_path"] = enriched.get("computed_in_path", False)

    return enriched


def analyze_path_clearance(objects: List[dict]) -> dict:
    """
    Analyze overall path clearance from a list of detected objects.
    Returns path status and the safest direction to move.
    """
    path_objects = [o for o in objects if o.get("in_path", False)]
    
    if not path_objects:
        return {
            "path_status": "clear",
            "safest_direction": "ahead",
            "blocking_objects": [],
        }

    # Count hazards by direction
    direction_hazards = {
        "left": 0, "ahead-left": 0, "ahead": 0, "ahead-right": 0, "right": 0
    }
    for obj in objects:
        d = obj.get("direction", "ahead")
        hazard = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(
            obj.get("hazard_level", "low"), 1
        )
        if d in direction_hazards:
            direction_hazards[d] += hazard

    # Find the safest direction
    safest = min(direction_hazards, key=direction_hazards.get)

    # Check if any high/critical hazard is in the walking path
    high_hazards_in_path = [
        o for o in path_objects
        if o.get("hazard_level") in ("high", "critical")
    ]

    if high_hazards_in_path:
        close_hazards = [
            o for o in high_hazards_in_path
            if o.get("distance") in ("very_close", "near")
        ]
        if close_hazards:
            status = "blocked"
        else:
            status = "partially_blocked"
    else:
        status = "partially_blocked" if path_objects else "clear"

    return {
        "path_status": status,
        "safest_direction": safest,
        "blocking_objects": [o.get("label", "unknown") for o in path_objects],
        "direction_hazard_scores": direction_hazards,
    }


def compute_spatial_summary(vlm_response: dict) -> dict:
    """
    Takes a VLM response and enriches it with computed spatial data.
    This is the main entry point for the spatial module.
    """
    objects = vlm_response.get("objects", [])
    enriched_objects = [enrich_object_with_spatial_data(obj) for obj in objects]
    path_analysis = analyze_path_clearance(enriched_objects)

    return {
        "objects": enriched_objects,
        "path_analysis": path_analysis,
        "scene_type": vlm_response.get("scene_type", "unknown"),
        "lighting": vlm_response.get("lighting", "normal"),
        "surface": vlm_response.get("surface", "unknown"),
    }
