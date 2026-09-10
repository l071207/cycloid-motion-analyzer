# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH)
datas = [
    (str(project_root / "cycloid_analyzer" / "samples" / "demo_background.png"), "cycloid_analyzer/samples"),
    (str(project_root / "cycloid_analyzer" / "samples" / "demo_movement_trace.json"), "cycloid_analyzer/samples"),
]

block_cipher = None

a = Analysis(
    ["cycloid_analyzer/main.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CycloidMotionAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CycloidMotionAnalyzer",
)
