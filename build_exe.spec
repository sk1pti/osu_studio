# -*- mode: python ; coding: utf-8 -*-
# Сборка папкой (onedir): pyinstaller build_exe.spec -> dist\osu_studio\osu_studio.exe
block_cipher = None

a = Analysis(
    ["run_studio.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy.tests", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="osu_studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX часто ломает Qt и ловится антивирусами
    runtime_tmpdir=None,
    console=False,      # без чёрного окна консоли
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="osu_studio",   # результат: dist\osu_studio\ (exe + библиотеки)
)
