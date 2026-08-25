# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('static', 'static'), ('tools.py', '.'), ('prompt.py', '.'), ('config.py', '.'), ('modules', 'modules')]
binaries = []
hiddenimports = [
    'engineio.async_drivers.threading', 'keyring.backends.Windows', 'pywhatkit', 'pyautogui',
    'bs4', 'requests', 'sounddevice',
    # pywebview's Windows backend picks one of these at runtime — PyInstaller's
    # static analysis can't see that dynamic import, so it must be listed
    # explicitly or the packaged .exe fails to open a window with no visible error.
    'webview.platforms.edgechromium', 'webview.platforms.winforms', 'webview.platforms.mshtml',
    'clr',
    # These are all imported dynamically (inside functions, not at module
    # top-level) across tools.py/modules/* for volume control, window
    # management, clipboard history, and safe-delete — PyInstaller's static
    # analysis cannot see function-local imports, so without listing them
    # explicitly here those features silently fail in the packaged .exe
    # even though they work fine with `python app.py`.
    'pycaw', 'pycaw.pycaw', 'comtypes', 'comtypes.client',
    'pygetwindow', 'pyperclip', 'send2trash',
]
tmp_ret = collect_all('engineio')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('socketio')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('flask_socketio')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('keyring')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ARIA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # DEBUG BUILD: console=True so a console window opens alongside ARIA and
    # shows any startup traceback. Once ARIA is confirmed launching cleanly,
    # flip this back to console=False for the version you actually ship —
    # see the note at the bottom of RUN_GUIDE.md.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['aria.ico'],
)

