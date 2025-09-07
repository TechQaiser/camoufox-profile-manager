
# Camoufox Profile Manager

A **desktop GUI application** (PyQt5) for managing multiple [Camoufox](https://pypi.org/project/camoufox/) browser profiles, similar to GoLogin or Multilogin.

![screenshot](docs/screenshot.png)

---

## ✨ Features

- Manage unlimited browser profiles
- Persistent storage directory per profile (`C:\ProfileName` by default)
- Configure viewport size, fullscreen toggle
- Proxy support (host, port, user, password)
- GeoIP auto-matching with proxies
- Start / stop sessions with Camoufox
- Profiles saved to `profiles.json` locally
- Dark + Cyan professional theme (`.qss`)
- Safe: disables "Launch" button while session is running

---

## 📦 Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/camoufox-profile-manager.git
cd camoufox-profile-manager


Install & run with the helper script:

python install.py


This will:

Check Python version (3.9+ recommended)

Install dependencies (PyQt5, camoufox[geoip])

Fetch the Camoufox browser binary (if missing)

Launch the GUI

🔧 Requirements

Python 3.9+

Windows/Linux/macOS

Internet (for first-time camoufox fetch)

🗂️ Project Structure
camoufox-profile-manager/
│── camoufox_manager.ui    # Qt Designer UI
│── main_window.py         # main GUI logic
│── run.py                 # entry point
│── install.py             # installer/launcher
│── dark.qss               # dark theme (black/cyan)
│── profiles.json          # auto-created (stores profiles)
│── requirements.txt
│── README.md

🚀 Usage

Start the app with python run.py (after first install).

Create a new profile.

Set viewport, proxy, or fullscreen.

Launch → a Camoufox window opens with your settings.

📋 Roadmap / TODO

 Profile metadata (homepage, tags, notes)

 Profile cloning (duplicate)

 Export / import profiles (JSON)

 Proxy testing (IP & location check)

 Proxy pools / rotation

 Multi-launch (run multiple profiles at once)

 Activity log (last launch / close)

 Color tags for profiles

 Dashboard landing page

 Profile grid/card view

 Settings dialog (custom camoufox path, defaults)

 Build .exe releases with GitHub Actions (PyInstaller)

🙏 Thanks

Huge thanks to Camoufox
 for providing the privacy-focused browser engine this project is built on.
