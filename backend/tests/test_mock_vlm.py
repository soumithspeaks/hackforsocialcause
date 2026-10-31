"""
Tests for AVRA Scene-Aware MockVLMEngine.
Verifies that the mock VLM produces accurate direction/distance/path analysis
from scene obstacle metadata + camera state.
"""
import math
import pytest
from PIL import Image
from backend.vlm import MockVLMEngine


@pytest.fixture
def vlm():
    return MockVLMEngine()


@pytest.fixture
def dummy_image():
    """1x1 black image — content doesn't matter for mock VLM."""
    return Image.new("RGB", (64, 64), color=(0, 0, 0))


# ── Helpers ────────────────────────────────────────────────────────

def make_metadata(
    cam_x=0, cam_z=2, cam_rot_y=0, obstacles=None, scene="indoor"
):
    """Build a metadata dict mimicking what the frontend sends."""
    return {
        "source": "simulation",
        "scene": scene,
        "camera_position": {"x": cam_x, "y": 1.6, "z": cam_z},
        "camera_rotation_y": cam_rot_y,
        "scene_obstacles": obstacles or [],
    }


# ══════════════════════════════════════════════════════════════════
# Test 1: No obstacles → clear path
# ══════════════════════════════════════════════════════════════════

def test_clear_path_no_obstacles(vlm, dummy_image):
    meta = make_metadata(obstacles=[])
    result = vlm.analyze_frame(dummy_image, metadata=meta)

    assert result["path_status"] == "clear"
    assert result["objects"] == []
    assert result["urgency"] == "routine"
    assert "clear" in result["recommended_action"].lower()


# ══════════════════════════════════════════════════════════════════
# Test 2: Obstacle directly ahead, very close → blocked
# ══════════════════════════════════════════════════════════════════

def test_obstacle_directly_ahead_very_close(vlm, dummy_image):
    obstacles = [
        {"label": "pole", "hazard": "high", "position": {"x": 0, "y": 0, "z": 0}},
    ]
    # Camera at z=2 looking down -Z → pole at z=0 is 2 units ahead (very_close)
    meta = make_metadata(cam_x=0, cam_z=2, cam_rot_y=0, obstacles=obstacles)
    result = vlm.analyze_frame(dummy_image, metadata=meta)

    assert len(result["objects"]) == 1
    obj = result["objects"][0]
    assert obj["label"] == "pole"
    assert obj["direction"] == "ahead"
    assert obj["distance"] == "very_close"
    assert obj["in_path"] is True
    assert result["path_status"] in ("blocked", "partially_blocked")


# ══════════════════════════════════════════════════════════════════
# Test 3: Obstacle to the right, medium distance → not in path
# ══════════════════════════════════════════════════════════════════

def test_obstacle_to_right(vlm, dummy_image):
    obstacles = [
        {"label": "bench", "hazard": "low", "position": {"x": 5, "y": 0, "z": -5}},
    ]
    # Camera at origin looking -Z, bench is to the right and ahead
    meta = make_metadata(cam_x=0, cam_z=0, cam_rot_y=0, obstacles=obstacles)
    result = vlm.analyze_frame(dummy_image, metadata=meta)

    assert len(result["objects"]) == 1
    obj = result["objects"][0]
    assert obj["label"] == "bench"
    assert obj["direction"] in ("right", "ahead-right")
    assert obj["in_path"] is False
    assert result["path_status"] == "clear"


# ══════════════════════════════════════════════════════════════════
# Test 4: Obstacle behind camera → should be culled
# ══════════════════════════════════════════════════════════════════

def test_obstacle_behind_camera_culled(vlm, dummy_image):
    obstacles = [
        {"label": "chair", "hazard": "medium", "position": {"x": 0, "y": 0, "z": 5}},
    ]
    # Camera at z=2 looking -Z, chair at z=5 is behind
    meta = make_metadata(cam_x=0, cam_z=2, cam_rot_y=0, obstacles=obstacles)
    result = vlm.analyze_frame(dummy_image, metadata=meta)

    assert len(result["objects"]) == 0
    assert result["path_status"] == "clear"


