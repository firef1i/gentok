#!/usr/bin/env python3
"""
Utility functions for running under PyInstaller frozen mode.

- Bundled (read-only) resources like templates live in sys._MEIPASS.
- User data (.env, tokens.json, browsers/) lives next to the executable.
"""

import os
import subprocess
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Return True if running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def get_bundled_resource_dir() -> Path:
    """Directory for read-only bundled resources (templates, etc.).

    In frozen mode this is sys._MEIPASS (a temp folder PyInstaller extracts to).
    In dev mode this is the project root (same as get_app_data_dir).
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def get_app_data_dir() -> Path:
    """Directory for user-writable data (.env, tokens.json, browsers/).

    In frozen mode this is the directory containing the executable.
    In dev mode this is the project root.
    """
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_playwright_browsers_path() -> Path:
    """Return the path where Playwright browsers are located.

    In frozen mode, returns the bundled location (sys._MEIPASS / "browsers").
    In dev mode, returns <project_root>/browsers.
    """
    if is_frozen():
        return Path(sys._MEIPASS) / "browsers"
    return get_app_data_dir() / "browsers"


def ensure_browsers_installed():
    """Ensure Playwright Chromium is available.

    In frozen mode, checks for the bundled browser first. If found, sets
    PLAYWRIGHT_BROWSERS_PATH and returns immediately — no download needed.
    Falls back to downloading only when no bundled browser is present.
    """
    browsers_path = get_playwright_browsers_path()
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)

    # Check if chromium is already installed / bundled
    existing = list(browsers_path.glob("chromium-*")) if browsers_path.exists() else []
    if existing:
        return

    # In frozen mode, if no bundled browser found, that's a build problem
    if is_frozen():
        print(f"ERROR: No bundled Chromium found at {browsers_path}")
        print("The application was not built correctly. Please rebuild.")
        sys.exit(1)

    print(f"First run: installing Playwright Chromium browser to {browsers_path} ...")
    print("This is a one-time download (~187 MB). Please wait...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(browsers_path)},
        )
        print("Chromium browser installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install Chromium browser: {e}")
        print("You can manually run: python -m playwright install chromium")
        sys.exit(1)
