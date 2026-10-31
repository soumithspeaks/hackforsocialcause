"""Smoke tests driven by the representative JSON scenarios in data/."""
import json
from pathlib import Path

import pytest
from PIL import Image

from backend.vlm import MockVLMEngine


SCENARIOS_PATH = Path(__file__).parent / "data" / "sample_scenes.json"
SCENARIOS = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item["name"])
def test_sample_scene_expectations(scenario):
    result = MockVLMEngine().analyze_frame(
        Image.new("RGB", (64, 64)), metadata=scenario["metadata"]
    )

    expected = scenario["expected"]
    assert result["path_status"] == expected["path_status"]
    assert len(result["objects"]) == expected["object_count"]
    for field in ("label", "direction", "distance", "in_path"):
        if field in expected:
            assert result["objects"][0][field] == expected[field]
    if "scene_type" in expected:
        assert result["scene_type"] == expected["scene_type"]
    if "urgency" in expected:
        assert result["urgency"] == expected["urgency"]
