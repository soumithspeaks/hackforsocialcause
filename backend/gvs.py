"""
AVRA Backend - GVS (Galvanic Vestibular Stimulation) Command Generator
Translates spatial reasoning into vestibular stimulation parameters.

In simulation mode, outputs visual commands.
In hardware mode, sends signals via Serial/BLE to a GVS device.
"""
import math
import logging
from typing import Dict, Optional, List
from enum import Enum

logger = logging.getLogger("avra.gvs")


class GVSMode(str, Enum):
    SIMULATION = "simulation"
    HARDWARE = "hardware"


class StimulationType(str, Enum):
    NUDGE = "nudge"           # Gentle directional guidance
    REDIRECT = "redirect"     # Moderate redirection
    STOP = "stop"             # Strong bilateral = stop/balance reset
    URGENT = "urgent"         # Sharp pulse for immediate danger


# ── Direction to angle mapping ─────────────────────────────────────
# 0° = straight ahead, negative = left, positive = right
DIRECTION_ANGLES = {
    "left": -90.0,
    "ahead-left": -45.0,
    "ahead": 0.0,
    "ahead-right": 45.0,
    "right": 90.0,
}

# ── Risk to intensity mapping ─────────────────────────────────────
RISK_INTENSITY = {
    "low": 0.15,
    "medium": 0.35,
    "high": 0.65,
    "critical": 0.90,
}


