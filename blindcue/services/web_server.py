"""Embedded Mobile-First Web Remote Server for BlindCUE with PIN Security.

Serves a native-feeling touch-optimized web controller for smartphones and tablets:
  - Giant tactile GO button with haptic feedback
  - Live Playing Cue monitor with real-time countdown progress bar
  - Next Standby Cue indicator
  - Transport buttons: Pause/Resume, Prev/Next, Blackout, Panic
  - Scrollable cue list with instant single-tap [ ▶ GO ] buttons
  - Real-time zero-latency sync via Server-Sent Events (SSE)
  - PIN Security Lock Screen protecting against unauthorized LAN access (Anti-Burlone)
  - Instant camera scan unlock via QR-embedded PIN tokens
  - 100% offline, zero external dependencies or CDNs
"""

from __future__ import annotations

import hmac
import http.server
import json
import logging
import queue
import threading
import time
import urllib.parse
from typing import Any
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("blindcue.web")

# Maximum permitted HTTP request payload (1 MB) to protect against DoS
MAX_BODY_SIZE = 1024 * 1024
# Cap concurrent SSE streams so runaway tabs cannot exhaust threads/sockets
MAX_SSE_CLIENTS = 32
# Sentinel pushed into SSE queues to unblock threads immediately on stop/revoke
_SSE_CLOSE = object()

