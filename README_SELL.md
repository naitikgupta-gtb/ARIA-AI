# ARIA — HUD Frontend + Packaging Guide

## What this is

A browser-based HUD frontend (the "Jarvis-style" 3-column dashboard —
status core, reactive voice orb, tool log) wired to your existing
`tools.py` and Gemini Live logic, running as **one process**:

```
aria_app/
├── server.py         # Flask + Socket.IO — serves the HUD, runs the engine
├── engine_web.py      # your aria_engine.py logic, emits over Socket.IO
├── launcher.py          # opens server.py in a native window (pywebview) — build this into the .exe
├── tools.py               # unchanged — copied from your upload
├── prompt.py                # unchanged — copied from your upload
├── static/
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── requirements.txt
└── build_exe.bat
```


## Run it in dev mode

```bash
pip install -r requirements.txt
python app.py
set api key in setting of aria frontend 
```

Open `http://127.0.0.1:8765` in a browser. Click **ENGAGE** to start
the voice engine — the core will animate with your mic level, the
console fills with the live transcript, and every tool call from
`tools.py` shows up in the Tool Activity panel.

## Package it as one .exe

```bash
build_exe.bat
```

## API key model: each customer uses their own key

Every install of ARIA now manages its own Gemini API key, entered
through the app itself — nobody's key is baked into the .exe, and you
never see or handle a customer's key.

**First run:** the HUD checks `/api/key/status`. No key yet → the
Settings modal opens automatically, ENGAGE stays disabled, and the
core shows `SETUP REQUIRED`. The customer pastes their own Gemini key
(with a link straight to Google AI Studio to get one) and clicks
**Save key**.

**Where it's stored:** `config_store.py` writes it to the OS
credential store via `keyring` (Windows Credential Manager / macOS
Keychain / Linux Secret Service) — not a plain file, not inside the
app bundle. If `keyring` has no usable backend on that machine, it
falls back to a JSON file under the user's own app-data folder
(`%APPDATA%\ARIA\config.json` on Windows); flag to customers that this
fallback path is unencrypted if they're on a shared machine.

**Changing the key later:** the ⚙ icon in the header reopens the
modal any time, showing a masked preview (`••••••1234`) of what's
currently saved.

**Your own dev/testing:** setting the `ARIA_API_KEY` environment
variable still works and takes priority over whatever's saved locally
— useful so your own key isn't sitting in the credential store on your
dev machine.

This means non-technical buyers do need to get their own Gemini API
key (Google AI Studio, free tier available) — there's no way around a
customer needing *some* credential when you're not proxying the calls
yourself. If you'd rather meter/charge for usage instead of customers
managing their own key and Gemini billing, that means routing calls
through a server you control with per-customer license keys — a
bigger build, happy to spec it out if you want to go that route later.

## Troubleshooting: stuck in connecting → disconnected → connecting

This means the engine is reaching `_session()` and failing before (or
right as) it gets a reply from Gemini — it then retries forever. The
actual reason is not hidden; two places show it:

1. **The terminal you ran `python server.py` in** — every failed
   attempt now prints the exception type, message, and full traceback.
   This is the most reliable place to look.
2. **The HUD's Session Core → Memory Timeline panel** — shows
   `Status → disconnected: <reason>` for each retry (truncated
   compared to the terminal, but often enough).

Most common causes, roughly in order of likelihood:

- **Invalid or expired API key.** If you pasted an old/revoked key
  (including the one that leaked earlier in this project), every
  connection attempt fails auth immediately. Reopen Settings (⚙) and
  paste a fresh key from https://aistudio.google.com/apikey.
- **The preview model isn't enabled for your key.** `engine_web.py`
  targets `models/gemini-2.5-flash-native-audio-preview-12-2025` —
  a preview model that some API keys/projects don't have access to.
  If the terminal shows something like a 403, "not found", or the
  connection closing right after the setup message is sent, this is
  likely it. Check model availability for your key in AI Studio, or
  swap the `"model"` value in `engine_web.py`'s `SETUP` dict for a
  model your key can reach.
- **No internet path to `generativelanguage.googleapis.com`** —
  corporate firewall, VPN, or antivirus blocking outbound
  WebSocket/TLS traffic on port 443 to that host.
- **No microphone available.** Less likely to produce this exact
  symptom (it fails after connecting), but if `sounddevice` can't find
  an input device, that also throws and retries — the terminal
  traceback will say so explicitly (`PortAudioError` or similar).

Paste the terminal traceback if you want help pinning down the exact
cause — the message after the last line ("...Error: ...") is the one
that matters.

## Fixing "Invalid async_mode specified" in the packaged .exe

If `ARIA.exe` crashes on launch with a traceback ending in
`ValueError: Invalid async_mode specified` (inside
`flask_socketio`/`engineio`), it built successfully but PyInstaller
missed some dynamically-imported modules that Flask-SocketIO and
`keyring` load at runtime rather than at import time — PyInstaller's
static analysis can't see those.

Fixed already in the updated `build_exe.bat`, which now adds:
```
--collect-all engineio --collect-all socketio --collect-all flask_socketio --collect-all keyring
--hidden-import engineio.async_drivers.threading --hidden-import keyring.backends.Windows
```
Just rerun `build_exe.bat` (delete the old `build\` and `dist\` folders
first so PyInstaller doesn't reuse a stale cache) and the new
`ARIA.exe` should open clean.

If you ever hit a similar crash after changing dependencies, the
pattern to look for is the same: a `ModuleNotFoundError` or a library
falling back to "no backend available" inside a frozen .exe almost
always means PyInstaller needs an explicit `--hidden-import` or
`--collect-all` for that package, since it can't detect imports the
library does dynamically at runtime.

## Adding your own logo/icon

1. Get a square logo image (512×512 or larger, PNG with transparent
   background works best).
2. Convert it to a proper multi-resolution `.ico`:
   ```
   pip install pillow
   python make_icon.py your_logo.png
   ```
   This writes `aria.ico` in the same folder.
3. Make sure `aria.ico` sits next to `build_exe.bat` (it's already
   wired up with `--icon "aria.ico"`).
4. Delete the old `build\` and `dist\` folders, then rerun
   `build_exe.bat`. The new `ARIA.exe` will use your icon for the .exe
   file itself, the taskbar, and the app window.

## Rebranding for sale

Swap these before shipping to customers:
- `static/index.html` — `<title>` and the `.brand-name` text
- `static/css/style.css` — the `:root` color tokens if you want a
  different palette than the cyan HUD theme
- `launcher.py` — the window title string
- `aria.ico` — your own logo (see above)
