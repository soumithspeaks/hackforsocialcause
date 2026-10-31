"""
AVRA Backend - VLM Wrapper for Qwen2.5-VL 3B
Handles model loading, structured prompting, and response parsing.
"""
import base64
import io
import json
import time
import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger("avra.vlm")

# ── Anti-hallucination constants ──────────────────────────────────
ALLOWED_LABELS = frozenset({
    "person", "vehicle", "car", "bus", "truck", "motorcycle", "bicycle",
    "pole", "chair", "table", "wall", "cone", "barrier", "bench",
    "trash_can", "trashcan", "stairs", "door", "curb", "fence",
    "sign", "tree", "dog", "animal", "pothole", "construction",
    "bollard", "pillar", "scooter", "plant",
})
MIN_CONFIDENCE = 0.40   # Drop anything below this threshold
MAX_OBJECTS = 8         # Cap per-frame to prevent noise floods

AVRA_SYSTEM_PROMPT = """You are AVRA, a strict safety-critical navigation assistant.
You are viewing a SYNTHETIC 3D simulation rendered with Three.js.
The scene contains simple geometric primitives (boxes, cylinders, spheres, cones) that represent real-world obstacles.

## ABSOLUTE RULES — VIOLATION = FAILURE
1. ONLY report objects you can CLEARLY see as distinct 3D shapes in the image.
2. If the path ahead has NO visible 3D obstacle shapes, you MUST return "objects": []. NEVER GUESS.
3. Map every detected shape to EXACTLY ONE of these labels:
   "person", "vehicle", "pole", "chair", "table", "wall", "cone",
   "barrier", "bench", "trash_can", "stairs", "sign", "door".
4. DO NOT invent labels outside that list (no "box", "cylinder", "cube", "structure", "platform", "railing", "shelf", "counter", "display", "window").
5. DO NOT describe textures, colors, lighting effects, shadows, or floors as objects.
6. DO NOT report the floor, ground plane, walls at the edges of the corridor, or the sky as obstacles.
7. Set confidence BELOW 0.5 if the shape is ambiguous. Prefer silence over wrong detections.
8. Report AT MOST 6 objects per frame. If you see more, keep only the 6 closest / highest-risk.

## DIRECTION & DISTANCE
- Directions relative to camera: "left", "ahead-left", "ahead", "ahead-right", "right".
- Distance tiers: "very_close" (<1m), "near" (1-3m), "medium" (3-6m), "far" (>6m).
- Focus on obstacles that overlap the CENTER of the image (the walking path).

## OUTPUT FORMAT — JSON ONLY, NO EXTRA TEXT
{
  "objects": [
    {
      "label": "<from allowed list>",
      "direction": "left|ahead-left|ahead|ahead-right|right",
      "distance": "very_close|near|medium|far",
      "hazard_level": "none|low|medium|high|critical",
      "in_path": true | false,
      "moving": false,
      "confidence": 0.0-1.0
    }
  ],
  "path_status": "clear|partially_blocked|blocked",
  "path_clear_direction": "left|ahead|right|none",
  "ocr_text": [],
  "scene_type": "indoor|outdoor|transition",
  "lighting": "bright|normal|dim|dark",
  "surface": "flat|uneven|stairs_up|stairs_down|ramp|unknown",
  "recommended_action": "<concise movement instruction>",
  "reasoning": "<1 sentence why>",
  "uncertainty": "low|medium|high",
  "urgency": "routine|alert|warning|critical"
}"""

AVRA_USER_PROMPT = """Analyze this synthetic 3D simulation image from a blind user's navigation perspective.
Identify ONLY clearly visible 3D obstacle shapes. If no obstacles are clearly visible, return an empty objects array.
Provide a safe movement instruction."""


