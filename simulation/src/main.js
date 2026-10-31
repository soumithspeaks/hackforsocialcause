/**
 * AVRA Simulation — Main Entry Point
 * Connects Three.js simulation, WebSocket backend, and all UI panels.
 */
import { SceneManager } from './simulation/Scene.js';

// ══════════════════════════════════════════════════════════════════
// State
// ══════════════════════════════════════════════════════════════════
let sceneManager = null;
let ws = null;
let wsConnected = false;
let frameInterval = null;
let fps = 0;
let fpsFrames = 0;
let lastFpsTime = performance.now();
let sendFps = 2; // frames per second to backend
let currentScene = 'realistic_city';
let lastResult = null;
let logEntries = [];

// ══════════════════════════════════════════════════════════════════
// Initialization
// ══════════════════════════════════════════════════════════════════
window.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('simulation-canvas');
    sceneManager = new SceneManager(canvas);
    sceneManager.loadScene(currentScene);

    // Start render loop
    requestAnimationFrame(renderLoop);

    // Connect to backend
    connectWebSocket();

    // UI event listeners
    setupUIListeners();

    // Hide loading screen after a short delay
    setTimeout(() => {
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('app').classList.remove('hidden');
        sceneManager._onResize();
        updateLoadStatus('Ready');
    }, 1500);
});

// ══════════════════════════════════════════════════════════════════
// Render Loop
// ══════════════════════════════════════════════════════════════════
function renderLoop() {
    requestAnimationFrame(renderLoop);
    if (sceneManager) {
        sceneManager.update();
    }

    // FPS counter
    fpsFrames++;
    const now = performance.now();
    if (now - lastFpsTime >= 1000) {
        fps = fpsFrames;
        fpsFrames = 0;
        lastFpsTime = now;
        document.getElementById('fps-counter').textContent = fps;
    }
}