# ── Embedded Mobile Web App (HTML5 + CSS3 + Vanilla ES6) ─────────────
_HTML_PAGE = """<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>BlindCUE · Live Remote</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="theme-color" content="#09090b">
  <style>
    * {
      box-sizing: border-box;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
      -webkit-user-select: none;
      margin: 0;
      padding: 0;
    }
    body {
      background-color: #09090b;
      color: #f4f4f5;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      touch-action: manipulation;
      display: flex;
      flex-direction: column;
      height: 100vh;
      height: 100dvh;
      overflow: hidden;
      padding-top: max(8px, env(safe-area-inset-top));
      padding-bottom: max(10px, env(safe-area-inset-bottom));
    }

    /* ── Header ── */
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px;
      background: #141417;
      border-bottom: 1px solid #27272a;
      flex-shrink: 0;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .brand-logo {
      font-size: 18px;
      font-weight: 900;
      letter-spacing: -0.5px;
      color: #38bdf8;
    }
    .brand-title {
      font-size: 13px;
      font-weight: 600;
      color: #a1a1aa;
      max-width: 160px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .conn-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 999px;
      background: #182218;
      color: #4ade80;
      border: 1px solid #22c55e44;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .conn-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #22c55e;
      box-shadow: 0 0 8px #22c55e;
      animation: pulse 2s infinite ease-in-out;
    }
    .conn-badge.offline {
      background: #2a1515;
      color: #f87171;
      border-color: #ef444444;
    }
    .conn-badge.offline .conn-dot {
      background: #ef4444;
      box-shadow: none;
      animation: none;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    /* ── Main Content Container ── */
    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      padding: 10px 12px;
      gap: 10px;
    }

    /* ── In Onda (Live Hero Card) ── */
    .hero-card {
      background: #14171f;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      position: relative;
      overflow: hidden;
      flex-shrink: 0;
      transition: all 0.25s ease;
    }
    .hero-card.is-live {
      background: linear-gradient(145deg, #0e1e17, #13271d);
      border-color: #166534;
      box-shadow: 0 4px 16px rgba(34, 197, 94, 0.12);
    }
    .hero-card.is-paused {
      background: linear-gradient(145deg, #241c10, #312513);
      border-color: #854d0e;
    }
    .hero-top-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .hero-phase-tag {
      font-size: 10px;
      font-weight: 800;
      padding: 3px 8px;
      border-radius: 4px;
      background: #27272a;
      color: #94a3b8;
      letter-spacing: 0.8px;
    }
    .hero-card.is-live .hero-phase-tag {
      background: #16a34a;
      color: #ffffff;
    }
    .hero-card.is-paused .hero-phase-tag {
      background: #f59e0b;
      color: #000000;
    }
    .hero-layer-tag {
      font-size: 10px;
      font-weight: 700;
      color: #38bdf8;
      background: #0f2744;
      padding: 2px 7px;
      border-radius: 4px;
      border: 1px solid #0284c7;
    }
    .hero-title {
      font-size: 18px;
      font-weight: 800;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-top: 2px;
    }
    .hero-progress-bg {
      height: 8px;
      background: #1e293b;
      border-radius: 999px;
      overflow: hidden;
      margin-top: 4px;
      position: relative;
    }
    .hero-progress-bar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #10b981, #22c55e);
      border-radius: 999px;
      transition: width 0.15s linear;
    }
    .hero-card.is-paused .hero-progress-bar {
      background: #f59e0b;
    }
    .hero-time-row {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      font-weight: 700;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      color: #cbd5e1;
      margin-top: 2px;
    }
    .hero-time-countdown {
      color: #e2e8f0;
      font-weight: 800;
    }

    /* ── Standby Card ── */
    .standby-card {
      background: #18181b;
      border: 1px solid #27272a;
      border-left: 4px solid #38bdf8;
      border-radius: 8px;
      padding: 8px 12px;
      display: flex;
      flex-direction: column;
      gap: 2px;
      flex-shrink: 0;
    }
    .standby-label {
      font-size: 9px;
      font-weight: 800;
      color: #38bdf8;
      letter-spacing: 0.8px;
      text-transform: uppercase;
    }
    .standby-title {
      font-size: 14px;
      font-weight: 700;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* ── Transport Controller (Tactile GO + Action Grid) ── */
    .controls-deck {
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex-shrink: 0;
    }

    /* Big GO Button */
    .btn-go {
      width: 100%;
      height: 76px;
      background: linear-gradient(135deg, #22c55e 0%, #15803d 100%);
      border: none;
      border-radius: 14px;
      color: #ffffff;
      font-size: 28px;
      font-weight: 900;
      letter-spacing: 2px;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      cursor: pointer;
      box-shadow: 0 6px 20px rgba(34, 197, 94, 0.35);
      transition: transform 0.08s ease, filter 0.08s ease;
    }
    .btn-go:active {
      transform: scale(0.97);
      filter: brightness(1.2);
    }

    /* Secondary Action Buttons Grid */
    .sub-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
    }
    .btn-sub {
      background: #18181b;
      border: 1px solid #27272a;
      border-radius: 8px;
      color: #cbd5e1;
      padding: 10px 4px;
      font-size: 11px;
      font-weight: 700;
      text-align: center;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      transition: background 0.1s ease, transform 0.08s ease;
    }
    .btn-sub:active {
      transform: scale(0.95);
      background: #27272a;
    }
    .btn-sub.pause-active {
      background: #854d0e;
      color: #ffffff;
      border-color: #f59e0b;
    }
    .btn-sub.panic {
      background: #261111;
      color: #f87171;
      border-color: #7f1d1d;
    }
    .btn-sub.panic:active {
      background: #ef4444;
      color: #ffffff;
    }

    /* ── Scrollable Scaletta (Live Cue List) ── */
    .cuelist-container {
      flex: 1;
      display: flex;
      flex-direction: column;
      background: #111114;
      border: 1px solid #27272a;
      border-radius: 10px;
      overflow: hidden;
      min-height: 120px;
    }
    .cuelist-header {
      padding: 6px 12px;
      background: #18181b;
      border-bottom: 1px solid #27272a;
      font-size: 10px;
      font-weight: 800;
      color: #94a3b8;
      letter-spacing: 0.8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .cuelist-scroll {
      flex: 1;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
      padding: 4px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .cue-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 10px;
      background: #18181b;
      border: 1px solid #27272a;
      border-radius: 6px;
      gap: 8px;
      cursor: pointer;
      transition: border-color 0.15s ease, background 0.15s ease;
    }
    .cue-row:active {
      background: #27272a;
    }
    .cue-row.is-standby {
      border-color: #38bdf8;
      background: #0f1c2e;
    }
    .cue-row.is-live {
      border-color: #22c55e;
      background: #0d2317;
    }
    .cue-info {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .cue-title-row {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .cue-badge {
      font-size: 10px;
      font-weight: 800;
      padding: 1px 5px;
      border-radius: 3px;
      background: #27272a;
      color: #94a3b8;
    }
    .cue-badge.video { background: #3b2a59; color: #c084fc; }
    .cue-badge.audio { background: #133929; color: #34d399; }
    .cue-badge.image { background: #3d2f13; color: #fbbf24; }
    .cue-badge.group { background: #1e2d4d; color: #60a5fa; }
    .cue-badge.action { background: #4c0519; color: #fda4af; }

    .cue-name {
      font-size: 13px;
      font-weight: 700;
      color: #f4f4f5;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .cue-meta {
      font-size: 10px;
      color: #71717a;
      font-family: ui-monospace, monospace;
    }
    .btn-cue-go {
      background: #1e293b;
      border: 1px solid #334155;
      color: #38bdf8;
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 11px;
      font-weight: 800;
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.1s ease;
    }
    .btn-cue-go:active {
      background: #0284c7;
      color: #ffffff;
      transform: scale(0.94);
    }
    .cue-row.is-live .btn-cue-go {
      background: #166534;
      border-color: #22c55e;
      color: #ffffff;
    }

    /* ── PIN Lock Screen Overlay ── */
    .pin-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(9, 9, 11, 0.97);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      z-index: 1000;
      display: none;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .pin-card {
      width: 100%;
      max-width: 320px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      text-align: center;
    }
    .pin-lock-icon {
      font-size: 42px;
      margin-bottom: 2px;
    }
    .pin-title {
      font-size: 18px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: 0.5px;
    }
    .pin-desc {
      font-size: 12px;
      color: #94a3b8;
      line-height: 1.4;
    }
    .pin-dots {
      display: flex;
      gap: 14px;
      margin: 12px 0;
    }
    .pin-dot {
      width: 16px;
      height: 16px;
      border-radius: 50%;
      border: 2px solid #475569;
      background: transparent;
      transition: all 0.15s ease;
    }
    .pin-dot.filled {
      background: #38bdf8;
      border-color: #38bdf8;
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.6);
    }
    .pin-keypad {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      width: 100%;
      max-width: 270px;
    }
    .pin-btn {
      height: 64px;
      border-radius: 50%;
      background: #18181b;
      border: 1px solid #27272a;
      color: #f4f4f5;
      font-size: 24px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.1s ease;
    }
    .pin-btn:active {
      transform: scale(0.92);
      background: #38bdf8;
      color: #000000;
    }
    .pin-btn.pin-action {
      font-size: 16px;
      background: #27272a;
      color: #94a3b8;
    }
    .pin-btn.pin-submit {
      background: #166534;
      border-color: #22c55e;
      color: #ffffff;
      font-weight: 800;
    }
    .pin-err {
      font-size: 12px;
      font-weight: 700;
      color: #ef4444;
      min-height: 18px;
    }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="brand">
      <span class="brand-logo">BlindCUE</span>
      <span class="brand-title" id="showTitle">Spettacolo</span>
    </div>
    <div class="conn-badge" id="connBadge">
      <div class="conn-dot"></div>
      <span id="connText">ONLINE</span>
    </div>
  </header>

  <!-- Main Viewport -->
  <main>
    <!-- In Onda (Live Hero Card) -->
    <div class="hero-card" id="heroCard">
      <div class="hero-top-row">
        <span class="hero-phase-tag" id="heroPhase">STANDBY</span>
        <span class="hero-layer-tag" id="heroLayer">LAYER 1</span>
      </div>
      <div class="hero-title" id="heroTitle">Nessun media in onda</div>
      <div class="hero-progress-bg">
        <div class="hero-progress-bar" id="heroProgressBar"></div>
      </div>
      <div class="hero-time-row">
        <span id="heroTimeElapsed">00:00</span>
        <span class="hero-time-countdown" id="heroTimeRemaining">--:--</span>
      </div>
    </div>

    <!-- Next Standby Cue -->
    <div class="standby-card" id="standbyCard">
      <div class="standby-label">PROSSIMO IN STANDBY</div>
      <div class="standby-title" id="standbyTitle">— Nessuna cue —</div>
    </div>

    <!-- Tactile Controls Deck -->
    <div class="controls-deck">
      <button class="btn-go" id="btnGo" onclick="doAction('go')">
        <span>▶ GO</span>
      </button>

      <div class="sub-grid">
        <button class="btn-sub" id="btnPause" onclick="doAction('pause_toggle')">
          <span style="font-size: 14px;">⏸</span>
          <span id="lblPause">PAUSA</span>
        </button>
        <button class="btn-sub" onclick="doAction('prev')">
          <span style="font-size: 14px;">⏮</span>
          <span>PREV</span>
        </button>
        <button class="btn-sub" onclick="doAction('next')">
          <span style="font-size: 14px;">⏭</span>
          <span>NEXT</span>
        </button>
        <button class="btn-sub panic" onclick="doAction('panic')">
          <span style="font-size: 14px;">🚨</span>
          <span>PANIC</span>
        </button>
      </div>
    </div>

    <!-- Scrollable Scaletta (Live Cue List) -->
    <div class="cuelist-container">
      <div class="cuelist-header">
        <span>SCALETTA LIVE</span>
        <span id="cueCount">0 CUE</span>
      </div>
      <div class="cuelist-scroll" id="cueListScroll">
        <!-- Rendered dynamically -->
      </div>
    </div>
  </main>

  <!-- PIN Lock Screen Overlay (Anti-Burlone) -->
  <div class="pin-overlay" id="pinOverlay">
    <div class="pin-card">
      <div class="pin-lock-icon">🔒</div>
      <div class="pin-title">REGIA PROTETTA</div>
      <div class="pin-desc">Inserisci il PIN a 6 cifre per sbloccare i comandi live sul palco.</div>

      <div class="pin-dots" id="pinDots">
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
      </div>

      <div class="pin-keypad">
        <button class="pin-btn" onclick="pressPin('1')">1</button>
        <button class="pin-btn" onclick="pressPin('2')">2</button>
        <button class="pin-btn" onclick="pressPin('3')">3</button>
        <button class="pin-btn" onclick="pressPin('4')">4</button>
        <button class="pin-btn" onclick="pressPin('5')">5</button>
        <button class="pin-btn" onclick="pressPin('6')">6</button>
        <button class="pin-btn" onclick="pressPin('7')">7</button>
        <button class="pin-btn" onclick="pressPin('8')">8</button>
        <button class="pin-btn" onclick="pressPin('9')">9</button>
        <button class="pin-btn pin-action" onclick="clearPin()">C</button>
        <button class="pin-btn" onclick="pressPin('0')">0</button>
        <button class="pin-btn pin-action pin-submit" onclick="submitPin()">OK</button>
      </div>

      <div class="pin-err" id="pinErr"></div>
    </div>
  </div>

  <script>
    let evtSource = null;
    let lastState = null;
    let currentPin = sessionStorage.getItem('blindcue_pin') || "";
    let enteredBuffer = "";

    // Check if PIN was embedded in URL (e.g. from camera QR code scan!)
    const urlParams = new URLSearchParams(window.location.search);
    const pinFromUrl = urlParams.get('pin');
    if (pinFromUrl) {
      currentPin = pinFromUrl;
      sessionStorage.setItem('blindcue_pin', currentPin);
    }

    function vibrate(ms = 40) {
      if (window.navigator && window.navigator.vibrate) {
        try { window.navigator.vibrate(ms); } catch (e) {}
      }
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    let lastCueListSig = "";

    function formatTime(sec) {
      if (sec === undefined || sec === null || isNaN(sec) || sec < 0) return "00:00";
      const s = Math.round(sec);
      const m = Math.floor(s / 60);
      const r = s % 60;
      return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
    }

    function doAction(actionName, cueId = null) {
      vibrate(actionName === 'panic' ? 80 : 40);
      const payload = { action: actionName };
      if (cueId !== null) payload.cue_id = cueId;

      const headers = { 'Content-Type': 'application/json' };
      if (currentPin) {
        headers['X-BlindCue-PIN'] = currentPin;
      }

      fetch('/api/action', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      })
      .then(res => {
        if (res.status === 401) {
          showLockScreen("Sessione scaduta o non autorizzata");
        }
      })
      .catch(err => console.error("Action error:", err));
    }

    function updateUI(state) {
      if (!state) return;
      lastState = state;

      // Check PIN lock
      if (state.authenticated === false) {
        showLockScreen(state.error || "");
        return;
      } else {
        hideLockScreen();
      }

      // 1. Show Title & Connection
      document.getElementById('showTitle').textContent = state.show_title || "Spettacolo";

      // 2. In Onda / Live Hero Card
      const hero = document.getElementById('heroCard');
      const active = (state.active_cues && state.active_cues.length > 0) ? state.active_cues[0] : null;

      if (active) {
        hero.classList.add('is-live');
        if (state.is_paused || active.is_paused) {
          hero.classList.add('is-paused');
          document.getElementById('heroPhase').textContent = "IN PAUSA";
        } else {
          hero.classList.remove('is-paused');
          document.getElementById('heroPhase').textContent = active.phase || "IN ONDA";
        }

        document.getElementById('heroLayer').textContent = `LAYER ${active.layer}`;
        document.getElementById('heroTitle').textContent = active.title || "Media Live";

        const dur = Math.max(0.1, active.end_sec - active.start_sec);
        const elap = Math.max(0.0, active.pos_sec - active.start_sec);
        const rem = Math.max(0.0, active.end_sec - active.pos_sec);
        const pct = Math.min(100, Math.max(0, (elap / dur) * 100));

        document.getElementById('heroProgressBar').style.width = `${pct.toFixed(1)}%`;
        document.getElementById('heroTimeElapsed').textContent = formatTime(elap);
        document.getElementById('heroTimeRemaining').textContent = `-${formatTime(rem)}`;
      } else {
        hero.classList.remove('is-live', 'is-paused');
        document.getElementById('heroPhase').textContent = "STANDBY";
        document.getElementById('heroLayer').textContent = "LAYER 0";
        document.getElementById('heroTitle').textContent = "Nessun media in onda";
        document.getElementById('heroProgressBar').style.width = "0%";
        document.getElementById('heroTimeElapsed').textContent = "00:00";
        document.getElementById('heroTimeRemaining').textContent = "--:--";
      }

      // 3. Standby Card
      if (state.standby_cue) {
        document.getElementById('standbyTitle').textContent = `${state.standby_cue.ref} · ${state.standby_cue.name}`;
      } else {
        document.getElementById('standbyTitle').textContent = "— Fine Scaletta —";
      }

      // 4. Pause button status
      const btnP = document.getElementById('btnPause');
      const lblP = document.getElementById('lblPause');
      if (state.is_paused) {
        btnP.classList.add('pause-active');
        lblP.textContent = "RIPRENDI";
      } else {
        btnP.classList.remove('pause-active');
        lblP.textContent = "PAUSA";
      }

      // 5. Scaletta (Cue List) — only rebuild DOM when list state changes so mobile taps never drop
      const listEl = document.getElementById('cueListScroll');
      const cues = state.cues || [];
      document.getElementById('cueCount').textContent = `${cues.length} CUE`;

      const cueSig = JSON.stringify(cues.map(c => [c.id, c.name, c.ref, c.type, c.layer, c.output_target, c.status, c.duration, c.is_standby]));
      if (cueSig !== lastCueListSig) {
        lastCueListSig = cueSig;
        let html = "";
        cues.forEach(c => {
          const statusNorm = String(c.status || "").toLowerCase();
          const typeNorm = String(c.type || "video").toLowerCase();
          const isLive = (statusNorm === "live");
          const isOffline = (statusNorm === "offline");
          const isSb = Boolean(c.is_standby);
          const rowClass = `cue-row ${isLive ? 'is-live' : ''} ${isSb ? 'is-standby' : ''}`;
          const safeType = ['video', 'audio', 'image', 'group', 'action'].includes(typeNorm) ? typeNorm : 'video';
          const typeClass = `cue-badge ${safeType}`;

          let icon = "🎬";
          if (safeType === "audio") icon = "🎵";
          else if (safeType === "image") icon = "🖼";
          else if (safeType === "group") icon = "📁";
          else if (safeType === "action") icon = "⚡";

          const outPrefix = (String(c.output_target || "A").toUpperCase() === "B") ? "B·" : "";
          const cueIdNum = Number(c.id);
          const safeIdArg = Number.isFinite(cueIdNum) ? String(cueIdNum) : JSON.stringify(String(c.id));

          html += `
            <div class="${rowClass}" onclick="doAction('select', ${safeIdArg})">
              <div class="cue-info">
                <div class="cue-title-row">
                  <span class="${typeClass}">${icon} ${escapeHtml(c.ref || ('#' + c.id))}</span>
                  <span class="cue-name">${escapeHtml(c.name)}</span>
                </div>
                <div class="cue-meta">${outPrefix}L${escapeHtml(c.layer)} · ${formatTime(c.duration)}${isOffline ? ' · ⚠ OFFLINE' : ''}</div>
              </div>
              <button class="btn-cue-go" onclick="event.stopPropagation(); doAction('cue_go', ${safeIdArg})">
                ${isLive ? '● LIVE' : '▶ GO'}
              </button>
            </div>
          `;
        });
        listEl.innerHTML = html;
      }
    }

    function setOnline(online) {
      const b = document.getElementById('connBadge');
      const t = document.getElementById('connText');
      if (online) {
        b.classList.remove('offline');
        t.textContent = "ONLINE";
      } else {
        b.classList.add('offline');
        t.textContent = "DISCONNESSO";
      }
    }

    function initSSE() {
      if (evtSource) {
        evtSource.close();
      }
      const sseUrl = currentPin ? `/api/events?pin=${encodeURIComponent(currentPin)}` : '/api/events';
      evtSource = new EventSource(sseUrl);

      evtSource.onopen = () => {
        setOnline(true);
      };

      evtSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          updateUI(data);
        } catch (err) {
          console.error("SSE parse error:", err);
        }
      };

      evtSource.onerror = () => {
        setOnline(false);
        evtSource.close();
        evtSource = null;
        // Probe status once so a revoked PIN opens the lock screen instead of retrying into lockout
        const probeUrl = currentPin ? `/api/status?pin=${encodeURIComponent(currentPin)}` : '/api/status';
        fetch(probeUrl)
          .then(res => res.json())
          .then(data => {
            if (data.authenticated === false && data.pin_required) {
              currentPin = "";
              sessionStorage.removeItem('blindcue_pin');
              showLockScreen(data.error || "Sessione revocata: reinserisci il PIN");
            } else {
              setTimeout(initSSE, 2500);
            }
          })
          .catch(() => {
            setTimeout(initSSE, 2500);
          });
      };
    }

    // ── PIN Pad Interaction & Security ──

    function showLockScreen(errMsg = "") {
      document.getElementById('pinOverlay').style.display = 'flex';
      if (errMsg) document.getElementById('pinErr').textContent = errMsg;
    }

    function hideLockScreen() {
      document.getElementById('pinOverlay').style.display = 'none';
      document.getElementById('pinErr').textContent = "";
    }

    function renderDots() {
      const dots = document.querySelectorAll('#pinDots .pin-dot');
      dots.forEach((d, idx) => {
        if (idx < enteredBuffer.length) {
          d.classList.add('filled');
        } else {
          d.classList.remove('filled');
        }
      });
    }

    function pressPin(digit) {
      vibrate(25);
      if (enteredBuffer.length < 6) {
        enteredBuffer += digit;
        renderDots();
        document.getElementById('pinErr').textContent = "";
        if (enteredBuffer.length === 6) {
          submitPin();
        }
      }
    }

    function clearPin() {
      vibrate(20);
      enteredBuffer = "";
      renderDots();
      document.getElementById('pinErr').textContent = "";
    }

    function submitPin() {
      if (!enteredBuffer) return;
      vibrate(40);
      const testPin = enteredBuffer;
      fetch(`/api/status?pin=${encodeURIComponent(testPin)}`)
        .then(res => res.json())
        .then(data => {
          if (data.authenticated) {
            currentPin = testPin;
            sessionStorage.setItem('blindcue_pin', currentPin);
            hideLockScreen();
            updateUI(data);
            initSSE();
          } else {
            enteredBuffer = "";
            renderDots();
            document.getElementById('pinErr').textContent = data.error || "PIN errato";
            vibrate(80);
          }
        })
        .catch(() => {
          document.getElementById('pinErr').textContent = "Errore di connessione alla regia";
        });
    }

    // Initial check
    const statusUrl = currentPin ? `/api/status?pin=${encodeURIComponent(currentPin)}` : '/api/status';
    fetch(statusUrl)
      .then(res => res.json())
      .then(data => {
        if (data.authenticated === false && data.pin_required) {
          showLockScreen();
        } else {
          updateUI(data);
          setOnline(true);
          initSSE();
        }
      })
      .catch(() => {
        setOnline(false);
        showLockScreen();
      });
  </script>
</body>
</html>
"""