class VLMEngine:
    """Wrapper for Qwen2.5-VL 3B with 4-bit quantization for local inference."""

    def __init__(self, model_name: str = "Qwen/Qwen2.5-VL-3B-Instruct", use_quantization: bool = True):
        self.model_name = model_name
        self.use_quantization = use_quantization
        self.model = None
        self.processor = None
        self.device = "cuda"
        self._loaded = False

    def load(self):
        """Load the VLM model with 4-bit quantization for RTX 3050."""
        if self._loaded:
            return

        logger.info(f"Loading VLM: {self.model_name} (quantized={self.use_quantization})")
        start = time.time()

        try:
            from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
            import torch

            if self.use_quantization:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                    self.model_name,
                    quantization_config=quantization_config,
                    device_map="auto",
                    torch_dtype=torch.float16,
                    trust_remote_code=True,
                )
            else:
                self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                    self.model_name,
                    device_map="auto",
                    torch_dtype=torch.float16,
                    trust_remote_code=True,
                )

            self.processor = AutoProcessor.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )

            self._loaded = True
            elapsed = time.time() - start
            logger.info(f"VLM loaded in {elapsed:.1f}s")

        except Exception as e:
            logger.error(f"Failed to load VLM: {e}")
            raise

    # Max resolution for VLM input — lower = faster inference
    VLM_MAX_RESOLUTION = 384

    def analyze_frame(self, image: Image.Image, custom_prompt: Optional[str] = None, metadata: Optional[dict] = None) -> dict:
        """
        Analyze a single frame and return structured scene analysis.
        
        Args:
            image: PIL Image from camera or simulation
            custom_prompt: Override the default user prompt
            
        Returns:
            Parsed JSON dict with scene analysis
        """
        if not self._loaded:
            self.load()

        # ── Downscale image for faster inference ──────────────────
        w, h = image.size
        max_dim = max(w, h)
        if max_dim > self.VLM_MAX_RESOLUTION:
            scale = self.VLM_MAX_RESOLUTION / max_dim
            new_w, new_h = int(w * scale), int(h * scale)
            image = image.resize((new_w, new_h), Image.LANCZOS)
            logger.debug(f"Resized frame {w}x{h} -> {new_w}x{new_h} for VLM")

        user_prompt = custom_prompt or AVRA_USER_PROMPT

        # Build the message in Qwen2.5-VL format
        # EXTREME OPTIMIZATION mode to force Qwen-VL to run on 4GB VRAM
        # Qwen-VL uses patches; restricting max_pixels forcefully reduces the number of image embeddings generated.
        MIN_PIXELS = 128 * 128
        MAX_PIXELS = 256 * 256
        messages = [
            {
                "role": "system",
                "content": AVRA_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image", 
                        "image": image,
                        "min_pixels": MIN_PIXELS,
                        "max_pixels": MAX_PIXELS
                    },
                    {"type": "text", "text": user_prompt},
                ],
            },
        ]

        start = time.time()

        try:
            from qwen_vl_utils import process_vision_info

            # Process the messages for the model
            text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs = process_vision_info(messages)

            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            ).to(self.model.device)

            import torch
            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=128,
                    temperature=0.1,
                    do_sample=False,
                )

            # Decode only the generated tokens
            generated_ids = output_ids[:, inputs["input_ids"].shape[1]:]
            response_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

            elapsed = time.time() - start
            logger.info(f"VLM inference took {elapsed:.2f}s")

            return self._parse_response(response_text, elapsed)

        except Exception as e:
            logger.error(f"VLM inference failed: {e}")
            return self._fallback_response(str(e))

    def _parse_response(self, text: str, inference_time: float) -> dict:
        """Parse the VLM response into structured JSON."""
        try:
            # Try to extract JSON from the response
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(text[json_start:json_end])
                parsed["_inference_time_s"] = inference_time
                parsed["_raw_response"] = text
                # ── Anti-hallucination post-processing ──
                parsed = self._filter_hallucinations(parsed)
                return parsed
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse VLM JSON response: {text[:200]}")

        # Return a structured fallback with the raw text
        return {
            "objects": [],
            "path_status": "unknown",
            "path_clear_direction": "none",
            "ocr_text": [],
            "scene_type": "unknown",
            "recommended_action": "Caution. Unable to fully analyze the scene. Proceed slowly.",
            "reasoning": "VLM response could not be parsed into structured format.",
            "uncertainty": "high",
            "urgency": "alert",
            "_inference_time_s": inference_time,
            "_raw_response": text,
            "_parse_error": True,
        }

    def _filter_hallucinations(self, parsed: dict) -> dict:
        """
        Post-processing filter to remove hallucinated objects.
        - Drops objects with labels not in ALLOWED_LABELS
        - Drops objects below MIN_CONFIDENCE
        - Caps total objects at MAX_OBJECTS (keep highest confidence)
        - Recalculates path_status if objects were removed
        """
        raw_objects = parsed.get("objects", [])
        if not raw_objects:
            return parsed

        filtered = []
        dropped = []
        for obj in raw_objects:
            label = obj.get("label", "").lower().strip()
            confidence = obj.get("confidence", 0.0)

            # Normalize common label variants
            label = self._normalize_label(label)
            obj["label"] = label

            if label not in ALLOWED_LABELS:
                dropped.append(f"{obj.get('label', '?')} (unknown label)")
                continue
            if confidence < MIN_CONFIDENCE:
                dropped.append(f"{label} (confidence {confidence:.2f} < {MIN_CONFIDENCE})")
                continue
            filtered.append(obj)

        # Sort by confidence descending, cap at MAX_OBJECTS
        filtered.sort(key=lambda o: o.get("confidence", 0), reverse=True)
        if len(filtered) > MAX_OBJECTS:
            dropped.extend(
                f"{o['label']} (over cap)" for o in filtered[MAX_OBJECTS:]
            )
            filtered = filtered[:MAX_OBJECTS]

        if dropped:
            logger.info(f"Hallucination filter dropped {len(dropped)} objects: {dropped}")

        parsed["objects"] = filtered
        parsed["_dropped_objects"] = dropped

        # Recalculate path_status if all path-blocking objects were removed
        if not any(o.get("in_path") for o in filtered):
            if parsed.get("path_status") in ("blocked", "partially_blocked"):
                parsed["path_status"] = "clear"
                parsed["path_clear_direction"] = "ahead"

        return parsed

    @staticmethod
    def _normalize_label(label: str) -> str:
        """Map common VLM label variants to our canonical labels."""
        LABEL_MAP = {
            "car": "vehicle",
            "automobile": "vehicle",
            "sedan": "vehicle",
            "suv": "vehicle",
            "bus": "vehicle",
            "truck": "vehicle",
            "van": "vehicle",
            "motorcycle": "vehicle",
            "traffic light": "pole",
            "traffic_light": "pole",
            "lamppost": "pole",
            "lamp_post": "pole",
            "light pole": "pole",
            "street light": "pole",
            "street_light": "pole",
            "stool": "chair",
            "sofa": "chair",
            "couch": "chair",
            "armchair": "chair",
            "desk": "table",
            "bin": "trash_can",
            "garbage": "trash_can",
            "garbage can": "trash_can",
            "garbage_can": "trash_can",
            "dustbin": "trash_can",
            "waste bin": "trash_can",
            "traffic cone": "cone",
            "traffic_cone": "cone",
            "pylon": "cone",
            "railing": "barrier",
            "guardrail": "barrier",
            "handrail": "barrier",
            "staircase": "stairs",
            "stairway": "stairs",
            "step": "stairs",
            "steps": "stairs",
            "pedestrian": "person",
            "man": "person",
            "woman": "person",
            "child": "person",
            "human": "person",
            # Things that are NOT obstacles — map to something we can filter
            "floor": "_floor",
            "ground": "_floor",
            "ceiling": "_ceiling",
            "sky": "_sky",
            "road": "_floor",
            "sidewalk": "_floor",
            "pavement": "_floor",
            "shadow": "_shadow",
            "light": "_light",
            "reflection": "_reflection",
        }
        return LABEL_MAP.get(label, label)

    def _fallback_response(self, error: str) -> dict:
        """Return a safe fallback when VLM is unavailable."""
        return {
            "objects": [],
            "path_status": "unknown",
            "path_clear_direction": "none",
            "ocr_text": [],
            "scene_type": "unknown",
            "recommended_action": "Stop. Navigation system error. Use caution.",
            "reasoning": f"VLM error: {error}",
            "uncertainty": "high",
            "urgency": "critical",
            "_inference_time_s": 0,
            "_error": error,
        }

    def is_loaded(self) -> bool:
        return self._loaded


