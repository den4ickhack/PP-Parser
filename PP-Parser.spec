# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['PP-Parser.py'],
    pathex=[],
    binaries=[],
    datas=[('service_providers.txt', '.'), ('employee_groups.json', '.')],
    hiddenimports=['selenium.webdriver.common.by', 'selenium.webdriver.chrome.service', 'selenium.webdriver.support.ui', 'selenium.webdriver.support.expected_conditions', 'bs4', 'lxml', 'urllib.parse'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas', 'numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PP-Parser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Denis\\Downloads\\1.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PP-Parser',
)
