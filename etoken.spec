# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for etoken app."""

import os
import importlib
from PyInstaller.utils.hooks import collect_submodules

playwright_path = os.path.dirname(importlib.import_module('playwright').__file__)

# Collect all playwright submodules for hidden imports
hidden_imports = [
    # playwright._impl.* modules
    *collect_submodules('playwright._impl'),
    # playwright.async_api.* modules
    *collect_submodules('playwright.async_api'),
    # playwright.sync_api.* modules
    *collect_submodules('playwright.sync_api'),
    # Other dependencies
    'dotenv',
    'flask',
    'jinja2.ext',
]

a = Analysis(
    ['webapp.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Templates (read-only, accessed via sys._MEIPASS)
        ('templates', 'templates'),
        # The entire playwright package (driver contains Node.js binary)
        (playwright_path, 'playwright'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# Filter out UPX from all binaries — it corrupts Playwright's Node binary
for bin_item in a.binaries:
    pass  # UPX handled via upx=False below

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='etoken',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # CRITICAL: UPX corrupts Playwright's Node binary
    console=True,  # Keep console for log output
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,  # CRITICAL: UPX corrupts Playwright's Node binary
    name='etoken',
)