# ── Embedded Director Monitor (Read-Only Live Dashboard for Tablets & Desks) ──
_HTML_MONITOR_PAGE = """<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>BlindCUE · Monitor Regia</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="theme-color" content="#09090b">
  <style>
    * {
      box-sizing: border-box;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
      -webkit-user-select: none;
      margin: 0;
      padding: 0;
      cursor: default;
    }
    body {
      background-color: #09090b;
      color: #f4f4f5;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      flex-direction: column;
      height: 100vh;
      height: 100dvh;
      overflow: hidden;
      padding-top: max(8px, env(safe-area-inset-top));
      padding-bottom: max(10px, env(safe-area-inset-bottom));
    }

    /* ── Header ── */
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 20px;
      background: #141417;
      border-bottom: 1px solid #27272a;
      flex-shrink: 0;
      gap: 12px;
    }
    .brand-group {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .brand-logo {
      font-size: 19px;
      font-weight: 900;
      letter-spacing: -0.5px;
      color: #38bdf8;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .badge-readonly {
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.6px;
      padding: 3px 8px;
      border-radius: 4px;
      background: #3b2a59;
      color: #c084fc;
      border: 1px solid #7c3aed66;
      text-transform: uppercase;
    }
    .show-title {
      font-size: 14px;
      font-weight: 700;
      color: #cbd5e1;
      max-width: 320px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .header-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .conn-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 999px;
      background: #182218;
      color: #4ade80;
      border: 1px solid #22c55e44;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .conn-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #22c55e;
      box-shadow: 0 0 8px #22c55e;
      animation: pulse 2s infinite ease-in-out;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }
    .conn-badge.offline {
      background: #2a1515;
      color: #f87171;
      border-color: #ef444444;
    }
    .conn-badge.offline .conn-dot {
      background: #ef4444;
      box-shadow: 0 0 6px #ef4444;
      animation: none;
    }

    /* ── Main Layout ── */
    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 12px 18px;
      gap: 12px;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
    }

    /* ── 3 Layers Multi-track Live Section ── */
    .section-title {
      font-size: 11px;
      font-weight: 800;
      color: #94a3b8;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .layers-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      flex-shrink: 0;
    }
    @media (max-width: 768px) {
      .layers-grid {
        grid-template-columns: 1fr;
      }
    }
    .layer-card {
      background: #141417;
      border: 1px solid #27272a;
      border-radius: 8px;
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: all 0.2s ease;
      position: relative;
      overflow: hidden;
    }
    .layer-card.is-live {
      border-color: #22c55e;
      background: #0d1e17;
      box-shadow: 0 0 16px rgba(34, 197, 94, 0.15);
    }
    .layer-card.is-paused {
      border-color: #f59e0b;
      background: #1e190f;
    }
    .layer-hdr {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .layer-badge {
      font-size: 11px;
      font-weight: 800;
      color: #38bdf8;
      letter-spacing: 0.5px;
    }
    .layer-status {
      font-size: 10px;
      font-weight: 800;
      padding: 2px 7px;
      border-radius: 4px;
      background: #27272a;
      color: #94a3b8;
      text-transform: uppercase;
    }
    .layer-card.is-live .layer-status {
      background: #166534;
      color: #86efac;
    }
    .layer-card.is-paused .layer-status {
      background: #854d0e;
      color: #fde047;
    }
    .layer-title {
      font-size: 13px;
      font-weight: 700;
      color: #f4f4f5;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      min-height: 18px;
    }
    .layer-progress-bg {
      height: 6px;
      background: #27272a;
      border-radius: 3px;
      overflow: hidden;
    }
    .layer-progress-bar {
      height: 100%;
      width: 0%;
      background: #22c55e;
      border-radius: 3px;
      transition: width 0.1s linear;
    }
    .layer-card.is-paused .layer-progress-bar {
      background: #f59e0b;
    }
    .layer-time-row {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      font-weight: 700;
      font-family: ui-monospace, monospace;
      color: #94a3b8;
    }

    /* ── Standby Banner ── */
    .standby-banner {
      background: #0f1c2e;
      border: 1px solid #0284c7;
      border-radius: 8px;
      padding: 10px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-shrink: 0;
    }
    .standby-left {
      display: flex;
      flex-direction: column;
      gap: 3px;
      min-width: 0;
    }
    .standby-tag {
      font-size: 10px;
      font-weight: 800;
      color: #38bdf8;
      letter-spacing: 0.8px;
      text-transform: uppercase;
    }
    .standby-cue-name {
      font-size: 15px;
      font-weight: 800;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .standby-meta {
      font-size: 11px;
      color: #94a3b8;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .standby-meta-item {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    /* ── Cue List Table (Scaletta Regia) ── */
    .table-container {
      flex: 1;
      background: #141417;
      border: 1px solid #27272a;
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      min-height: 200px;
    }
    .table-header-bar {
      padding: 8px 14px;
      background: #18181b;
      border-bottom: 1px solid #27272a;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      font-weight: 800;
      color: #94a3b8;
      letter-spacing: 0.6px;
      flex-shrink: 0;
    }
    .table-scroll {
      flex: 1;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 12px;
    }
    thead th {
      position: sticky;
      top: 0;
      background: #18181b;
      color: #94a3b8;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      padding: 8px 12px;
      border-bottom: 1px solid #27272a;
      z-index: 2;
    }
    tbody tr {
      border-bottom: 1px solid #1e1e24;
      transition: background 0.15s ease;
    }
    tbody tr.is-live {
      background: rgba(34, 197, 94, 0.12);
      border-left: 3px solid #22c55e;
    }
    tbody tr.is-standby {
      background: rgba(56, 189, 248, 0.10);
      border-left: 3px solid #38bdf8;
    }
    tbody td {
      padding: 8px 12px;
      vertical-align: middle;
      color: #cbd5e1;
    }
    .cue-col-ref {
      font-weight: 800;
      font-family: ui-monospace, monospace;
      color: #f4f4f5;
      font-size: 13px;
      white-space: nowrap;
    }
    .cue-col-name {
      font-weight: 600;
      color: #ffffff;
    }
    .cue-notes {
      font-size: 10px;
      color: #71717a;
      margin-top: 2px;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 10px;
      font-weight: 800;
      padding: 2px 6px;
      border-radius: 4px;
      background: #27272a;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .status-badge.live {
      background: #166534;
      color: #86efac;
      border: 1px solid #22c55e66;
    }
    .status-badge.standby {
      background: #0369a1;
      color: #bae6fd;
      border: 1px solid #38bdf866;
    }
    .type-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 3px;
      background: #27272a;
      color: #cbd5e1;
    }
    .type-badge.video { background: #3b2a59; color: #c084fc; }
    .type-badge.audio { background: #133929; color: #34d399; }
    .type-badge.image { background: #3d2f13; color: #fbbf24; }
    .type-badge.group { background: #1e2d4d; color: #60a5fa; }
    .type-badge.action { background: #4c0519; color: #fda4af; }

    /* Footer notice */
    footer {
      padding: 6px 16px;
      text-align: center;
      font-size: 10px;
      color: #64748b;
      border-top: 1px solid #1e1e24;
      flex-shrink: 0;
    }

    /* ── PIN Lock Screen Overlay ── */
    .pin-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(9, 9, 11, 0.97);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      z-index: 1000;
      display: none;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .pin-card {
      width: 100%;
      max-width: 320px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      text-align: center;
    }
    .pin-lock-icon {
      font-size: 42px;
      margin-bottom: 2px;
    }
    .pin-title {
      font-size: 18px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: 0.5px;
    }
    .pin-desc {
      font-size: 12px;
      color: #94a3b8;
      line-height: 1.4;
    }
    .pin-dots {
      display: flex;
      gap: 12px;
      margin: 12px 0;
    }
    .pin-dot {
      width: 14px;
      height: 14px;
      border-radius: 50%;
      border: 2px solid #475569;
      background: transparent;
      transition: all 0.15s ease;
    }
    .pin-dot.filled {
      background: #38bdf8;
      border-color: #38bdf8;
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.6);
    }
    .pin-keypad {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      width: 100%;
      max-width: 270px;
    }
    .pin-btn {
      height: 60px;
      border-radius: 50%;
      background: #18181b;
      border: 1px solid #27272a;
      color: #f4f4f5;
      font-size: 24px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.1s ease;
    }
    .pin-btn:active {
      transform: scale(0.92);
      background: #38bdf8;
      color: #000000;
    }
    .pin-btn.pin-action {
      font-size: 16px;
      background: #27272a;
      color: #94a3b8;
    }
    .pin-btn.pin-submit {
      background: #166534;
      border-color: #22c55e;
      color: #ffffff;
      font-weight: 800;
    }
    .pin-err {
      font-size: 12px;
      font-weight: 700;
      color: #ef4444;
      min-height: 18px;
    }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="brand-group">
      <div class="brand-logo">
        <span>👁️ BlindCUE</span>
      </div>
      <span class="badge-readonly">Monitor Regia · Sola Lettura</span>
      <span class="show-title" id="showTitle">Spettacolo</span>
    </div>
    <div class="header-right">
      <div class="conn-badge" id="connBadge">
        <div class="conn-dot"></div>
        <span id="connText">LIVE SYNC</span>
      </div>
    </div>
  </header>

  <!-- Main Viewport -->
  <main>
    <!-- Section: 3-Layer Multitrack Compositing View -->
    <div class="section-title">
      <span>● Livelli di Emissione in Tempo Reale (3 Layer)</span>
    </div>
    <div class="layers-grid">
      <!-- Layer 1 -->
      <div class="layer-card" id="layerCard1">
        <div class="layer-hdr">
          <span class="layer-badge">LAYER 1 (FONDO)</span>
          <span class="layer-status" id="layerStatus1">IDLE</span>
        </div>
        <div class="layer-title" id="layerTitle1">— Inattivo / Nero —</div>
        <div class="layer-progress-bg">
          <div class="layer-progress-bar" id="layerBar1"></div>
        </div>
        <div class="layer-time-row">
          <span id="layerElap1">00:00</span>
          <span id="layerRem1">--:--</span>
        </div>
      </div>

      <!-- Layer 2 -->
      <div class="layer-card" id="layerCard2">
        <div class="layer-hdr">
          <span class="layer-badge">LAYER 2 (MEDIO)</span>
          <span class="layer-status" id="layerStatus2">IDLE</span>
        </div>
        <div class="layer-title" id="layerTitle2">— Inattivo / Nero —</div>
        <div class="layer-progress-bg">
          <div class="layer-progress-bar" id="layerBar2"></div>
        </div>
        <div class="layer-time-row">
          <span id="layerElap2">00:00</span>
          <span id="layerRem2">--:--</span>
        </div>
      </div>

      <!-- Layer 3 -->
      <div class="layer-card" id="layerCard3">
        <div class="layer-hdr">
          <span class="layer-badge">LAYER 3 (OVERLAY)</span>
          <span class="layer-status" id="layerStatus3">IDLE</span>
        </div>
        <div class="layer-title" id="layerTitle3">— Inattivo / Nero —</div>
        <div class="layer-progress-bg">
          <div class="layer-progress-bar" id="layerBar3"></div>
        </div>
        <div class="layer-time-row">
          <span id="layerElap3">00:00</span>
          <span id="layerRem3">--:--</span>
        </div>
      </div>
    </div>

    <!-- Output B Layers (shown dynamically when dual independent outputs are active) -->
    <div class="section-title" id="outputBTitle" style="display: none;">
      <span>● Uscita B — Proiettore Indipendente (Layer B·1..B·3)</span>
    </div>
    <div class="layers-grid" id="outputBGrid" style="display: none;">
      <div class="layer-card" id="layerCard4">
        <div class="layer-hdr">
          <span class="layer-badge">B·LAYER 1 (FONDO)</span>
          <span class="layer-status" id="layerStatus4">IDLE</span>
        </div>
        <div class="layer-title" id="layerTitle4">— Inattivo / Nero —</div>
        <div class="layer-progress-bg"><div class="layer-progress-bar" id="layerBar4"></div></div>
        <div class="layer-time-row"><span id="layerElap4">00:00</span><span id="layerRem4">--:--</span></div>
      </div>
      <div class="layer-card" id="layerCard5">
        <div class="layer-hdr">
          <span class="layer-badge">B·LAYER 2 (MEDIO)</span>
          <span class="layer-status" id="layerStatus5">IDLE</span>
        </div>
        <div class="layer-title" id="layerTitle5">— Inattivo / Nero —</div>
        <div class="layer-progress-bg"><div class="layer-progress-bar" id="layerBar5"></div></div>
        <div class="layer-time-row"><span id="layerElap5">00:00</span><span id="layerRem5">--:--</span></div>
      </div>
      <div class="layer-card" id="layerCard6">
        <div class="layer-hdr">
          <span class="layer-badge">B·LAYER 3 (OVERLAY)</span>
          <span class="layer-status" id="layerStatus6">IDLE</span>
        </div>
        <div class="layer-title" id="layerTitle6">— Inattivo / Nero —</div>
        <div class="layer-progress-bg"><div class="layer-progress-bar" id="layerBar6"></div></div>
        <div class="layer-time-row"><span id="layerElap6">00:00</span><span id="layerRem6">--:--</span></div>
      </div>
    </div>

    <!-- Section: Standby Cue Banner -->
    <div class="standby-banner" id="standbyBanner">
      <div class="standby-left">
        <div class="standby-tag">PROSSIMA CUE IN STANDBY (PROSSIMO LANCIO)</div>
        <div class="standby-cue-name" id="standbyCueName">— Nessuna cue in standby —</div>
        <div class="standby-meta" id="standbyMeta"></div>
      </div>
    </div>

    <!-- Section: Scaletta Spettacolo Completa -->
    <div class="table-container">
      <div class="table-header-bar">
        <span>SCALETTA COMPLETA DELLO SPETTACOLO</span>
        <span id="cuesCountBadge">0 CUE</span>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th style="width: 105px;">STATO</th>
              <th style="width: 70px;">Q #</th>
              <th>TITOLO CUE & NOTE</th>
              <th style="width: 95px;">TIPO</th>
              <th style="width: 65px;">LAYER</th>
              <th style="width: 75px;">DURATA</th>
              <th style="width: 95px;">FADE IN/OUT</th>
              <th style="width: 95px;">AVANZAMENTO</th>
            </tr>
          </thead>
          <tbody id="cuesTableBody">
            <!-- Dynamically rendered rows -->
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <!-- Footer Notice -->
  <footer>
    🔒 Interfaccia passiva di monitoraggio per la Direzione Artistica e di Scena · Nessun comando attivo abilitato · BlindCUE Native
  </footer>

  <!-- PIN Lock Screen Overlay -->
  <div class="pin-overlay" id="pinOverlay">
    <div class="pin-card">
      <div class="pin-lock-icon">🔒</div>
      <div class="pin-title">REGIA PROTETTA</div>
      <div class="pin-desc">Inserisci il PIN a 6 cifre per accedere alla visualizzazione del Monitor Regia.</div>

      <div class="pin-dots" id="pinDots">
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
        <div class="pin-dot"></div>
      </div>

      <div class="pin-keypad">
        <button class="pin-btn" onclick="pressPin('1')">1</button>
        <button class="pin-btn" onclick="pressPin('2')">2</button>
        <button class="pin-btn" onclick="pressPin('3')">3</button>
        <button class="pin-btn" onclick="pressPin('4')">4</button>
        <button class="pin-btn" onclick="pressPin('5')">5</button>
        <button class="pin-btn" onclick="pressPin('6')">6</button>
        <button class="pin-btn" onclick="pressPin('7')">7</button>
        <button class="pin-btn" onclick="pressPin('8')">8</button>
        <button class="pin-btn" onclick="pressPin('9')">9</button>
        <button class="pin-btn pin-action" onclick="clearPin()">C</button>
        <button class="pin-btn" onclick="pressPin('0')">0</button>
        <button class="pin-btn pin-action pin-submit" onclick="submitPin()">OK</button>
      </div>

      <div class="pin-err" id="pinErr"></div>
    </div>
  </div>

  <script>
    let evtSource = null;
    let lastState = null;
    let currentPin = sessionStorage.getItem('blindcue_pin') || "";
    let enteredBuffer = "";

    // Read ?pin=... from URL (auto-unlock when scanning QR code)
    const urlParams = new URLSearchParams(window.location.search);
    const pinFromUrl = urlParams.get('pin');
    if (pinFromUrl) {
      currentPin = pinFromUrl;
      sessionStorage.setItem('blindcue_pin', currentPin);
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    let lastMonitorTableSig = "";

    function formatTime(sec) {
      if (sec === undefined || sec === null || isNaN(sec) || sec < 0) return "00:00";
      const s = Math.round(sec);
      const m = Math.floor(s / 60);
      const r = s % 60;
      return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
    }

    function updateMonitorUI(state) {
      if (!state) return;
      lastState = state;

      if (state.authenticated === false) {
        showLockScreen(state.error || "");
        return;
      } else {
        hideLockScreen();
      }

      // Show Title
      document.getElementById('showTitle').textContent = state.show_title || "Spettacolo";

      // Layers Deck (1-3 Output A, plus 4-6 Output B when dual output is active)
      const layers = state.layers || {};
      const dualActive = Boolean(state.dual_output_active);
      document.getElementById('outputBTitle').style.display = dualActive ? 'flex' : 'none';
      document.getElementById('outputBGrid').style.display = dualActive ? 'grid' : 'none';
      const activeIds = dualActive ? [1, 2, 3, 4, 5, 6] : [1, 2, 3];
      activeIds.forEach(lIdx => {
        const lData = layers[String(lIdx)] || { is_live: false, title: "— Inattivo / Nero —", phase: "IDLE", pos_sec: 0, end_sec: 0, start_sec: 0 };
        const card = document.getElementById(`layerCard${lIdx}`);
        const stat = document.getElementById(`layerStatus${lIdx}`);
        const title = document.getElementById(`layerTitle${lIdx}`);
        const bar = document.getElementById(`layerBar${lIdx}`);
        const elap = document.getElementById(`layerElap${lIdx}`);
        const rem = document.getElementById(`layerRem${lIdx}`);

        if (lData.is_live) {
          card.classList.add('is-live');
          if (lData.is_paused || state.is_paused) {
            card.classList.add('is-paused');
            stat.textContent = "IN PAUSA";
          } else {
            card.classList.remove('is-paused');
            stat.textContent = lData.phase || "ON AIR";
          }
          title.textContent = `${lData.q_label ? lData.q_label + ' · ' : ''}${lData.title}`;

          const dur = Math.max(0.1, lData.end_sec - lData.start_sec);
          const pos = Math.max(0.0, lData.pos_sec - lData.start_sec);
          const rSec = Math.max(0.0, lData.end_sec - lData.pos_sec);
          const pct = Math.min(100, Math.max(0, (pos / dur) * 100));

          bar.style.width = `${pct.toFixed(1)}%`;
          elap.textContent = formatTime(pos);
          rem.textContent = `-${formatTime(rSec)}`;
        } else {
          card.classList.remove('is-live', 'is-paused');
          stat.textContent = "IDLE";
          title.textContent = "— Inattivo / Nero —";
          bar.style.width = "0%";
          elap.textContent = "00:00";
          rem.textContent = "--:--";
        }
      });

      // Standby Banner
      const sbName = document.getElementById('standbyCueName');
      const sbMeta = document.getElementById('standbyMeta');
      if (state.standby_cue) {
        sbName.textContent = `${state.standby_cue.ref} · ${state.standby_cue.name}`;
        sbMeta.innerHTML = `
          <span class="standby-meta-item"><b>Layer:</b> L${escapeHtml(state.standby_cue.layer)}</span>
          <span class="standby-meta-item"><b>Durata:</b> ${formatTime(state.standby_cue.duration)}</span>
          <span class="standby-meta-item"><b>Fade:</b> ${escapeHtml(state.standby_cue.fade_in || 0)}s IN / ${escapeHtml(state.standby_cue.fade_out || 0)}s OUT</span>
          ${state.standby_cue.notes ? `<span class="standby-meta-item"><b>Note:</b> ${escapeHtml(state.standby_cue.notes)}</span>` : ''}
        `;
      } else {
        sbName.textContent = "— Fine Scaletta —";
        sbMeta.innerHTML = `<span class="standby-meta-item">Tutte le cue eseguite</span>`;
      }

      // Scaletta Table (diffed to avoid repaint jitter)
      const tb = document.getElementById('cuesTableBody');
      const cues = state.cues || [];
      document.getElementById('cuesCountBadge').textContent = `${cues.length} CUE`;

      const tableSig = JSON.stringify(cues);
      if (tableSig !== lastMonitorTableSig) {
        lastMonitorTableSig = tableSig;
        let html = "";
        cues.forEach(c => {
          const statusNorm = String(c.status || "").toLowerCase();
          const typeNorm = String(c.type || "video").toLowerCase();
          const safeType = ['video', 'audio', 'image', 'group', 'action'].includes(typeNorm) ? typeNorm : 'video';
          const isLive = (statusNorm === "live");
          const isSb = Boolean(c.is_standby);
          const rowClass = `${isLive ? 'is-live' : ''} ${isSb ? 'is-standby' : ''}`;

          let stBadge = `<span class="status-badge">○ PRONTA</span>`;
          if (isLive) {
            stBadge = `<span class="status-badge live">● IN ONDA</span>`;
          } else if (isSb) {
            stBadge = `<span class="status-badge standby">▶ STANDBY</span>`;
          } else if (statusNorm === "offline") {
            stBadge = `<span class="status-badge" style="color:#f87171;">⚠ OFFLINE</span>`;
          }

          const typeClass = `type-badge ${safeType}`;
          let icon = "🎬";
          if (safeType === "audio") icon = "🎵";
          else if (safeType === "image") icon = "🖼";
          else if (safeType === "group") icon = "📁";
          else if (safeType === "action") icon = "⚡";

          const outPrefix = (String(c.output_target || "A").toUpperCase() === "B") ? "B·" : "";
          const followTxt = c.follow_mode === 'AUTO_FOLLOW' ? 'Auto-follow' : (c.follow_mode === 'SIMULTANEOUS' ? 'Simultanea' : 'Manuale');

          html += `
            <tr class="${rowClass}">
              <td>${stBadge}</td>
              <td class="cue-col-ref">${escapeHtml(c.ref || ('#' + c.id))}</td>
              <td>
                <div class="cue-col-name">${escapeHtml(c.name)}</div>
                ${c.notes ? `<div class="cue-notes">${escapeHtml(c.notes)}</div>` : ''}
              </td>
              <td><span class="${typeClass}">${icon} ${escapeHtml(safeType.toUpperCase())}</span></td>
              <td><span style="font-weight:700; color:#38bdf8;">${outPrefix}L${escapeHtml(c.layer)}</span></td>
              <td style="font-family:ui-monospace, monospace;">${formatTime(c.duration)}</td>
              <td style="font-family:ui-monospace, monospace; color:#94a3b8;">${escapeHtml(c.fade_in || 0)}s / ${escapeHtml(c.fade_out || 0)}s</td>
              <td style="font-size:11px; color:#a1a1aa;">${followTxt}</td>
            </tr>
          `;
        });
        tb.innerHTML = html;
      }
    }

    function setOnline(online) {
      const b = document.getElementById('connBadge');
      const t = document.getElementById('connText');
      if (online) {
        b.classList.remove('offline');
        t.textContent = "LIVE SYNC";
      } else {
        b.classList.add('offline');
        t.textContent = "DISCONNESSO";
      }
    }

    function initSSE() {
      if (evtSource) {
        evtSource.close();
      }
      const sseUrl = currentPin ? `/api/events?pin=${encodeURIComponent(currentPin)}` : '/api/events';
      evtSource = new EventSource(sseUrl);
      evtSource.onopen = () => setOnline(true);
      evtSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          updateMonitorUI(data);
        } catch (err) {
          console.error("SSE parse error:", err);
        }
      };
      evtSource.onerror = () => {
        setOnline(false);
        evtSource.close();
        evtSource = null;
        // Probe status once so a revoked PIN opens the lock screen instead of retrying into lockout
        const probeUrl = currentPin ? `/api/status?pin=${encodeURIComponent(currentPin)}` : '/api/status';
        fetch(probeUrl)
          .then(res => res.json())
          .then(data => {
            if (data.authenticated === false && data.pin_required) {
              currentPin = "";
              sessionStorage.removeItem('blindcue_pin');
              showLockScreen(data.error || "Sessione revocata: reinserisci il PIN");
            } else {
              setTimeout(initSSE, 2500);
            }
          })
          .catch(() => {
            setTimeout(initSSE, 2500);
          });
      };
    }

    // PIN lock controls for monitor
    function showLockScreen(errMsg = "") {
      document.getElementById('pinOverlay').style.display = 'flex';
      if (errMsg) document.getElementById('pinErr').textContent = errMsg;
    }

    function hideLockScreen() {
      document.getElementById('pinOverlay').style.display = 'none';
      document.getElementById('pinErr').textContent = "";
    }

    function renderDots() {
      const dots = document.querySelectorAll('#pinDots .pin-dot');
      dots.forEach((d, idx) => {
        if (idx < enteredBuffer.length) d.classList.add('filled');
        else d.classList.remove('filled');
      });
    }

    function pressPin(digit) {
      if (enteredBuffer.length < 6) {
        enteredBuffer += digit;
        renderDots();
        document.getElementById('pinErr').textContent = "";
        if (enteredBuffer.length === 6) {
          submitPin();
        }
      }
    }

    function clearPin() {
      enteredBuffer = "";
      renderDots();
      document.getElementById('pinErr').textContent = "";
    }

    function submitPin() {
      if (!enteredBuffer) return;
      const testPin = enteredBuffer;
      fetch(`/api/status?pin=${encodeURIComponent(testPin)}`)
        .then(res => res.json())
        .then(data => {
          if (data.authenticated) {
            currentPin = testPin;
            sessionStorage.setItem('blindcue_pin', currentPin);
            hideLockScreen();
            updateMonitorUI(data);
            initSSE();
          } else {
            enteredBuffer = "";
            renderDots();
            document.getElementById('pinErr').textContent = data.error || "PIN errato";
          }
        })
        .catch(() => {
          document.getElementById('pinErr').textContent = "Errore di connessione alla regia";
        });
    }

    // Initial load check
    const statusUrl = currentPin ? `/api/status?pin=${encodeURIComponent(currentPin)}` : '/api/status';
    fetch(statusUrl)
      .then(res => res.json())
      .then(data => {
        if (data.authenticated === false && data.pin_required) {
          showLockScreen();
        } else {
          updateMonitorUI(data);
          setOnline(true);
          initSSE();
        }
      })
      .catch(() => {
        setOnline(false);
        showLockScreen();
      });
  </script>
</body>
</html>
"""


