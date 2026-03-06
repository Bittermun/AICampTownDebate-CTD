#!/usr/bin/env python3
"""
Single-round streaming viewer for tournament transcripts.

Runs a local HTTP server with:
- /       : static visual UI
- /events : Server-Sent Events (SSE) replay stream
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Round Stream Viewer</title>
  <style>
    :root {
      --bg: #f4f1ea;
      --ink: #1f1f1f;
      --muted: #6e665a;
      --panel: #fffaf2;
      --line: #d9ccb8;
      --a: #2364aa;
      --b: #d1495b;
      --good: #2b9348;
      --warn: #ff9f1c;
      --shadow: rgba(31, 31, 31, 0.1);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Aptos", sans-serif;
      background:
        radial-gradient(circle at 15% 20%, rgba(35, 100, 170, 0.08), transparent 40%),
        radial-gradient(circle at 85% 15%, rgba(209, 73, 91, 0.1), transparent 38%),
        radial-gradient(circle at 50% 90%, rgba(255, 159, 28, 0.08), transparent 42%),
        var(--bg);
      color: var(--ink);
    }
    .wrap {
      max-width: 1024px;
      margin: 0 auto;
      padding: 20px 14px 32px;
    }
    .hero {
      background: var(--panel);
      border: 2px solid var(--line);
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 8px 20px var(--shadow);
    }
    .topic {
      font-size: clamp(18px, 2.8vw, 28px);
      margin: 4px 0 8px;
      line-height: 1.2;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
    }
    .status {
      display: inline-block;
      margin-top: 10px;
      padding: 4px 9px;
      border-radius: 999px;
      background: #efe4d4;
      border: 1px solid var(--line);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .02em;
    }
    .grid {
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .card {
      background: var(--panel);
      border: 2px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      min-height: 120px;
      box-shadow: 0 6px 16px var(--shadow);
      position: relative;
      overflow: hidden;
    }
    .name {
      font-size: 12px;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: .08em;
      margin: 0 0 2px;
    }
    .score {
      font-size: clamp(24px, 4.3vw, 44px);
      font-weight: 900;
      margin: 0;
      line-height: 1;
    }
    .bar {
      width: 100%;
      height: 10px;
      margin-top: 10px;
      background: #efe4d4;
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid var(--line);
    }
    .fill {
      height: 100%;
      width: 50%;
      transition: width 380ms ease-out;
    }
    .fill-a { background: linear-gradient(90deg, #2c7ace, var(--a)); }
    .fill-b { background: linear-gradient(90deg, #e05d6d, var(--b)); }
    .pulse {
      animation: pulse 550ms ease-out;
    }
    @keyframes pulse {
      0% { transform: scale(1); }
      35% { transform: scale(1.05); }
      100% { transform: scale(1); }
    }
    .log-wrap {
      margin-top: 14px;
      background: var(--panel);
      border: 2px solid var(--line);
      border-radius: 12px;
      box-shadow: 0 6px 16px var(--shadow);
      overflow: hidden;
    }
    .log-header {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
      font-size: 13px;
      color: var(--muted);
    }
    .btn {
      border: 1px solid var(--line);
      background: #efe4d4;
      padding: 6px 10px;
      border-radius: 8px;
      font-size: 12px;
      cursor: pointer;
      color: var(--ink);
    }
    .btn:hover { filter: brightness(.98); }
    .log {
      list-style: none;
      margin: 0;
      padding: 0;
      max-height: 56vh;
      overflow: auto;
    }
    .entry {
      padding: 10px 12px;
      border-bottom: 1px solid #efe4d4;
      animation: rise 280ms ease-out;
    }
    .entry:last-child { border-bottom: 0; }
    .entry-type {
      font-size: 11px;
      letter-spacing: .07em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 4px;
    }
    .entry-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: baseline;
    }
    .entry-speaker { font-weight: 700; font-size: 14px; }
    .entry-bet { font-size: 12px; color: var(--warn); font-weight: 600; }
    .entry-content {
      margin-top: 6px;
      font-size: 13px;
      white-space: pre-wrap;
      line-height: 1.35;
      color: #2d2b26;
      max-height: 190px;
      overflow: auto;
    }
    .winner {
      margin-top: 14px;
      padding: 10px 12px;
      border-radius: 10px;
      background: #e6f5ec;
      border: 1px solid #b7dec4;
      color: #1f5d35;
      font-weight: 700;
      display: none;
    }
    .diag {
      margin-top: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 10px;
      font-size: 12px;
      color: var(--muted);
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .diag b { color: var(--ink); }
    .confetti {
      position: fixed;
      pointer-events: none;
      inset: 0;
      overflow: hidden;
    }
    .confetti span {
      position: absolute;
      top: -30px;
      font-size: 18px;
      animation: fall linear forwards;
    }
    @keyframes rise {
      from { transform: translateY(6px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    @keyframes fall {
      to { transform: translateY(105vh) rotate(460deg); opacity: .95; }
    }
    @media (max-width: 760px) {
      .grid { grid-template-columns: 1fr; }
      .log { max-height: 52vh; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="meta" id="meta">Waiting for stream...</div>
      <h1 class="topic" id="topic">Round stream</h1>
      <div class="status" id="status">CONNECTING</div>
    </div>

    <div class="grid">
      <section class="card" id="cardA">
        <p class="name" id="nameA">Debater A</p>
        <p class="score" id="scoreA">50%</p>
        <div class="bar"><div class="fill fill-a" id="barA"></div></div>
      </section>
      <section class="card" id="cardB">
        <p class="name" id="nameB">Debater B</p>
        <p class="score" id="scoreB">50%</p>
        <div class="bar"><div class="fill fill-b" id="barB"></div></div>
      </section>
    </div>

    <section class="log-wrap">
      <div class="log-header">
        <span id="turnCounter">0 events</span>
        <button class="btn" id="replayBtn" type="button">Replay</button>
      </div>
      <ul class="log" id="log"></ul>
    </section>
    <div class="winner" id="winnerBanner"></div>
    <div class="diag" id="diagPanel">
      <div>State: <b id="diagState">idle</b></div>
      <div>Last event: <b id="diagLastEvent">none</b></div>
      <div>Server health: <b id="diagHealth">unknown</b></div>
    </div>
  </div>
  <div class="confetti" id="confetti"></div>

  <script>
    const topicEl = document.getElementById("topic");
    const metaEl = document.getElementById("meta");
    const statusEl = document.getElementById("status");
    const nameAEl = document.getElementById("nameA");
    const nameBEl = document.getElementById("nameB");
    const scoreAEl = document.getElementById("scoreA");
    const scoreBEl = document.getElementById("scoreB");
    const barAEl = document.getElementById("barA");
    const barBEl = document.getElementById("barB");
    const cardAEl = document.getElementById("cardA");
    const cardBEl = document.getElementById("cardB");
    const logEl = document.getElementById("log");
    const turnCounterEl = document.getElementById("turnCounter");
    const replayBtn = document.getElementById("replayBtn");
    const winnerBanner = document.getElementById("winnerBanner");
    const confettiRoot = document.getElementById("confetti");
    const diagStateEl = document.getElementById("diagState");
    const diagLastEventEl = document.getElementById("diagLastEvent");
    const diagHealthEl = document.getElementById("diagHealth");

    let source = null;
    let count = 0;
    let streamDone = false;

    const labelType = (kind) => {
      const map = {
        round_start: "ROUND START",
        round_end: "ROUND END",
        argument: "ARGUMENT",
        counter: "COUNTER",
        deliberation: "DELIBERATION",
        judgment: "JUDGMENT",
        payout: "PAYOUT"
      };
      return map[kind] || kind.toUpperCase();
    };

    const cleanContent = (text) => (text || "").replace(/\\*\\*/g, "").trim();

    const setStatus = (text) => { statusEl.textContent = text; };
    const setDiagState = (text) => { diagStateEl.textContent = text; };
    const setDiagHealth = (text) => { diagHealthEl.textContent = text; };
    const stampLastEvent = () => { diagLastEventEl.textContent = new Date().toLocaleTimeString(); };

    const updateScores = (a, b) => {
      const aa = Math.max(0, Math.min(100, Math.round((a || 0.5) * 100)));
      const bb = Math.max(0, Math.min(100, Math.round((b || 0.5) * 100)));
      scoreAEl.textContent = aa + "%";
      scoreBEl.textContent = bb + "%";
      barAEl.style.width = aa + "%";
      barBEl.style.width = bb + "%";
      cardAEl.classList.remove("pulse");
      cardBEl.classList.remove("pulse");
      void cardAEl.offsetWidth;
      cardAEl.classList.add("pulse");
      cardBEl.classList.add("pulse");
    };

    const addEntry = (event) => {
      count += 1;
      turnCounterEl.textContent = count + " events";
      const item = document.createElement("li");
      item.className = "entry";

      const bet = (event.tokens_bet && event.tokens_bet > 0) ? `${event.tokens_bet.toFixed(1)} bet` : "";
      const time = event.ts || "";

      item.innerHTML = `
        <div class="entry-type">${labelType(event.type)}</div>
        <div class="entry-head">
          <span class="entry-speaker">${event.speaker || "System"}</span>
          <span class="entry-bet">${bet} ${time ? " • " + time : ""}</span>
        </div>
        <div class="entry-content">${cleanContent(event.content || "")}</div>
      `;
      logEl.prepend(item);
    };

    const launchConfetti = () => {
      confettiRoot.innerHTML = "";
      const icons = ["🎉", "✨", "🏆", "🎊"];
      for (let i = 0; i < 36; i += 1) {
        const s = document.createElement("span");
        s.textContent = icons[i % icons.length];
        s.style.left = Math.round(Math.random() * 100) + "vw";
        s.style.animationDuration = (2.2 + Math.random() * 1.8).toFixed(2) + "s";
        s.style.animationDelay = (Math.random() * 0.55).toFixed(2) + "s";
        confettiRoot.appendChild(s);
      }
      setTimeout(() => { confettiRoot.innerHTML = ""; }, 4300);
    };

    const resetView = () => {
      count = 0;
      streamDone = false;
      setDiagState("idle");
      diagLastEventEl.textContent = "none";
      logEl.innerHTML = "";
      turnCounterEl.textContent = "0 events";
      winnerBanner.style.display = "none";
      winnerBanner.textContent = "";
      updateScores(0.5, 0.5);
    };

    const startStream = () => {
      if (source) {
        source.close();
      }
      resetView();
      setStatus("CONNECTING");
      setDiagState("connecting");
      source = new EventSource(`/events?nonce=${Date.now()}`);

      source.onopen = () => {
        setStatus("LIVE");
        setDiagState("open");
      };

      source.onmessage = (msg) => {
        stampLastEvent();
        const event = JSON.parse(msg.data);
        if (event.type === "round_start") {
          topicEl.textContent = event.topic || "Round stream";
          metaEl.textContent = `${event.tournament_id || "tournament"} • round ${event.round_id || "?"} • ${event.total_turns || 0} turns`;
          if (event.debater_a) nameAEl.textContent = event.debater_a;
          if (event.debater_b) nameBEl.textContent = event.debater_b;
          addEntry(event);
          return;
        }

        if (event.type === "judgment") {
          updateScores(event.confidence_a, event.confidence_b);
        }
        addEntry(event);

        if (event.type === "round_end") {
          streamDone = true;
          setStatus("COMPLETE");
          setDiagState("complete");
          if (event.winner) {
            winnerBanner.style.display = "block";
            winnerBanner.textContent = `Winner: ${event.winner} | Final confidence A=${Math.round((event.confidence_a || 0) * 100)}% B=${Math.round((event.confidence_b || 0) * 100)}%`;
            launchConfetti();
          }
          if (source) {
            source.close();
          }
        }
      };

      source.onerror = () => {
        if (!streamDone) {
          setStatus("SERVER OFFLINE");
          setDiagState("error");
        }
      };
    };

    const healthPoll = async () => {
      try {
        const r = await fetch(`/health?ts=${Date.now()}`, { cache: "no-store" });
        if (!r.ok) {
          setDiagHealth(`bad (${r.status})`);
          return;
        }
        const body = await r.json();
        setDiagHealth(body.status || "ok");
      } catch {
        setDiagHealth("unreachable");
      }
    };

    setInterval(healthPoll, 2000);
    healthPoll();
    replayBtn.addEventListener("click", startStream);
    startStream();
  </script>
</body>
</html>
"""