class GVSController:
    """
    Generates GVS stimulation commands from AVRA spatial/risk data.
    
    The GVS system works by sending small electrical currents to the
    vestibular nerve behind the ears, which the brain interprets as
    a shift in balance, causing the body to naturally lean/step in
    a compensating direction.
    
    LEFT electrode  → activates right-leaning response (body moves right)
    RIGHT electrode → activates left-leaning response (body moves left)
    BILATERAL       → stop/balance disruption signal
    """

    def __init__(self, mode: GVSMode = GVSMode.SIMULATION, max_intensity: float = 1.0):
        self.mode = mode
        self.max_intensity = max_intensity
        self.last_command = None
        self.command_history: List[dict] = []
        # Hardware connection (stub for future)
        self._hw_connection = None

    def generate_command(self, risk_data: dict, path_analysis: dict, verified_action: dict) -> dict:
        """
        Generate a GVS command from the AVRA pipeline output.
        
        The command specifies:
        - direction_angle: which way the body should move (negative=left, positive=right)
        - intensity: strength of stimulation (0-1)
        - duration_ms: how long to apply the stimulus
        - stimulation_type: nudge, redirect, stop, or urgent
        - channels: left, right, or both electrode activation
        """
        scene_risk = risk_data.get("scene_risk_level", "low")
        primary_hazard = risk_data.get("primary_hazard")
        urgency = verified_action.get("urgency", "routine")
        safest_direction = path_analysis.get("safest_direction", "ahead")
        path_status = path_analysis.get("path_status", "clear")

        # ── No stimulation needed ──────────────────────────────────
        if scene_risk == "low" and path_status == "clear":
            cmd = self._no_stimulation()
            self._record(cmd)
            return cmd

        # ── Determine where to guide the user ─────────────────────
        if primary_hazard:
            hazard_direction = primary_hazard.get("direction", "ahead")
            hazard_risk = primary_hazard.get("risk_level", "low")
            
            # Guide AWAY from the hazard (opposite direction)
            guide_direction = self._opposite_direction(hazard_direction)
            intensity = RISK_INTENSITY.get(hazard_risk, 0.3)
            
            # Determine stimulation type based on urgency
            if urgency == "critical" or hazard_risk == "critical":
                stim_type = StimulationType.URGENT
                intensity = min(self.max_intensity, intensity * 1.5)
                duration_ms = 400
            elif path_status == "blocked":
                stim_type = StimulationType.STOP
                intensity = min(self.max_intensity, 0.7)
                duration_ms = 500
            elif hazard_risk == "high":
                stim_type = StimulationType.REDIRECT
                duration_ms = 350
            else:
                stim_type = StimulationType.NUDGE
                duration_ms = 250
        else:
            # No specific hazard but path not fully clear
            guide_direction = safest_direction
            intensity = 0.2
            stim_type = StimulationType.NUDGE
            duration_ms = 200

        # Convert direction to angle
        direction_angle = DIRECTION_ANGLES.get(guide_direction, 0.0)

        # Determine electrode channels
        if stim_type == StimulationType.STOP:
            channels = "bilateral"
        elif direction_angle < 0:
            channels = "right"   # Stimulate right → body goes left
        elif direction_angle > 0:
            channels = "left"    # Stimulate left → body goes right
        else:
            channels = "bilateral"

        cmd = {
            "active": True,
            "direction_angle": direction_angle,
            "guide_direction": guide_direction,
            "intensity": round(min(self.max_intensity, intensity), 3),
            "duration_ms": duration_ms,
            "stimulation_type": stim_type.value,
            "channels": channels,
            "reason": f"Guiding {guide_direction} due to {stim_type.value}: {primary_hazard.get('label', 'hazard') if primary_hazard else 'path condition'}",
            "hazard_source": primary_hazard.get("label") if primary_hazard else None,
            "hazard_direction": primary_hazard.get("direction") if primary_hazard else None,
        }

        # Apply to hardware if connected
        if self.mode == GVSMode.HARDWARE:
            self._send_to_hardware(cmd)

        self._record(cmd)
        return cmd

    def _opposite_direction(self, hazard_direction: str) -> str:
        """Return the opposite safe direction from a hazard."""
        opposites = {
            "left": "right",
            "ahead-left": "right",
            "ahead": "right",  # Default: veer right when ahead is blocked
            "ahead-right": "left",
            "right": "left",
        }
        return opposites.get(hazard_direction, "right")

    def _no_stimulation(self) -> dict:
        """Return a null GVS command (no stimulation needed)."""
        return {
            "active": False,
            "direction_angle": 0.0,
            "guide_direction": "ahead",
            "intensity": 0.0,
            "duration_ms": 0,
            "stimulation_type": "none",
            "channels": "none",
            "reason": "Path clear, no stimulation needed.",
            "hazard_source": None,
            "hazard_direction": None,
        }

    def _record(self, cmd: dict):
        """Record command to history for analysis."""
        self.last_command = cmd
        self.command_history.append(cmd)
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]

    def _send_to_hardware(self, cmd: dict):
        """
        Send GVS command to physical hardware.
        STUB: Implement serial/BLE communication for real device.
        """
        logger.info(f"[GVS HW] {cmd['stimulation_type']}: "
                     f"dir={cmd['direction_angle']}°, "
                     f"intensity={cmd['intensity']}, "
                     f"duration={cmd['duration_ms']}ms, "
                     f"channels={cmd['channels']}")
        # TODO: Serial/BLE implementation
        # import serial
        # packet = self._encode_packet(cmd)
        # self._hw_connection.write(packet)

    def get_visualization_data(self) -> dict:
        """
        Return data formatted for the GVS visualization dashboard.
        Used by the simulation frontend.
        """
        if not self.last_command or not self.last_command.get("active"):
            return {
                "active": False,
                "arrow_angle": 0,
                "arrow_strength": 0,
                "pulse_animation": False,
                "left_electrode": 0,
                "right_electrode": 0,
                "body_lean_angle": 0,
                "status_text": "Idle - No stimulation",
                "status_color": "#4CAF50",  # Green
            }

        cmd = self.last_command
        intensity = cmd["intensity"]
        angle = cmd["direction_angle"]

        # Electrode activation levels
        if cmd["channels"] == "bilateral":
            left_e = intensity * 0.5
            right_e = intensity * 0.5
        elif cmd["channels"] == "left":
            left_e = intensity
            right_e = 0
        else:
            left_e = 0
            right_e = intensity

        # Color based on stimulation type
        colors = {
            "nudge": "#FFC107",     # Amber
            "redirect": "#FF9800",   # Orange
            "stop": "#F44336",       # Red
            "urgent": "#D32F2F",     # Dark Red
        }

        return {
            "active": True,
            "arrow_angle": angle,
            "arrow_strength": intensity,
            "pulse_animation": cmd["stimulation_type"] in ("urgent", "stop"),
            "left_electrode": round(left_e, 3),
            "right_electrode": round(right_e, 3),
            "body_lean_angle": angle * intensity * 0.3,  # Simulated lean
            "status_text": f"{cmd['stimulation_type'].title()}: {cmd['guide_direction']} ({intensity:.0%})",
            "status_color": colors.get(cmd["stimulation_type"], "#FFC107"),
            "duration_ms": cmd["duration_ms"],
            "reason": cmd["reason"],
        }
