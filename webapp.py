#!/usr/bin/env python3
"""
E-Token Webapp — Configuration panel + token history viewer.
Runs alongside etoken_monitor.py (which reads .env and writes tokens.json).
"""

import json
import threading
import asyncio
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from etoken_monitor import run_monitor

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"
TOKENS_FILE = BASE_DIR / "tokens.json"

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_env() -> dict:
    """Parse .env into a dict, preserving all keys."""
    config = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


def write_env(config: dict):
    """Write dict back to .env (overwrites)."""
    lines = [f"{k}={v}" for k, v in config.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n")


def read_tokens() -> list:
    """Read tokens.json, return list of dicts (newest first)."""
    if not TOKENS_FILE.exists():
        return []
    try:
        tokens = json.loads(TOKENS_FILE.read_text())
    except (json.JSONDecodeError, ValueError):
        return []
    return list(reversed(tokens))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    config = read_env()
    return render_template("index.html", config=config)


@app.route("/config", methods=["POST"])
def save_config():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    trucks = request.form.get("trucks", "").strip()
    material = request.form.get("material", "GOODEARTH").strip()
    cycle_interval = request.form.get("cycle_interval", "30").strip()
    start_time = request.form.get("start_time", "").strip()

    config = read_env()
    config["ETOKEN_USERNAME"] = username
    config["ETOKEN_PASSWORD"] = password
    config["TRUCK_NO"] = trucks
    config["MATERIAL"] = material
    config["CYCLE_INTERVAL"] = cycle_interval
    config["START_TIME"] = start_time
    write_env(config)
    return jsonify({"status": "ok"})


@app.route("/tokens")
def get_tokens():
    tokens = read_tokens()
    # Only return entries with a non-empty token
    successful = [t for t in tokens if t.get("token")]
    return jsonify(successful)


@app.route("/tokens/clear", methods=["POST"])
def clear_tokens():
    if TOKENS_FILE.exists():
        TOKENS_FILE.write_text("[]")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Monitor control
# ---------------------------------------------------------------------------

_stop_event = None
_monitor_thread = None


def _run_monitor_thread():
    """Target function for the monitor background thread."""
    global _stop_event
    _stop_event = threading.Event()
    # Reload .env values fresh each time the monitor starts
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE, override=True)
    asyncio.run(run_monitor(headless=True, stop_event=_stop_event))


@app.route("/monitor/start", methods=["POST"])
def monitor_start():
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        return jsonify({"status": "already_running"})
    _monitor_thread = threading.Thread(target=_run_monitor_thread, daemon=True)
    _monitor_thread.start()
    return jsonify({"status": "started"})


@app.route("/monitor/stop", methods=["POST"])
def monitor_stop():
    global _stop_event
    if _stop_event:
        _stop_event.set()
    return jsonify({"status": "stopped"})


@app.route("/monitor/status")
def monitor_status():
    running = _monitor_thread is not None and _monitor_thread.is_alive()
    return jsonify({"running": running})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
