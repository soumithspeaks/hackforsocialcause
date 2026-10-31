"""
AVRA Backend - Risk Scoring Engine
Computes per-object and scene-level risk scores.
"""
import logging
from typing import List, Dict

logger = logging.getLogger("avra.risk")

# ── Hazard weights by object class ─────────────────────────────────
HAZARD_WEIGHTS = {
    # Vehicles (critical)
    "car": 0.95, "bus": 0.95, "truck": 0.95, "motorcycle": 0.90,
    "bicycle": 0.80, "scooter": 0.85,
    # Infrastructure hazards
    "pole": 0.70, "pillar": 0.70, "bollard": 0.65,
    "stairs": 0.75, "stairs_up": 0.75, "stairs_down": 0.80,
    "curb": 0.60, "pothole": 0.70, "construction": 0.80,
    "barrier": 0.65, "fence": 0.50,
    # People/animals
    "person": 0.50, "dog": 0.55, "animal": 0.55,
    # Furniture/objects
    "chair": 0.45, "bench": 0.40, "table": 0.45,
    "trash_can": 0.35, "cone": 0.40,
    # Low hazard
    "wall": 0.30, "door": 0.25, "tree": 0.35,
    "sign": 0.15, "plant": 0.20,
    # Default
    "obstacle": 0.60, "object": 0.40, "unknown": 0.50,
}

# ── Distance multipliers (closer = more dangerous) ─────────────────
DISTANCE_MULTIPLIERS = {
    "very_close": 1.0,
    "near": 0.75,
    "medium": 0.45,
    "far": 0.20,
}

# ── Path intersection multiplier ───────────────────────────────────
PATH_MULTIPLIER_IN_PATH = 1.5
PATH_MULTIPLIER_OFF_PATH = 0.4

# ── Movement multiplier ────────────────────────────────────────────
MOVING_MULTIPLIER = 1.3
STATIC_MULTIPLIER = 1.0

# ── Risk thresholds ────────────────────────────────────────────────
RISK_THRESHOLDS = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
    "critical": 0.90,
}


def compute_object_risk(obj: dict) -> dict:
    """
    Compute a risk score for a single detected object.
    
    Risk = hazard_weight × distance_multiplier × path_multiplier × movement_multiplier
    Clamped to [0, 1].
    """
    label = obj.get("label", "unknown").lower()
    distance = obj.get("distance", "medium")
    in_path = obj.get("in_path", False)
    moving = obj.get("moving", False)
    confidence = obj.get("confidence", 0.7)

    # Base hazard weight
    hazard_weight = HAZARD_WEIGHTS.get(label, 0.50)

    # Distance multiplier
    dist_mult = DISTANCE_MULTIPLIERS.get(distance, 0.45)

    # Path intersection
    path_mult = PATH_MULTIPLIER_IN_PATH if in_path else PATH_MULTIPLIER_OFF_PATH

    # Movement
    move_mult = MOVING_MULTIPLIER if moving else STATIC_MULTIPLIER

    # Compute raw risk
    raw_risk = hazard_weight * dist_mult * path_mult * move_mult

    # Scale by detection confidence
    risk_score = min(1.0, raw_risk * confidence)

    # Determine risk level
    if risk_score >= RISK_THRESHOLDS["critical"]:
        risk_level = "critical"
    elif risk_score >= RISK_THRESHOLDS["high"]:
        risk_level = "high"
    elif risk_score >= RISK_THRESHOLDS["medium"]:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        **obj,
        "risk_score": round(risk_score, 3),
        "risk_level": risk_level,
        "_risk_components": {
            "hazard_weight": hazard_weight,
            "distance_multiplier": dist_mult,
            "path_multiplier": path_mult,
            "movement_multiplier": move_mult,
            "confidence": confidence,
        },
    }


def compute_scene_risk(objects: List[dict], path_analysis: dict) -> dict:
    """
    Compute scene-level risk from all objects and path analysis.
    Returns the highest individual risk as the scene risk.
    """
    scored_objects = [compute_object_risk(obj) for obj in objects]

    if not scored_objects:
        return {
            "objects": [],
            "scene_risk_score": 0.0,
            "scene_risk_level": "low",
            "primary_hazard": None,
            "hazard_count": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        }

    # Sort by risk (highest first)
    scored_objects.sort(key=lambda x: x["risk_score"], reverse=True)

    # Scene risk = highest individual object risk
    scene_risk = scored_objects[0]["risk_score"]

    # If path is blocked, boost scene risk
    path_status = path_analysis.get("path_status", "clear")
    if path_status == "blocked":
        scene_risk = min(1.0, scene_risk * 1.2)
    elif path_status == "partially_blocked":
        scene_risk = min(1.0, scene_risk * 1.1)

    # Count hazards by level
    hazard_count = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for obj in scored_objects:
        level = obj.get("risk_level", "low")
        if level in hazard_count:
            hazard_count[level] += 1

    # Determine scene risk level
    if scene_risk >= RISK_THRESHOLDS["critical"]:
        scene_risk_level = "critical"
    elif scene_risk >= RISK_THRESHOLDS["high"]:
        scene_risk_level = "high"
    elif scene_risk >= RISK_THRESHOLDS["medium"]:
        scene_risk_level = "medium"
    else:
        scene_risk_level = "low"

    return {
        "objects": scored_objects,
        "scene_risk_score": round(scene_risk, 3),
        "scene_risk_level": scene_risk_level,
        "primary_hazard": scored_objects[0] if scored_objects else None,
        "hazard_count": hazard_count,
    }