class WebRemoteBridge(QObject):
    """Thread-safe signal dispatcher from HTTP worker threads into the Qt main GUI loop."""

    go_requested = Signal()
    panic_requested = Signal()
    blackout_requested = Signal()
    pause_toggle_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    next_cue_requested = Signal()
    prev_cue_requested = Signal()
    cue_go_requested = Signal(object)           # cue id or index
    cue_select_requested = Signal(object)       # cue id or index


class _ThreadingHttpServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, controller: WebRemoteServer):
        """Threaded HTTP server keeping a reference to the remote controller."""
        super().__init__(server_address, RequestHandlerClass)
        self.controller = controller


class _BlindCueHttpRequestHandler(http.server.BaseHTTPRequestHandler):
    """Handles HTTP requests, REST actions, and SSE (Server-Sent Events) live streaming."""

    # Protect request threads against Slowloris / half-open mobile Wi-Fi drops
    timeout = 10

    @property
    def controller(self) -> WebRemoteServer:
        """Return the server instance this request handler belongs to."""
        return self.server.controller

    def log_message(self, format: str, *args: Any) -> None:
        """Silence the default stderr access log; BlindCue logs via ``logger``."""
        # Keep console clean; log only at debug level
        logger.debug("[WEB] " + (format % args))

    def _write_body(self, data: bytes) -> bool:
        """Write a response body tolerating clients that vanish mid-response."""
        try:
            self.wfile.write(data)
            return True
        except OSError as exc:
            logger.debug("[WEB] Client disconnected during response: %s", exc)
            return False

    def _is_authenticated(self) -> tuple[bool, str]:
        if not self.controller.is_pin_required():
            return True, ""
        client_ip = self.client_address[0]

        # 1. Check Header X-BlindCue-PIN
        hdr_pin = self.headers.get("X-BlindCue-PIN", "").strip()
        if hdr_pin:
            return self.controller.check_pin(hdr_pin, client_ip)

        # 2. Check query parameter ?pin= (properly URL-decoded)
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.query:
            params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
            pin_vals = params.get("pin")
            if pin_vals:
                cand = pin_vals[0].strip()
                return self.controller.check_pin(cand, client_ip)

        return False, "PIN di regia richiesto"

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Respond cleanly to CORS preflight requests from mobile/tablet browsers."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-BlindCue-PIN")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        """Serve the remote page, the REST state snapshot and the SSE stream."""
        path = self.path.split("?")[0].rstrip("/")
        if path in ("", "/"):
            self._serve_html()
        elif path in ("/monitor", "/regia", "/director", "/view"):
            self._serve_monitor_html()
        elif path == "/api/status":
            self._serve_status()
        elif path == "/api/events":
            self._serve_sse()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        """Handle remote commands (GO, PANIC, cue selection) sent by the web UI."""
        path = self.path.split("?")[0].rstrip("/")
        if path == "/api/action":
            self._handle_action()
        else:
            self.send_error(404, "Not Found")

    def _serve_html(self) -> None:
        content = _HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self._write_body(content)

    def _serve_monitor_html(self) -> None:
        content = _HTML_MONITOR_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self._write_body(content)

    def _serve_status(self) -> None:
        is_auth, err_msg = self._is_authenticated()
        if not is_auth:
            # Send locked status payload
            resp_data = {
                "authenticated": False,
                "pin_required": True,
                "error": err_msg,
                "show_title": "BlindCUE (Protetto)",
                "cues": [],
            }
        else:
            resp_data = self.controller.get_state_snapshot()
            resp_data["authenticated"] = True
            resp_data["pin_required"] = self.controller.is_pin_required()

        data = json.dumps(resp_data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self._write_body(data)

    def _serve_sse(self) -> None:
        """Stream real-time updates to mobile clients via Server-Sent Events."""
        is_auth, _ = self._is_authenticated()
        if not is_auth:
            self.send_error(401, "Unauthorized - PIN Required")
            return

        client_queue: queue.Queue = queue.Queue(maxsize=30)
        if not self.controller.register_sse_client(client_queue):
            self.send_error(503, "Too Many SSE Clients")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Send initial full state immediately
        try:
            init_state = self.controller.get_state_snapshot()
            init_state["authenticated"] = True
            init_state["pin_required"] = self.controller.is_pin_required()
            msg = f"data: {json.dumps(init_state)}\n\n".encode()
            self.wfile.write(msg)
            self.wfile.flush()
        except Exception:
            logger.debug("[WEB] SSE handshake failed for %s", self.client_address[0], exc_info=True)
            self.controller.unregister_sse_client(client_queue)
            return

        try:
            while self.controller.is_running():
                try:
                    payload = client_queue.get(timeout=10.0)
                except queue.Empty:
                    # Heartbeat comment to keep connection alive across mobile NAT/Wi-Fi
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    continue
                if payload is _SSE_CLOSE:
                    break
                body = payload if isinstance(payload, str) else json.dumps(payload)
                self.wfile.write(f"data: {body}\n\n".encode())
                self.wfile.flush()
        except OSError as exc:
            logger.debug("[WEB] SSE client %s disconnected: %s", self.client_address[0], exc)
        finally:
            # Explicitly close the underlying TCP socket so EventSource clients
            # receive immediate EOF on revoke/stop instead of waiting on keep-alive.
            self.close_connection = True
            self.controller.unregister_sse_client(client_queue)

    def _handle_action(self) -> None:
        is_auth, err_msg = self._is_authenticated()
        if not is_auth:
            resp_err = json.dumps({"ok": False, "error": "unauthorized", "message": err_msg}).encode("utf-8")
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_err)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self._write_body(resp_err)
            return

        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            self.send_error(400, "Invalid Content-Length")
            return
        if length < 0 or length > MAX_BODY_SIZE:
            self.send_error(413, "Payload Too Large")
            return
        try:
            raw_body = self.rfile.read(min(length, MAX_BODY_SIZE))
            data = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            self.send_error(400, f"Malformed JSON: {exc}")
            return
        if not isinstance(data, dict):
            self.send_error(400, "JSON payload must be an object")
            return

        action = str(data.get("action", "")).lower()
        cue_id = data.get("cue_id")

        client_ip = self.client_address[0]
        self.controller.notify_action_received(action, cue_id, client_ip)

        bridge = self.controller.bridge
        if action == "go":
            bridge.go_requested.emit()
        elif action == "panic":
            bridge.panic_requested.emit()
        elif action == "blackout":
            bridge.blackout_requested.emit()
        elif action == "pause_toggle":
            bridge.pause_toggle_requested.emit()
        elif action == "pause":
            bridge.pause_requested.emit()
        elif action == "resume":
            bridge.resume_requested.emit()
        elif action == "next":
            bridge.next_cue_requested.emit()
        elif action == "prev":
            bridge.prev_cue_requested.emit()
        elif action == "cue_go" and cue_id is not None:
            bridge.cue_go_requested.emit(cue_id)
        elif action == "select" and cue_id is not None:
            bridge.cue_select_requested.emit(cue_id)

        resp = json.dumps({"ok": True, "action": action}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self._write_body(resp)


class WebRemoteServer:
    """Threaded HTTP and SSE server managing the smartphone/tablet live remote."""

    def __init__(self, port: int = 8080) -> None:
        """Create the HTTP/SSE remote server (started later with ``start``)."""
        self.port = port
        self.bridge = WebRemoteBridge()
        self._httpd: _ThreadingHttpServer | None = None
        self._thread: threading.Thread | None = None
        self._serve_started = threading.Event()
        self._running = False
        self._state_provider: Callable[[], dict[str, Any]] | None = None
        self._sse_clients: set[queue.Queue] = set()
        self._clients_lock = threading.Lock()

        # Security PIN protection (Anti-Burlone)
        self._pin_required: bool = True
        self._pin: str = "4821"
        self._failed_attempts: dict[str, tuple[int, float]] = {}  # ip -> (fails, lockout_until)
        self._auth_lock = threading.Lock()

        self._last_action: str = ""
        self._last_client_ip: str = ""

    def set_pin_protection(self, enabled: bool, pin: str = "4821") -> None:
        """Require a PIN before a remote client can send commands.

        The PIN is checked per session: a successful pairing is remembered for
        the client IP so the operator is not asked again during the show.
        """
        self._pin_required = bool(enabled)
        self._pin = str(pin).strip()

    def is_pin_required(self) -> bool:
        """True when remote commands must present the PIN."""
        return self._pin_required

    def get_pin(self) -> str:
        """Return the PIN currently shown to the operator (QR / dialog)."""
        return self._pin

    def check_pin(self, candidate: str, client_ip: str) -> tuple[bool, str]:
        """Validate a PIN sent by a remote client.

        Returns ``(ok, reason)``; on success the client IP is remembered so
        subsequent requests from the same device skip the PIN prompt.
        """
        if not self._pin_required:
            return True, ""
        now = time.time()
        with self._auth_lock:
            if len(self._failed_attempts) > 256:
                self._failed_attempts = {
                    ip: entry for ip, entry in self._failed_attempts.items()
                    if entry[1] > now
                }
            fails, lockout = self._failed_attempts.get(client_ip, (0, 0.0))
            if fails >= 5:
                if now < lockout:
                    rem = max(1, int(lockout - now))
                    return False, f"Troppi tentativi errati. Blocco temporaneo per {rem}s."
                # Lockout period elapsed: reset strike counter cleanly
                fails = 0

            if hmac.compare_digest(str(candidate).strip(), self._pin):
                self._failed_attempts.pop(client_ip, None)
                return True, ""
            else:
                fails += 1
                lock = now + 30.0 if fails >= 5 else 0.0
                self._failed_attempts[client_ip] = (fails, lock)
                return False, "PIN errato."

    def _close_all_sse_clients(self) -> None:
        """Unblock and drop every active SSE queue immediately."""
        with self._clients_lock:
            clients = list(self._sse_clients)
            self._sse_clients.clear()
        for q in clients:
            try:
                q.put_nowait(_SSE_CLOSE)
            except queue.Full:
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    q.put_nowait(_SSE_CLOSE)
                except queue.Full:
                    pass

    def revoke_all_sessions(self) -> None:
        """Clear failed attempts and immediately terminate active SSE streams to force re-authentication."""
        with self._auth_lock:
            self._failed_attempts.clear()
        self._close_all_sse_clients()

    def set_state_provider(self, provider: Callable[[], dict[str, Any]]) -> None:
        """Register the callback that builds the JSON state snapshot.

        The callback is invoked from the HTTP threads, so it must be
        thread-safe: BlindCue reads the state through Qt signals/locks.
        """
        self._state_provider = provider

    def is_running(self) -> bool:
        """True while the HTTP server thread is accepting connections."""
        return self._running

    def get_connected_clients_count(self) -> int:
        """Number of remote clients currently subscribed to the SSE stream."""
        with self._clients_lock:
            return len(self._sse_clients)

    def get_last_action_info(self) -> str:
        """Human-readable description of the last remote command received."""
        if not self._last_action:
            return "Nessuna azione web ricevuta"
        return f"{self._last_action} da {self._last_client_ip}"

    def register_sse_client(self, client_queue: queue.Queue) -> bool:
        """Subscribe a browser client to the state stream (bounded to MAX_SSE_CLIENTS)."""
        with self._clients_lock:
            if len(self._sse_clients) >= MAX_SSE_CLIENTS:
                logger.warning("[WEB] Rejected SSE client: limit %d reached", MAX_SSE_CLIENTS)
                return False
            self._sse_clients.add(client_queue)
            active = len(self._sse_clients)
        logger.info("[WEB] Mobile client connected (Active: %d)", active)
        return True

    def unregister_sse_client(self, client_queue: queue.Queue) -> None:
        """Drop a browser client that disconnected or timed out."""
        with self._clients_lock:
            self._sse_clients.discard(client_queue)
        logger.info("[WEB] Mobile client disconnected (Active: %d)", self.get_connected_clients_count())

    def broadcast_state(self, state: dict[str, Any] | None = None) -> None:
        """Push real-time state update to all currently connected mobile phones and tablets."""
        payload_src = state if state is not None else self.get_state_snapshot()
        snapshot = dict(payload_src)
        snapshot["authenticated"] = True
        snapshot["pin_required"] = self._pin_required
        try:
            # Pre-serialise once: the payload is immutable, so worker threads never race
            payload = json.dumps(snapshot)
        except (TypeError, ValueError):
            logger.debug("[WEB] State snapshot is not JSON serialisable", exc_info=True)
            return

        with self._clients_lock:
            dead: list[queue.Queue] = []
            for q in self._sse_clients:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead.append(q)
            for d in dead:
                self._sse_clients.discard(d)

    def get_state_snapshot(self) -> dict[str, Any]:
        """Return the latest state dictionary without invoking the provider again."""
        if self._state_provider:
            try:
                return self._state_provider()
            except Exception as exc:
                logger.error("[WEB] Error evaluating state provider: %s", exc)
        return {"show_title": "BlindCue", "is_live": False, "cues": []}

    def notify_action_received(self, action: str, cue_id: Any, client_ip: str) -> None:
        """Record the last command for the status line and the logs."""
        self._last_action = f"{action}" + (f" #{cue_id}" if cue_id is not None else "")
        self._last_client_ip = client_ip
        logger.info("[WEB] Received action '%s' from %s", self._last_action, client_ip)

    def start(self, port: int | None = None) -> bool:
        """Start the threaded HTTP server on the specified port."""
        self.stop()
        if port is not None:
            self.port = port

        try:
            # Bind to 0.0.0.0 (all LAN interfaces)
            self._httpd = _ThreadingHttpServer(("0.0.0.0", self.port), _BlindCueHttpRequestHandler, controller=self)  # noqa: S104
            self._running = True

            self._thread = threading.Thread(target=self._run_server, daemon=True, name="BlindCue-WebServer")
            self._thread.start()
            logger.info("[WEB] Remote Web Server running at http://0.0.0.0:%d (PIN Protected: %s)", self.port, self._pin_required)
            return True
        except Exception as exc:
            logger.error("[WEB] Could not start HTTP server on port %d: %s", self.port, exc)
            self._running = False
            self._httpd = None
            return False

    def _run_server(self) -> None:
        if not self._httpd:
            return
        self._serve_started.set()
        try:
            self._httpd.serve_forever()
        except Exception:
            logger.debug("[WEB] HTTP server loop terminated unexpectedly", exc_info=True)

    def stop(self) -> None:
        """Stop HTTP server and unblock all worker threads immediately."""
        self._running = False
        # Wake and terminate active SSE streams first so handler threads exit promptly
        self._close_all_sse_clients()
        if self._httpd:
            if (self._thread is not None
                    and threading.current_thread() is not self._thread):
                # shutdown() deadlocks unless serve_forever() is already running
                self._serve_started.wait(timeout=2.0)
                try:
                    self._httpd.shutdown()
                except Exception:
                    logger.debug("[WEB] Error shutting down HTTP server", exc_info=True)
                try:
                    self._httpd.server_close()
                except Exception:
                    logger.debug("[WEB] Error closing HTTP socket", exc_info=True)
                # Join the server loop so no orphan thread survives stop()
                self._thread.join(timeout=3.0)
                if self._thread.is_alive():
                    logger.warning("[WEB] HTTP server thread did not terminate within timeout")
            else:
                try:
                    self._httpd.server_close()
                except Exception:
                    logger.debug("[WEB] Error closing HTTP socket", exc_info=True)
            self._httpd = None
        self._thread = None
        self._close_all_sse_clients()
        logger.info("[WEB] Remote Web Server stopped")

    def __del__(self) -> None:
        """Best-effort server shutdown; never raises during interpreter shutdown."""
        try:
            self.stop()
        except Exception:
            logger.debug("[WEB] Error during destructor cleanup", exc_info=True)