@dataclass
class ViewerConfig:
    transcript_path: Path
    round_id: int
    speed: float


def _round_winner(round_data: dict[str, Any], debater_a: str, debater_b: str) -> str:
    conf_a = float(round_data.get("confidence_a", 0.0) or 0.0)
    conf_b = float(round_data.get("confidence_b", 0.0) or 0.0)
    if conf_a > conf_b:
        return debater_a
    if conf_b > conf_a:
        return debater_b
    return "TIE"


def _format_time() -> str:
    return time.strftime("%H:%M:%S")


def load_round_events(config: ViewerConfig) -> list[dict[str, Any]]:
    data = json.loads(config.transcript_path.read_text(encoding="utf-8"))
    rounds = data.get("rounds", [])
    if not rounds:
        raise ValueError("Transcript has no rounds.")

    selected = None
    for item in rounds:
        if int(item.get("round_id", -1)) == config.round_id:
            selected = item
            break
    if selected is None:
        available = [int(r.get("round_id", -1)) for r in rounds]
        raise ValueError(f"Round {config.round_id} not found. Available rounds: {available}")

    cfg = data.get("config", {})
    debater_a = str(cfg.get("debater_a", "Debater A"))
    debater_b = str(cfg.get("debater_b", "Debater B"))

    events: list[dict[str, Any]] = [{
        "type": "round_start",
        "speaker": "System",
        "content": "Streaming replay started.",
        "topic": selected.get("topic", ""),
        "round_id": selected.get("round_id"),
        "total_turns": len(selected.get("turns", [])),
        "tournament_id": data.get("tournament_id", ""),
        "debater_a": debater_a,
        "debater_b": debater_b,
        "ts": _format_time(),
    }]

    for turn in selected.get("turns", []):
        events.append({
            "type": turn.get("type", "unknown"),
            "speaker": turn.get("speaker", "Unknown"),
            "content": turn.get("content", ""),
            "tokens_bet": float(turn.get("tokens_bet", 0.0) or 0.0),
            "confidence_a": turn.get("confidence_a"),
            "confidence_b": turn.get("confidence_b"),
            "ts": _format_time(),
        })

    events.append({
        "type": "round_end",
        "speaker": "System",
        "content": (
            f"Round complete. Tokens awarded: "
            f"A={float(selected.get('tokens_awarded_a', 0.0) or 0.0):.1f}, "
            f"B={float(selected.get('tokens_awarded_b', 0.0) or 0.0):.1f}"
        ),
        "winner": _round_winner(selected, debater_a, debater_b),
        "confidence_a": float(selected.get("confidence_a", 0.0) or 0.0),
        "confidence_b": float(selected.get("confidence_b", 0.0) or 0.0),
        "ts": _format_time(),
    })

    return events