# ══════════════════════════════════════════════════════════════════
# Test 5: Multiple obstacles → correct sorting and capping
# ══════════════════════════════════════════════════════════════════

def test_multiple_obstacles_sorted(vlm, dummy_image):
    obstacles = [
        {"label": "person", "hazard": "medium", "position": {"x": -1, "y": 0, "z": -8}},
        {"label": "pole", "hazard": "high", "position": {"x": 0.5, "y": 0, "z": -2}},
        {"label": "vehicle", "hazard": "critical", "position": {"x": 4, "y": 0, "z": -5}},
    ]
    meta = make_metadata(cam_x=0, cam_z=0, cam_rot_y=0, obstacles=obstacles)
    result = vlm.analyze_frame(dummy_image, metadata=meta)

    # Should detect all 3 and sort by closest first
    assert len(result["objects"]) >= 2
    # Closest object (pole at dist=2) should be first
    assert result["objects"][0]["label"] == "pole"


# ══════════════════════════════════════════════════════════════════
# Test 6: Camera rotated → FOV cull works correctly
# ══════════════════════════════════════════════════════════════════

def test_camera_rotated_fov_cull(vlm, dummy_image):
    obstacles = [
        # Object directly ahead when facing -Z, but camera is rotated 90° to the right
        {"label": "pole", "hazard": "high", "position": {"x": 0, "y": 0, "z": -5}},
        # Object to the right of -Z axis, which is ahead when camera rotated right
        {"label": "chair", "hazard": "medium", "position": {"x": -5, "y": 0, "z": 0}},
    ]
    # Camera rotated 90° right (pi/2) → now looking along -X
    meta = make_metadata(cam_x=0, cam_z=0, cam_rot_y=math.pi / 2, obstacles=obstacles)
    result = vlm.analyze_frame(dummy_image, metadata=meta)

    labels = [o["label"] for o in result["objects"]]
    # After rotating, the chair at x=-5 is now ahead, pole at z=-5 is to the side
    assert "chair" in labels


# ══════════════════════════════════════════════════════════════════
# Test 7: Outdoor scene detection
# ══════════════════════════════════════════════════════════════════

def test_outdoor_scene_type(vlm, dummy_image):
    meta = make_metadata(scene="realistic_outdoor", obstacles=[])
    result = vlm.analyze_frame(dummy_image, metadata=meta)
    assert result["scene_type"] == "outdoor"


# ══════════════════════════════════════════════════════════════════
# Test 8: No metadata at all → graceful fallback
# ══════════════════════════════════════════════════════════════════

def test_no_metadata_fallback(vlm, dummy_image):
    result = vlm.analyze_frame(dummy_image, metadata=None)
    assert result["path_status"] == "clear"
    assert result["objects"] == []
    assert result["urgency"] == "routine"


# ══════════════════════════════════════════════════════════════════
# Test 9: Vehicle in path → critical urgency
# ══════════════════════════════════════════════════════════════════

def test_vehicle_in_path_critical(vlm, dummy_image):
    obstacles = [
        {"label": "vehicle", "hazard": "critical", "position": {"x": 0, "y": 0, "z": -1}},
    ]
    # Very close, in path
    meta = make_metadata(cam_x=0, cam_z=0, cam_rot_y=0, obstacles=obstacles)
    result = vlm.analyze_frame(dummy_image, metadata=meta)

    assert len(result["objects"]) == 1
    obj = result["objects"][0]
    assert obj["label"] == "vehicle"
    assert obj["in_path"] is True
    assert obj["hazard_level"] == "critical"
    assert result["path_status"] == "blocked"
    assert result["urgency"] in ("critical", "warning")
    assert "stop" in result["recommended_action"].lower() or "STOP" in result["recommended_action"]