class MockVLMEngine:
    """
    Scene-aware mock VLM engine for testing and simulation without GPU.
    Uses actual obstacle metadata (positions, labels) and camera state
    from the Three.js simulation to produce geometrically accurate detections.
    """

    import math as _math

    # Camera FOV half-angle (degrees). Three.js uses 75° FOV → ±37.5°
    _HALF_FOV_DEG = 37.5

    # Distance thresholds (metres in Three.js units)
    _DIST_THRESHOLDS = {
        "very_close": 3.0,
        "near": 6.0,
        "medium": 12.0,
        # anything beyond 12 → "far"
    }

    # Central walking corridor width (metres either side of camera forward axis)
    _PATH_HALF_WIDTH = 1.5

    def __init__(self):
        self._loaded = True

    def load(self):
        pass

    # ── Public API ────────────────────────────────────────────────
    def analyze_frame(
        self,
        image: Image.Image,
        custom_prompt: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Generate a mock analysis from scene obstacle metadata.

        If metadata contains `scene_obstacles` and `camera_position`,
        we compute directions/distances geometrically.  Otherwise fall
        back to a simple "path clear" response.
        """
        metadata = metadata or {}
        obstacles = metadata.get("scene_obstacles", [])
        cam_pos = metadata.get("camera_position", {})
        cam_rot_y = metadata.get("camera_rotation_y", 0.0)
        scene_name = metadata.get("scene", "indoor")

        # No obstacle data → return safe fallback
        if not obstacles or not cam_pos:
            return self._clear_scene_response(scene_name)

        cx = cam_pos.get("x", 0.0)
        cz = cam_pos.get("z", 0.0)

        detected = []
        for obs in obstacles:
            pos = obs.get("position", {})
            ox, oz = pos.get("x", 0.0), pos.get("z", 0.0)

            # Vector from camera to obstacle
            dx = ox - cx
            dz = oz - cz

            # Distance
            dist = self._math.sqrt(dx * dx + dz * dz)
            if dist < 0.3:
                continue  # ignore objects we're standing on

            # Angle relative to camera forward direction (Three.js: forward = -Z)
            # cam_rot_y: yaw in radians, 0 = looking down -Z
            fwd_x = -self._math.sin(cam_rot_y)
            fwd_z = -self._math.cos(cam_rot_y)

            # Signed angle between forward vector and obstacle vector
            dot = fwd_x * dx + fwd_z * dz
            cross = fwd_x * dz - fwd_z * dx  # positive → obstacle to the right
            angle_deg = self._math.degrees(self._math.atan2(cross, dot))

            # FOV cull — only keep obstacles within ±60° (generous margin)
            if abs(angle_deg) > 60:
                continue

            # Skip obstacles behind the camera (dot < 0 means behind)
            if dot < 0:
                continue

            # Ignore very far objects
            if dist > 20:
                continue

            # Compute lateral offset from walking path centre-line
            # Project obstacle onto the camera's right vector
            right_x = -fwd_z  # perpendicular to forward
            right_z = fwd_x
            lateral = dx * right_x + dz * right_z
            in_path = abs(lateral) < self._PATH_HALF_WIDTH and dot > 0

            direction = self._angle_to_direction(angle_deg)
            distance_tier = self._dist_to_tier(dist)
            label = obs.get("label", "obstacle")
            hazard_src = obs.get("hazard", "low")

            # Compute hazard_level from combo of source hazard + distance + in_path
            hazard_level = self._compute_hazard_level(hazard_src, distance_tier, in_path)

            # Confidence: closer + in-path → higher confidence
            base_conf = 0.92 if dist < 6 else (0.82 if dist < 12 else 0.70)
            confidence = round(min(0.98, base_conf + (0.05 if in_path else 0.0)), 2)

            # Map euclidean distance to human steps (avg step ~ 0.75m)
            steps = max(1, int(round(dist / 0.75)))

            detected.append({
                "label": label,
                "direction": direction,
                "distance": distance_tier,
                "steps": steps,
                "hazard_level": hazard_level,
                "in_path": in_path,
                "moving": label == "person",  # people can move
                "confidence": confidence,
            })

        # Sort by distance (closest first) and cap at 8
        tier_order = {"very_close": 0, "near": 1, "medium": 2, "far": 3}
        detected.sort(key=lambda o: tier_order.get(o["distance"], 3))
        detected = detected[:8]

        # ── Path analysis ─────────────────────────────────────────
        in_path_objects = [o for o in detected if o["in_path"]]
        high_in_path = [o for o in in_path_objects if o["hazard_level"] in ("high", "critical")]
        close_high = [o for o in high_in_path if o["distance"] in ("very_close", "near")]

        if close_high:
            path_status = "blocked"
        elif high_in_path:
            path_status = "partially_blocked"
        elif in_path_objects:
            path_status = "partially_blocked"
        else:
            path_status = "clear"

        # Find safest direction
        dir_scores = {"left": 0, "ahead-left": 0, "ahead": 0, "ahead-right": 0, "right": 0}
        hazard_weights = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        for o in detected:
            d = o["direction"]
            if d in dir_scores:
                dir_scores[d] += hazard_weights.get(o["hazard_level"], 1)
        safest = min(dir_scores, key=dir_scores.get)
        path_clear_direction = safest if path_status != "clear" else "ahead"

        # ── Action & urgency ──────────────────────────────────────
        action, urgency = self._generate_action(detected, path_status, safest)

        # ── Scene metadata ────────────────────────────────────────
        is_outdoor = "outdoor" in scene_name or "city" in scene_name or "street" in scene_name
        scene_type = "outdoor" if is_outdoor else "indoor"

        return {
            "objects": detected,
            "path_status": path_status,
            "path_clear_direction": path_clear_direction,
            "ocr_text": [],
            "scene_type": scene_type,
            "lighting": "bright" if is_outdoor else "normal",
            "surface": "flat",
            "recommended_action": action,
            "reasoning": self._build_reasoning(detected, path_status),
            "uncertainty": "low",
            "urgency": urgency,
            "_inference_time_s": 0.02,
            "_mock": True,
        }

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _angle_to_direction(angle_deg: float) -> str:
        """Map signed angle (negative=left, positive=right) to direction label."""
        if angle_deg < -30:
            return "left"
        elif angle_deg < -10:
            return "ahead-left"
        elif angle_deg <= 10:
            return "ahead"
        elif angle_deg <= 30:
            return "ahead-right"
        else:
            return "right"

    def _dist_to_tier(self, dist: float) -> str:
        if dist < self._DIST_THRESHOLDS["very_close"]:
            return "very_close"
        elif dist < self._DIST_THRESHOLDS["near"]:
            return "near"
        elif dist < self._DIST_THRESHOLDS["medium"]:
            return "medium"
        return "far"

    @staticmethod
    def _compute_hazard_level(hazard_src: str, distance: str, in_path: bool) -> str:
        """Combine source hazard with proximity and path intersection."""
        base = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(hazard_src, 2)
        if in_path:
            base += 1
        if distance in ("very_close", "near"):
            base += 1
        if base >= 4:
            return "critical"
        elif base >= 3:
            return "high"
        elif base >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _generate_action(objects: list, path_status: str, safest: str) -> tuple:
        """Generate recommended_action and urgency."""
        if not objects:
            return "Path is clear. Continue ahead.", "routine"

        in_path_high = [o for o in objects if o["in_path"] and o["hazard_level"] in ("high", "critical")]

        if path_status == "blocked" and in_path_high:
            primary = in_path_high[0]
            dist = f"in {primary['steps']} step{'s' if primary['steps'] != 1 else ''}"
            if primary["distance"] == "very_close":
                return f"Stop! {primary['label'].title()} {dist}. Move {safest}.", "critical"
            return f"Stop. {primary['label'].title()} {primary['direction']}, {dist}. Veer {safest}.", "warning"

        if path_status == "partially_blocked":
            blocker = next((o for o in objects if o["in_path"]), objects[0])
            dist = f"in {blocker['steps']} step{'s' if blocker['steps'] != 1 else ''}"
            return f"Caution. {blocker['label'].title()} {dist}. Go {safest}.", "alert"

        # Objects nearby but path clear
        closest = objects[0]
        return f"Clear. {closest['label'].title()} to the {closest['direction']}.", "routine"

    @staticmethod
    def _build_reasoning(objects: list, path_status: str) -> str:
        if not objects:
            return "Clear path."
        labels = ", ".join(set(o["label"] for o in objects))
        return f"{len(objects)} object(s). {labels}."

    @staticmethod
    def _clear_scene_response(scene_name: str) -> dict:
        is_outdoor = "outdoor" in scene_name or "city" in scene_name
        return {
            "objects": [],
            "path_status": "clear",
            "path_clear_direction": "ahead",
            "ocr_text": [],
            "scene_type": "outdoor" if is_outdoor else "indoor",
            "lighting": "bright" if is_outdoor else "normal",
            "surface": "flat",
            "recommended_action": "Path is clear. Continue ahead.",
            "reasoning": "No obstacles detected in field of view. Path is clear.",
            "uncertainty": "low",
            "urgency": "routine",
            "_inference_time_s": 0.01,
            "_mock": True,
        }

    def is_loaded(self) -> bool:
        return True