def _delay_for(event_type: str, speed: float) -> float:
    base = {
        "round_start": 0.5,
        "argument": 1.0,
        "counter": 0.95,
        "deliberation": 0.9,
        "judgment": 1.35,
        "payout": 0.8,
        "round_end": 0.5,
    }.get(event_type, 0.9)
    return max(0.08, base / max(0.1, speed))


def build_handler(events: list[dict[str, Any]], speed: float):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = HTML_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if parsed.path == "/health":
                payload = json.dumps({"status": "ok", "ts": int(time.time())}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if parsed.path == "/events":
                _ = parse_qs(parsed.query)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                for event in events:
                    payload = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")
                    try:
                        self.wfile.write(payload)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    time.sleep(_delay_for(str(event.get("type", "")), speed))
                return

            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args):  # noqa: A003
            return

    return Handler


def _pick_default_transcript(repo_root: Path) -> Path:
    candidates = sorted(
        repo_root.glob("logs/**/*_transcript.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    return repo_root / "logs" / "tournament_results_transcript.json"


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Stream one tournament round in a local browser UI.")
    parser.add_argument(
        "--transcript",
        type=Path,
        default=_pick_default_transcript(repo_root),
        help="Transcript JSON path (default: latest *_transcript.json in logs).",
    )
    parser.add_argument("--round-id", type=int, default=1, help="Round id to replay.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host bind address.")
    parser.add_argument("--port", type=int, default=8787, help="Port.")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier. Example: 2.0 = 2x.")
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Auto-open the viewer URL in your default browser.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    transcript = args.transcript.resolve()
    if not transcript.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript}")

    config = ViewerConfig(transcript_path=transcript, round_id=args.round_id, speed=args.speed)
    events = load_round_events(config)
    handler_cls = build_handler(events, speed=config.speed)
    server = ThreadingHTTPServer((args.host, args.port), handler_cls)

    url = f"http://{args.host}:{args.port}"
    print(f"Round stream viewer ready: {url}")
    print(f"Transcript: {transcript}")
    print(f"Round: {args.round_id} | Events: {len(events)} | Speed: {args.speed}x")
    print("Press Ctrl+C to stop.")

    if args.open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping viewer...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