// ══════════════════════════════════════════════════════════════════
// WebSocket Connection
// ══════════════════════════════════════════════════════════════════
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/frames`;

    updateConnectionStatus('connecting');

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            wsConnected = true;
            updateConnectionStatus('connected');
            addLog('System connected to AVRA backend', 'info');
            startFrameSending();
        };

        ws.onmessage = (event) => {
            try {
                const result = JSON.parse(event.data);
                lastResult = result;
                updateUI(result);
            } catch (e) {
                console.error('Failed to parse result:', e);
            }
        };

        ws.onclose = () => {
            wsConnected = false;
            updateConnectionStatus('disconnected');
            addLog('Disconnected from backend', 'warning');
            stopFrameSending();
            // Retry in 3 seconds
            setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            updateConnectionStatus('error');
            // Start demo mode with mock data
            startDemoMode();
        };
    } catch (e) {
        console.error('WebSocket connection failed:', e);
        startDemoMode();
    }
}

function startFrameSending() {
    stopFrameSending();
    frameInterval = setInterval(() => {
        if (!wsConnected || !sceneManager || ws.readyState !== WebSocket.OPEN) return;

        const dataUrl = sceneManager.captureFrame();
        if (!dataUrl) return;

        // Extract base64 data (remove "data:image/jpeg;base64," prefix)
        const base64 = dataUrl.split(',')[1];

        // Gather camera state and scene obstacle data for backend
        const camState = sceneManager.getCameraState();
        const obstacleData = sceneManager.obstacles.map(o => ({
            label: o.label,
            hazard: o.hazard,
            position: { x: o.position.x, y: o.position.y, z: o.position.z },
        }));

        ws.send(JSON.stringify({
            image_base64: base64,
            metadata: {
                source: 'simulation',
                scene: currentScene,
                timestamp: Date.now(),
                camera_position: camState.position,
                camera_rotation_y: camState.rotationY,
                scene_obstacles: obstacleData,
            },
        }));
    }, 1000 / sendFps);
}

function stopFrameSending() {
    if (frameInterval) {
        clearInterval(frameInterval);
        frameInterval = null;
    }
}

// ══════════════════════════════════════════════════════════════════
// Demo Mode (when backend is not available)
// ══════════════════════════════════════════════════════════════════
function startDemoMode() {
    addLog('Backend unavailable — running in demo mode', 'warning');
    updateConnectionStatus('demo');

    // Generate mock data periodically
    setInterval(() => {
        const mockResult = generateMockResult();
        lastResult = mockResult;
        updateUI(mockResult);
    }, 1000 / sendFps);
}

function generateMockResult() {
    const scenarios = [
        {
            objects: [
                { label: 'pole', direction: 'ahead-left', distance: 'near', risk_level: 'high', risk_score: 0.72, in_path: true, moving: false, confidence: 0.91 },
                { label: 'person', direction: 'right', distance: 'medium', risk_level: 'low', risk_score: 0.18, in_path: false, moving: true, confidence: 0.85 },
            ],
            path_status: 'partially_blocked',
            safest_direction: 'right',
            scene_risk_score: 0.72,
            scene_risk_level: 'high',
            action: 'Pole ahead-left, near. Veer slightly right.',
            urgency: 'warning',
            reasoning_mode: 'verify',
            router_reason: 'High risk with obstacle in path. Verifying.',
            gvs: { active: true, arrow_angle: 45, arrow_strength: 0.65, pulse_animation: false, left_electrode: 0.65, right_electrode: 0, body_lean_angle: 8.8, status_text: 'Redirect: right (65%)', status_color: '#FF9800', duration_ms: 350, reason: 'Guiding right due to redirect: pole' },
            scene_type: 'indoor',
            processing_time_ms: 142,
        },
        {
            objects: [],
            path_status: 'clear',
            safest_direction: 'ahead',
            scene_risk_score: 0.0,
            scene_risk_level: 'low',
            action: 'Path is clear. Continue ahead.',
            urgency: 'routine',
            reasoning_mode: 'direct',
            router_reason: 'Low risk, stable scene. Direct instruction.',
            gvs: { active: false, arrow_angle: 0, arrow_strength: 0, pulse_animation: false, left_electrode: 0, right_electrode: 0, body_lean_angle: 0, status_text: 'Idle - No stimulation', status_color: '#4CAF50' },
            scene_type: 'indoor',
            processing_time_ms: 48,
        },
        {
            objects: [
                { label: 'chair', direction: 'ahead', distance: 'near', risk_level: 'medium', risk_score: 0.45, in_path: true, moving: false, confidence: 0.88 },
                { label: 'table', direction: 'ahead-right', distance: 'medium', risk_level: 'low', risk_score: 0.21, in_path: false, moving: false, confidence: 0.82 },
            ],
            path_status: 'partially_blocked',
            safest_direction: 'left',
            scene_risk_score: 0.45,
            scene_risk_level: 'medium',
            action: 'Chair ahead. Step left to navigate around it.',
            urgency: 'alert',
            reasoning_mode: 'verify',
            router_reason: 'Medium risk with new detections. Verifying.',
            gvs: { active: true, arrow_angle: -45, arrow_strength: 0.35, pulse_animation: false, left_electrode: 0, right_electrode: 0.35, body_lean_angle: -4.7, status_text: 'Nudge: left (35%)', status_color: '#FFC107', duration_ms: 250, reason: 'Guiding left due to nudge: chair' },
            scene_type: 'indoor',
            processing_time_ms: 95,
        },
        {
            objects: [
                { label: 'car', direction: 'ahead', distance: 'near', risk_level: 'critical', risk_score: 0.95, in_path: true, moving: true, confidence: 0.96 },
            ],
            path_status: 'blocked',
            safest_direction: 'right',
            scene_risk_score: 0.95,
            scene_risk_level: 'critical',
            action: 'STOP! Vehicle ahead, very close. Do not proceed.',
            urgency: 'critical',
            reasoning_mode: 'deep',
            router_reason: 'Critical risk with unstable scene. Full analysis required.',
            gvs: { active: true, arrow_angle: 0, arrow_strength: 0.9, pulse_animation: true, left_electrode: 0.45, right_electrode: 0.45, body_lean_angle: 0, status_text: 'Urgent: ahead (90%)', status_color: '#D32F2F', duration_ms: 400, reason: 'Guiding ahead due to urgent: car' },
            scene_type: 'outdoor',
            processing_time_ms: 285,
        },
    ];

    const scenario = scenarios[Math.floor(Math.random() * scenarios.length)];
    return {
        frame_id: Math.floor(Math.random() * 1000),
        ...scenario,
        audio_spoken: Math.random() > 0.5,
        scene_stable: Math.random() > 0.3,
        tracked_objects: scenario.objects.length + Math.floor(Math.random() * 3),
    };
}

// ══════════════════════════════════════════════════════════════════
// UI Updates
// ══════════════════════════════════════════════════════════════════
function updateUI(result) {
    if (!result) return;

    updateLatency(result.processing_time_ms);
    updateRiskPanel(result);
    updateObjectsPanel(result.objects || []);
    updateGVSPanel(result.gvs || {});
    updateRouterPanel(result);
    updateHUD(result);
    updateActionBar(result);

    // Pass the GVS packet to the scene engine for physical pull effect
    if (sceneManager) {
        sceneManager.applyGVS(result.gvs || null);
    }

    // ── Real-time Audio Feedback System ─────────────────────────
    handleRealtimeAudio(result);

    if (result.gvs && result.gvs.active) {
        addLog(`⚡ GVS: ${result.gvs.status_text}`, 'gvs');
    }
}

// ══════════════════════════════════════════════════════════════════
// Real-Time Audio Feedback Engine
// ══════════════════════════════════════════════════════════════════
let _audioCtx = null;
let _lastSpokenText = '';
let _lastSpokenCoreText = '';
let _lastSpeechTime = 0;
let _lastBeepTime = 0;
let _lastBeepDirection = '';
let _approachBeepInterval = null;

// Cooldowns (ms)
const SPEECH_COOLDOWN_ROUTINE = 4000;
const SPEECH_COOLDOWN_ALERT = 2500;
const SPEECH_COOLDOWN_WARNING = 1500;
const SPEECH_COOLDOWN_CRITICAL = 500;
const BEEP_COOLDOWN = 800;

function getAudioContext() {
    if (!_audioCtx) {
        _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (_audioCtx.state === 'suspended') _audioCtx.resume();
    return _audioCtx;
}

/**
 * Play a directional beep tone.
 * @param {string} direction - left/ahead-left/ahead/ahead-right/right
 * @param {string} urgency - routine/alert/warning/critical
 */
function playDirectionalBeep(direction, urgency) {
    const now = Date.now();
    if (now - _lastBeepTime < BEEP_COOLDOWN) return;
    if (direction === _lastBeepDirection && now - _lastBeepTime < BEEP_COOLDOWN * 2) return;
    _lastBeepTime = now;
    _lastBeepDirection = direction;

    try {
        const ctx = getAudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const panner = ctx.createStereoPanner();

        // Frequency by urgency
        const freqMap = { routine: 440, alert: 600, warning: 800, critical: 1000 };
        osc.frequency.value = freqMap[urgency] || 440;
        osc.type = urgency === 'critical' ? 'square' : 'sine';

        // Stereo pan by direction
        const panMap = {
            'left': -1.0, 'ahead-left': -0.5, 'ahead': 0,
            'ahead-right': 0.5, 'right': 1.0,
        };
        panner.pan.value = panMap[direction] ?? 0;

        // Duration and volume by urgency
        const durationMap = { routine: 0.1, alert: 0.15, warning: 0.2, critical: 0.3 };
        const volMap = { routine: 0.08, alert: 0.12, warning: 0.18, critical: 0.25 };
        const dur = durationMap[urgency] || 0.1;
        const vol = volMap[urgency] || 0.1;

        gain.gain.setValueAtTime(vol, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);

        osc.connect(panner).connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + dur + 0.05);

        // Double beep for critical
        if (urgency === 'critical') {
            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.frequency.value = freqMap.critical * 1.5;
            osc2.type = 'square';
            gain2.gain.setValueAtTime(vol, ctx.currentTime + dur + 0.08);
            gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur + 0.08 + dur);
            osc2.connect(panner).connect(gain2).connect(ctx.destination);
            osc2.start(ctx.currentTime + dur + 0.08);
            osc2.stop(ctx.currentTime + dur * 2 + 0.15);
        }
    } catch (e) { /* Audio not available */ }
}

/**
 * Start approach beeps — rapid beeping that intensifies as distance shrinks.
 * @param {string} distance - very_close/near/medium/far
 * @param {string} direction - direction of the closest threat
 */
function updateApproachBeeps(distance, direction) {
    if (_approachBeepInterval) {
        clearInterval(_approachBeepInterval);
        _approachBeepInterval = null;
    }

    const intervalMap = { very_close: 400, near: 1200, medium: 3000 };
    const interval = intervalMap[distance];
    if (!interval) return; // far → no beeps

    const urgMap = { very_close: 'critical', near: 'warning', medium: 'alert' };
    _approachBeepInterval = setInterval(() => {
        playDirectionalBeep(direction, urgMap[distance] || 'alert');
    }, interval);
}

/**
 * Smart TTS that avoids repeating the same thing and adjusts speech rate by urgency.
 */
function smartSpeak(text, urgency) {
    if (!('speechSynthesis' in window)) return;

    const now = Date.now();
    const cooldownMap = {
        routine: SPEECH_COOLDOWN_ROUTINE,
        alert: SPEECH_COOLDOWN_ALERT,
        warning: SPEECH_COOLDOWN_WARNING,
        critical: SPEECH_COOLDOWN_CRITICAL,
    };
    const cooldown = cooldownMap[urgency] || SPEECH_COOLDOWN_ROUTINE;

    // Deduplicate: ignore dynamic numbers (like exact step counts) when checking for same instruction
    const coreText = text.replace(/\d+/g, '');
    if (coreText === _lastSpokenCoreText && now - _lastSpeechTime < cooldown * 2) return;

    // Respect cooldown
    if (now - _lastSpeechTime < cooldown) return;

    // Critical/warning: interrupt current speech
    if (urgency === 'critical' || urgency === 'warning') {
        window.speechSynthesis.cancel();
    }

    // Don't queue if already speaking (unless urgent)
    if (window.speechSynthesis.speaking && urgency !== 'critical') return;

    const utterance = new SpeechSynthesisUtterance(text);
    const rateMap = { routine: 1.0, alert: 1.1, warning: 1.25, critical: 1.4 };
    utterance.rate = rateMap[urgency] || 1.0;
    utterance.pitch = urgency === 'critical' ? 1.2 : 1.0;
    utterance.volume = urgency === 'critical' ? 1.0 : 0.9;

    window.speechSynthesis.speak(utterance);
    _lastSpokenText = text;
    _lastSpokenCoreText = coreText;
    _lastSpeechTime = now;

    const logType = urgency === 'critical' ? 'danger' : urgency === 'warning' ? 'warning' : 'info';
    addLog(`🔊 "${text}"`, logType);
}

/**
 * Main audio handler — called every frame from updateUI.
 */
function handleRealtimeAudio(result) {
    const objects = result.objects || [];
    const urgency = result.urgency || 'routine';
    const action = result.action || '';

    // Always speak on high-urgency events
    if (urgency === 'critical' || urgency === 'warning') {
        smartSpeak(action, urgency);
    }

    // Find closest in-path threat for approach beeps
    const inPathThreats = objects.filter(o => o.in_path);
    if (inPathThreats.length > 0) {
        const closest = inPathThreats[0]; // already sorted by distance
        const dir = closest.direction || 'ahead';
        const dist = closest.distance || 'medium';
        updateApproachBeeps(dist, dir);

        // Speak alert/routine for moderate threats
        if (urgency === 'alert') {
            smartSpeak(action, urgency);
        }
    } else {
        // No in-path threats → stop approach beeps
        if (_approachBeepInterval) {
            clearInterval(_approachBeepInterval);
            _approachBeepInterval = null;
        }

        // Occasionally confirm "path clear" (long cooldown)
        if (result.path_status === 'clear' && objects.length === 0) {
            smartSpeak('Path clear. Continue ahead.', 'routine');
        } else if (objects.length > 0) {
            smartSpeak(action, 'routine');
        }
    }

    // Directional beep for any nearby object (even off-path)
    const nearbyOnSide = objects.find(o =>
        !o.in_path && (o.distance === 'very_close' || o.distance === 'near')
    );
    if (nearbyOnSide) {
        playDirectionalBeep(nearbyOnSide.direction, 'alert');
    }
}

function updateConnectionStatus(status) {
    const pill = document.getElementById('pipeline-status');
    const text = pill.querySelector('.status-text');
    pill.className = 'status-pill';

    switch (status) {
        case 'connected':
            pill.classList.add('connected');
            text.textContent = 'Connected';
            break;
        case 'connecting':
            text.textContent = 'Connecting…';
            break;
        case 'disconnected':
            text.textContent = 'Disconnected';
            break;
        case 'error':
            pill.classList.add('error');
            text.textContent = 'Connection Error';
            break;
        case 'demo':
            pill.classList.add('connected');
            text.textContent = 'Demo Mode';
            break;
    }
}

function updateLatency(ms) {
    const el = document.getElementById('latency-counter');
    el.textContent = ms ? `${Math.round(ms)}ms` : '—';
}

function updateLoadStatus(msg) {
    const el = document.getElementById('load-status');
    if (el) el.textContent = msg;
}

// ── Risk Panel ────────────────────────────────────────────────────
function updateRiskPanel(result) {
    const badge = document.getElementById('risk-badge');
    const fill = document.getElementById('risk-fill');
    const score = document.getElementById('risk-score');
    const pathStatus = document.getElementById('path-status');

    const level = result.scene_risk_level || 'low';
    const riskScore = result.scene_risk_score || 0;

    badge.textContent = level.toUpperCase();
    badge.className = `risk-badge ${level}`;
    fill.style.width = `${riskScore * 100}%`;
    score.textContent = riskScore.toFixed(2);

    const pathText = pathStatus.querySelector('.path-text');
    const pathIcon = pathStatus.querySelector('.path-icon');
    const ps = result.path_status || 'unknown';
    pathText.textContent = `Path: ${ps.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}`;
    pathIcon.textContent = ps === 'clear' ? '✅' : ps === 'blocked' ? '🚫' : '⚠️';
}

// ── Objects Panel ──────────────────────────────────────────────────
function updateObjectsPanel(objects) {
    const list = document.getElementById('objects-list');
    const count = document.getElementById('object-count');

    count.textContent = objects.length;

    if (objects.length === 0) {
        list.innerHTML = '<div class="empty-state">No objects detected</div>';
        return;
    }

    list.innerHTML = objects.map(obj => {
        const risk = obj.risk_level || 'low';
        const riskColors = { low: '#10b981', medium: '#f59e0b', high: '#ef4444', critical: '#dc2626' };
        return `
      <div class="object-item risk-${risk}">
        <span class="obj-label">${obj.label || 'unknown'}</span>
        <span class="obj-direction">${obj.direction || '—'}</span>
        <span class="obj-risk" style="background:${riskColors[risk]}22; color:${riskColors[risk]}">${risk}</span>
      </div>
    `;
    }).join('');
}

// ── GVS Panel ──────────────────────────────────────────────────────
function updateGVSPanel(gvs) {
    const statusBadge = document.getElementById('gvs-status');
    const dirLabel = document.getElementById('gvs-direction');
    const intensityFill = document.getElementById('gvs-intensity-fill');
    const typeLabel = document.getElementById('gvs-type');
    const channelsLabel = document.getElementById('gvs-channels');

    // Electrodes
    const leftE = document.getElementById('gvs-electrode-left');
    const rightE = document.getElementById('gvs-electrode-right');

    // Arrow
    const arrowLine = document.getElementById('gvs-arrow-line');
    const arrowHead = document.getElementById('gvs-arrow-head');
    const arrowGroup = document.getElementById('gvs-arrow-group');

    // Torso for lean
    const torso = document.getElementById('gvs-torso');

    if (!gvs || !gvs.active) {
        statusBadge.textContent = 'IDLE';
        statusBadge.className = 'gvs-status-badge';
        dirLabel.textContent = '—';
        intensityFill.style.width = '0%';
        typeLabel.textContent = '—';
        channelsLabel.textContent = '—';
        leftE.style.fill = 'var(--surface-2)';
        rightE.style.fill = 'var(--surface-2)';
        arrowLine.style.opacity = '0';
        arrowHead.style.opacity = '0';
        torso.style.transform = '';
        return;
    }

    statusBadge.textContent = 'ACTIVE';
    statusBadge.className = 'gvs-status-badge active';

    // Direction
    const angle = gvs.arrow_angle || 0;
    dirLabel.textContent = angle < 0 ? `← ${Math.abs(angle)}°` : angle > 0 ? `→ ${angle}°` : '↑ 0°';

    // Intensity
    const intensity = (gvs.arrow_strength || 0) * 100;
    intensityFill.style.width = `${intensity}%`;

    // Get type from status_text
    const typeMatch = gvs.status_text?.match(/^(\w+):/);
    typeLabel.textContent = typeMatch ? typeMatch[1] : '—';

    // Channels
    const le = gvs.left_electrode || 0;
    const re = gvs.right_electrode || 0;
    channelsLabel.textContent = le > 0 && re > 0 ? 'Bilateral' : le > 0 ? 'Left' : re > 0 ? 'Right' : '—';

    // Electrode colors
    const eColor = gvs.status_color || '#a855f7';
    leftE.style.fill = le > 0 ? eColor : 'var(--surface-2)';
    leftE.style.opacity = le > 0 ? Math.max(0.4, le) : 1;
    rightE.style.fill = re > 0 ? eColor : 'var(--surface-2)';
    rightE.style.opacity = re > 0 ? Math.max(0.4, re) : 1;

    // Direction arrow
    arrowLine.style.opacity = '1';
    arrowHead.style.opacity = '1';
    arrowGroup.style.transform = `translate(100px, 130px) rotate(${angle}deg)`;
    arrowLine.style.stroke = eColor;
    arrowHead.style.fill = eColor;

    // Body lean
    const lean = gvs.body_lean_angle || 0;
    torso.style.transform = `rotate(${lean}deg)`;
    torso.style.transformOrigin = '100px 75px';

    // Pulse animation
    if (gvs.pulse_animation) {
        leftE.style.animation = 'pulse-dot 0.4s infinite';
        rightE.style.animation = 'pulse-dot 0.4s infinite';
    } else {
        leftE.style.animation = '';
        rightE.style.animation = '';
    }
}

// ── Router Panel ──────────────────────────────────────────────────
function updateRouterPanel(result) {
    const modes = ['direct', 'verify', 'tool', 'deep'];
    const activeMode = result.reasoning_mode || 'direct';

    modes.forEach(m => {
        const el = document.getElementById(`mode-${m}`);
        el.className = `mode-chip${m === activeMode ? ' active' : ''}`;
    });

    document.getElementById('router-reason').textContent = result.router_reason || '';
}

// ── HUD ───────────────────────────────────────────────────────────
function updateHUD(result) {
    const objects = result.objects || [];
    const safest = result.safest_direction || 'ahead';
    const dirIds = ['left', 'ahead-left', 'ahead', 'ahead-right', 'right'];

    // Reset all
    dirIds.forEach(d => {
        const el = document.getElementById(`dir-${d}`);
        el.className = 'dir-arrow';
    });

    // Mark safest direction
    const safeEl = document.getElementById(`dir-${safest}`);
    if (safeEl) safeEl.classList.add('active');

    // Mark hazard directions
    objects.forEach(obj => {
        if (obj.risk_level === 'high' || obj.risk_level === 'critical') {
            const el = document.getElementById(`dir-${obj.direction}`);
            if (el) {
                el.classList.remove('active');
                el.classList.add('hazard');
            }
        } else if (obj.risk_level === 'medium') {
            const el = document.getElementById(`dir-${obj.direction}`);
            if (el && !el.classList.contains('hazard')) {
                el.classList.add('warning-dir');
            }
        }
    });
}

// ── Action Bar ────────────────────────────────────────────────────
function updateActionBar(result) {
    const bar = document.querySelector('.hud-action-bar');
    const text = document.getElementById('action-text');
    const icon = bar.querySelector('.action-icon');

    text.textContent = result.action || 'Analyzing…';

    // Remove previous urgency classes
    bar.className = 'hud-action-bar';

    const urgency = result.urgency || 'routine';
    if (urgency === 'critical') {
        bar.classList.add('urgency-critical');
        icon.textContent = '🚨';
    } else if (urgency === 'warning') {
        bar.classList.add('urgency-warning');
        icon.textContent = '⚠️';
    } else {
        icon.textContent = '🔊';
    }
}

// ── Log Panel ─────────────────────────────────────────────────────
function addLog(message, type = 'info') {
    const container = document.getElementById('log-entries');
    const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

    const entry = document.createElement('div');
    entry.className = `log-entry${type === 'warning' ? ' log-warning' : type === 'danger' ? ' log-danger' : type === 'gvs' ? ' log-gvs' : ''}`;
    entry.innerHTML = `<span class="log-time">${time}</span><span class="log-msg">${message}</span>`;

    // Remove empty state if present
    const empty = container.querySelector('.empty-state');
    if (empty) empty.remove();

    container.prepend(entry);

    // Keep max 30 entries
    while (container.children.length > 30) {
        container.removeChild(container.lastChild);
    }

    logEntries.push({ time, message, type });
}

// ══════════════════════════════════════════════════════════════════
// UI Event Listeners
// ══════════════════════════════════════════════════════════════════
function setupUIListeners() {
    // Settings modal
    document.getElementById('settings-btn').addEventListener('click', () => {
        document.getElementById('settings-modal').classList.remove('hidden');
    });

    document.getElementById('close-settings').addEventListener('click', () => {
        document.getElementById('settings-modal').classList.add('hidden');
    });

    document.getElementById('settings-modal').addEventListener('click', (e) => {
        if (e.target.id === 'settings-modal') {
            document.getElementById('settings-modal').classList.add('hidden');
        }
    });

    // Scene selector
    document.getElementById('setting-scene').addEventListener('change', (e) => {
        currentScene = e.target.value;
        sceneManager.loadScene(currentScene);
        addLog(`Scene changed to: ${currentScene}`, 'info');
    });

    // FPS setting
    document.getElementById('setting-fps').addEventListener('change', (e) => {
        sendFps = parseInt(e.target.value);
        if (wsConnected) {
            startFrameSending();
        }
        addLog(`Frame rate set to: ${sendFps} FPS`, 'info');
    });

    // GVS intensity slider
    document.getElementById('setting-gvs-intensity').addEventListener('input', (e) => {
        document.getElementById('gvs-intensity-label').textContent = parseFloat(e.target.value).toFixed(1);
    });

    // Clear log
    document.getElementById('clear-log-btn').addEventListener('click', () => {
        document.getElementById('log-entries').innerHTML = '<div class="empty-state">Waiting for events…</div>';
        logEntries = [];
    });

    // Escape to unlock pointer
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.getElementById('settings-modal').classList.add('hidden');
        }
    });
}
