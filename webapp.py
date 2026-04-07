#!/usr/bin/env python3
"""
E-Token Webapp — Configuration panel + token history viewer.
Runs alongside etoken_monitor.py (which reads .env and writes tokens.json).
"""

import json
import os
import threading
import asyncio
from flask import Flask, render_template, request, jsonify
from etoken_monitor import run_monitor
from frozen_utils import is_frozen, get_app_data_dir, get_bundled_resource_dir, ensure_browsers_installed

APP_DATA_DIR = get_app_data_dir()
ENV_FILE = APP_DATA_DIR / ".env"
TOKENS_FILE = APP_DATA_DIR / "tokens.json"

# In frozen mode, templates are inside sys._MEIPASS; otherwise use default
_template_folder = str(get_bundled_resource_dir() / "templates") if is_frozen() else "templates"
app = Flask(__name__, template_folder=_template_folder)

# Set Playwright browsers path when running frozen
if is_frozen():
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(APP_DATA_DIR / "browsers")


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
    if is_frozen():
        ensure_browsers_installed()
        app.run(debug=False, port=5000)
    else:
        app.run(debug=True, port=5000)
