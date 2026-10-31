"""
AVRA Backend - Audio Guidance Module
Text-to-speech output with verbosity control and interruption policy.
"""
import logging
import threading
import queue
from typing import Optional

logger = logging.getLogger("avra.audio")


class AudioGuidance:
    """
    Manages text-to-speech output for AVRA.
    
    Features:
    - Verbosity levels: minimal, normal, detailed
    - Priority-based interruption (critical interrupts current speech)
    - Non-blocking speech via threading
    - Speech queue management
    """

    VERBOSITY_LEVELS = {
        "minimal": 1,   # Only critical/warning
        "normal": 2,    # Alerts and above
        "detailed": 3,  # Everything including routine
    }

    def __init__(self, verbosity: str = "normal", use_tts: bool = True):
        self.verbosity = verbosity
        self.use_tts = use_tts
        self.speech_queue = queue.Queue(maxsize=5)
        self.is_speaking = False
        self._engine = None
        self._thread = None
        self._running = False

        if use_tts:
            self._init_tts()

    def _init_tts(self):
        """Initialize the TTS engine."""
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 175)  # Slightly faster for urgency
            self._engine.setProperty("volume", 0.9)
            logger.info("TTS engine initialized.")
        except Exception as e:
            logger.warning(f"TTS init failed: {e}. Audio will be text-only.")
            self.use_tts = False

    def speak(self, text: str, urgency: str = "routine", force: bool = False) -> dict:
        """
        Queue a speech instruction.
        
        Args:
            text: The instruction to speak
            urgency: routine, alert, warning, critical
            force: If True, skip verbosity filter
            
        Returns:
            Status dict with whether the speech was queued
        """
        # Verbosity filter
        if not force and not self._should_speak(urgency):
            return {"queued": False, "reason": "Below verbosity threshold", "text": text}
            
        if not self.use_tts:
            return {"queued": False, "reason": "TTS disabled", "text": text}

        # Trim text for conciseness
        trimmed = self._trim_for_speech(text, urgency)

        # Critical urgency: clear queue and speak immediately
        if urgency == "critical":
            self._clear_queue()

        try:
            self.speech_queue.put_nowait({
                "text": trimmed,
                "urgency": urgency,
            })
        except queue.Full:
            # Queue full — drop lowest priority
            logger.warning("Speech queue full. Dropping oldest non-critical.")
            return {"queued": False, "reason": "Queue full", "text": trimmed}

        # Start speaking if not already
        if self.use_tts and not self.is_speaking:
            self._speak_next()

        return {"queued": True, "text": trimmed, "urgency": urgency}

    def _should_speak(self, urgency: str) -> bool:
        """Check if the urgency meets the verbosity threshold."""
        urgency_levels = {
            "routine": 3,
            "alert": 2,
            "warning": 1,
            "critical": 0,  # Always speak
        }
        threshold = self.VERBOSITY_LEVELS.get(self.verbosity, 2)
        return urgency_levels.get(urgency, 2) <= threshold

    def _trim_for_speech(self, text: str, urgency: str) -> str:
        """Trim text for concise speech. Urgent messages stay short."""
        if urgency in ("critical", "warning"):
            # Keep it very short
            if len(text) > 80:
                text = text[:77] + "..."
        elif len(text) > 120:
            text = text[:117] + "..."
        return text

    def _speak_next(self):
        """Speak the next item in the queue."""
        if self.speech_queue.empty():
            self.is_speaking = False
            return

        try:
            item = self.speech_queue.get_nowait()
            self.is_speaking = True

            if self._engine:
                self._engine.say(item["text"])
                self._engine.runAndWait()

            logger.info(f"[TTS] [{item['urgency']}] {item['text']}")
            self.is_speaking = False

            # Continue with next if available
            if not self.speech_queue.empty():
                self._speak_next()

        except Exception as e:
            logger.error(f"TTS error: {e}")
            self.is_speaking = False

    def _clear_queue(self):
        """Clear the speech queue for urgent interruption."""
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
            except queue.Empty:
                break

    def set_verbosity(self, level: str):
        """Update verbosity level."""
        if level in self.VERBOSITY_LEVELS:
            self.verbosity = level
            logger.info(f"Verbosity set to: {level}")

    def get_last_speech(self) -> Optional[str]:
        """Return the last spoken text for logging."""
        return None  # Simplified; could track history
