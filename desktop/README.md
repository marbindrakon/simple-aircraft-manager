# Desktop Installer (Windows)

This directory contains the Windows desktop packaging for Simple Aircraft Manager — a per-user installer that bundles the Django app with a Python runtime, a `pystray` tray launcher, and a SQLite database under `%LOCALAPPDATA%\SimpleAircraftManager\`.

## Building the installer

Authoring happens on Linux; the build itself runs on Windows. The split lets you keep iterating on `desktop/*.py` from your normal dev box and only hop to a Windows VM when you need to validate or ship.

### Prerequisites (on the Windows VM)

- Windows 11 (or 10).
- Python 3.12 from python.org (the launcher in `py.exe` matters for the build script's `py -3.12 -m venv` line).
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) — install with the "Add iscc to PATH" option, or add `C:\Program Files (x86)\Inno Setup 6\` to PATH manually.
- Git for Windows.

### Build steps

```powershell
git clone <repo> simple-aircraft-manager
cd simple-aircraft-manager
git checkout <feature-branch>
.\desktop\build-windows.ps1
```

The script:

1. Creates a venv at `.\venv\` if missing.
2. Installs `requirements.txt` and `requirements-desktop.txt`.
3. Runs `collectstatic` into `build\staticfiles\`.
4. Runs PyInstaller (`desktop\sam-windows.spec`) → `dist\SimpleAircraftManager\`.
5. Runs Inno Setup → `Output\SimpleAircraftManagerSetup-<version>.exe`.

If any step fails, fix the error and rerun — the script is idempotent.

## Smoke-test checklist

Run after each successful build on a clean Windows 11 VM. Items grouped by area; check off as you go.

### Build & basic startup

- [ ] `dist\SimpleAircraftManager\sam.exe` launches without errors when `%LOCALAPPDATA%\SimpleAircraftManager\config.ini` exists.
- [ ] System tray icon appears.
- [ ] Default browser opens to `http://127.0.0.1:8765/` (or fallback port) and the page loads cleanly — no connection-refused.
- [ ] Dashboard renders with PatternFly CSS and Alpine.js working (WhiteNoise serving static under `DEBUG=False`).
- [ ] User is auto-logged-in only when `config.ini` explicitly contains `mode = disabled`.
- [ ] Create one aircraft → reload → it persists.
- [ ] Upload a logbook scan → view it → file loads (media-serving route works under `DEBUG=False`).
- [ ] Tray "Quit" cleanly shuts down (process exits, port released within 10s, `instance.lock` released).
- [ ] Restart app → previous aircraft + uploaded file still there.

### Installer behavior

- [ ] `iscc desktop\installer.iss` produces `Output\SimpleAircraftManagerSetup-*.exe`.
- [ ] Install **without UAC prompt** (per-user install, `PrivilegesRequired=lowest`).
- [ ] Install with **"Require login"** + Anthropic key: completes, shortcut works, login page appears, entered creds work.
- [ ] Install with **"No login"** on a fresh machine: shortcut works, no auth prompt, dashboard loads.
- [ ] Install on a Windows account whose username contains a non-ASCII character (e.g. `andré`): paths resolve, app launches.
- [ ] Uninstall: removes `%LOCALAPPDATA%\Programs\SimpleAircraftManager\`, leaves `%LOCALAPPDATA%\SimpleAircraftManager\` intact, leaves Credential Manager entry intact.

### Reinstall scenarios

Cross-mode reinstall (no-auth ↔ require-login) is **unsupported** — the previous user's aircraft remain owned by the old user. Document, do not test.

- [ ] Reinstall same auth mode over existing data: data preserved, app works.
- [ ] Reinstall with an Anthropic key: AI logbook import works on a sample PDF.
- [ ] Reinstall without entering a key (over an install that had one): existing keyring entry reused, AI features still work.
- [ ] Reinstall after manually clearing the Credential Manager `SimpleAircraftManager` entry (Control Panel → User Accounts → Credential Manager → Generic Credentials): AI features fail gracefully.

### Robustness

- [ ] Double-click the shortcut twice in quick succession: second instance opens browser to existing port, exits cleanly.
- [ ] Force-kill via Task Manager during a write, then relaunch: data intact, no stale lock blocks startup, the next launch's backup includes the just-committed write (verifies WAL backup correctness).
- [ ] Quit via tray while a logbook AI import is mid-flight: on relaunch the `ImportJob` row is marked `failed`, no orphan staging dirs.
- [ ] Launch with no internet (offline) and no Anthropic key: app starts, AI features silently absent.
- [ ] Launch with no internet and an Anthropic key: app starts; AI features show network errors when invoked, no crash.

### SmartScreen (informational)

- [ ] Confirm SmartScreen "Don't run / More info → Run anyway" UX is acceptable for unsigned binaries (Day-2: code signing).

## Manual recovery

### "I forgot my password" / "Bad credentials saved"

In required-login mode, the password lives only in Django's auth_user table (hashed). To reset:

1. Quit the app via the tray.
2. Open a terminal and run:
   ```cmd
   "%LOCALAPPDATA%\Programs\SimpleAircraftManager\sam.exe" --reset-password
   ```
   (Day-2 feature; for now, manually delete `%LOCALAPPDATA%\SimpleAircraftManager\db.sqlite3`, accept the data loss, and reinstall.)

### "Database is corrupted"

The launcher writes rotating backups of `db.sqlite3` before every migrate. To restore:

1. Quit the app.
2. Open `%LOCALAPPDATA%\SimpleAircraftManager\` in Explorer.
3. Rename `db.sqlite3` → `db.sqlite3.broken`.
4. Rename the most recent `db.sqlite3.bak.0` → `db.sqlite3`.
5. Relaunch.

### "I want to reset everything"

1. Uninstall via Add/Remove Programs.
2. Delete `%LOCALAPPDATA%\SimpleAircraftManager\` in Explorer.
3. Open Windows Credential Manager → User Accounts → Credential Manager → Generic Credentials → remove `SimpleAircraftManager`.
4. Reinstall.

## Architecture pointers

- Spec: `docs/superpowers/specs/2026-04-27-windows-desktop-installer-poc-design.md`
- Plan: `docs/superpowers/plans/2026-04-27-windows-desktop-installer-poc.md`
- Settings module: `simple_aircraft_manager/settings_desktop.py`
- All desktop runtime code: `desktop/*.py`
