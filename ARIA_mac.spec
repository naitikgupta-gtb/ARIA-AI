# -*- mode: python ; coding: utf-8 -*-
# ARIA_mac.spec — build this ON a Mac (PyInstaller doesn't cross-compile;
# a Windows machine can only ever produce a .exe, never a .app, and
# vice versa). Run with: pyinstaller ARIA_mac.spec
#
# Before building, generate an .icns icon (macOS doesn't use .ico):
#   1. Put a 1024x1024 PNG at branding/aria_logo_1024.png (already there)
#   2. On a Mac, run:
#        mkdir aria.iconset
#        sips -z 16 16     branding/aria_logo_1024.png --out aria.iconset/icon_16x16.png
#        sips -z 32 32     branding/aria_logo_1024.png --out aria.iconset/icon_16x16@2x.png
#        sips -z 32 32     branding/aria_logo_1024.png --out aria.iconset/icon_32x32.png
#        sips -z 64 64     branding/aria_logo_1024.png --out aria.iconset/icon_32x32@2x.png
#        sips -z 128 128   branding/aria_logo_1024.png --out aria.iconset/icon_128x128.png
#        sips -z 256 256   branding/aria_logo_1024.png --out aria.iconset/icon_128x128@2x.png
#        sips -z 256 256   branding/aria_logo_1024.png --out aria.iconset/icon_256x256.png
#        sips -z 512 512   branding/aria_logo_1024.png --out aria.iconset/icon_256x256@2x.png
#        sips -z 512 512   branding/aria_logo_1024.png --out aria.iconset/icon_512x512.png
#        cp branding/aria_logo_1024.png aria.iconset/icon_512x512@2x.png
#        iconutil -c icns aria.iconset -o branding/aria.icns
from PyInstaller.utils.hooks import collect_all

datas = [('static', 'static'), ('tools.py', '.'), ('prompt.py', '.'), ('config.py', '.'), ('modules', 'modules')]
binaries = []
hiddenimports = [
    'engineio.async_drivers.threading', 'pywhatkit', 'pyautogui', 'bs4', 'requests',
    'sounddevice', 'pyperclip', 'send2trash',
    # pywebview's macOS backend (Cocoa/WKWebView via pyobjc) — the Windows
    # equivalents (edgechromium/winforms/mshtml/clr) don't exist here.
    'webview.platforms.cocoa',
    'keyring.backends.macOS',
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
    [],
    exclude_binaries=True,
    name='ARIA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # DEBUG BUILD: console=True shows startup errors in Terminal instead of
    # failing silently. Flip to False once confirmed working, then rebuild.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='ARIA',
)

app = BUNDLE(
    coll,
    name='ARIA.app',
    icon='branding/aria.icns',  # generate this first — see instructions above
    bundle_identifier='com.aria.assistant',
    info_plist={
        'NSMicrophoneUsageDescription': 'ARIA needs microphone access for voice commands.',
        'NSCameraUsageDescription': 'ARIA needs camera access if you use vision features.',
        'CFBundleShortVersionString': '1.1.0',
    },
)
