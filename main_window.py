import json
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List

from PyQt5 import QtCore, QtGui, QtWidgets, uic

# ---- Camoufox (sync API) ----------------------------------------------------
try:
    from camoufox.sync_api import Camoufox
    CAMOUFOX_OK = True
except Exception:
    CAMOUFOX_OK = False

PROFILES_FILE = "profiles.json"


# ===== Data models =====
@dataclass
class ProxyConfig:
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""

    def to_proxy_dict(self) -> Optional[Dict[str, Any]]:
        if not self.host or not self.port:
            return None
        d = {"server": f"http://{self.host}:{self.port}"}
        if self.username:
            d["username"] = self.username
        if self.password:
            d["password"] = self.password
        return d


@dataclass
class Profile:
    name: str = "Profile"
    viewport_width: int = 1280
    viewport_height: int = 800
    fullscreen: bool = False
    persistent_dir: str = ""
    use_geoip: bool = False
    proxy: ProxyConfig = field(default_factory=ProxyConfig)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["proxy"] = asdict(self.proxy)
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Profile":
        raw_proxy = d.get("proxy", {})
        if not isinstance(raw_proxy, dict):
            raw_proxy = {}
        name = d.get("name", "Profile")

        # Default storage to C:\<ProfileName> if empty
        persistent_dir = d.get("persistent_dir", "")
        if not persistent_dir:
            persistent_dir = os.path.join("C:\\", name)

        return Profile(
            name=name,
            viewport_width=int(d.get("viewport_width", 1280)),
            viewport_height=int(d.get("viewport_height", 800)),
            fullscreen=bool(d.get("fullscreen", False)),
            persistent_dir=persistent_dir,
            use_geoip=bool(d.get("use_geoip", False)),
            proxy=ProxyConfig(
                host=raw_proxy.get("host", ""),
                port=int(raw_proxy.get("port", 0) or 0),
                username=raw_proxy.get("username", ""),
                password=raw_proxy.get("password", ""),
            ),
        )


# ===== Persistence =====
def load_profiles() -> List[Profile]:
    if not os.path.exists(PROFILES_FILE):
        return []
    with open(PROFILES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Profile.from_dict(x) for x in raw]


def save_profiles(profiles: List[Profile]) -> None:
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in profiles], f, indent=2)


# ===== Worker thread =====
class CamoufoxWorker(QtCore.QThread):
    started_ok = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)
    stopped = QtCore.pyqtSignal(str)

    def __init__(self, profile: Profile, launch_size: Optional[tuple[int,int]]=None, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.launch_size = launch_size  # (W,H) computed from fullscreen or viewport
        self._stop = False
        self._ctx = None

    def run(self):
        if not CAMOUFOX_OK:
            self.error.emit("Camoufox not available. Install with: pip install -U 'camoufox[geoip]' and run 'camoufox fetch'.")
            return
        try:
            W, H = self.launch_size if self.launch_size else (self.profile.viewport_width, self.profile.viewport_height)
            opts: Dict[str, Any] = {
                "headless": False,  # GUI app; we use fullscreen instead
                "window": (W + 2, H + 88),
            }

            if self.profile.persistent_dir:
                os.makedirs(self.profile.persistent_dir, exist_ok=True)
                opts["persistent_context"] = True
                opts["user_data_dir"] = os.path.abspath(self.profile.persistent_dir)

            px = self.profile.proxy.to_proxy_dict()
            if px:
                opts["proxy"] = px
                if self.profile.use_geoip:
                    opts["geoip"] = True

            self._ctx = Camoufox(**opts).__enter__()

            # Reuse existing page if present; close extras
            pages = list(getattr(self._ctx, "pages", []))
            if pages:
                page = pages[0]
                for extra in pages[1:]:
                    try: extra.close()
                    except Exception: pass
            else:
                page = self._ctx.new_page()

            # Set viewport; if fullscreen, try to match W,H (already set above)
            try:
                page.set_viewport_size({"width": W, "height": H})
            except Exception:
                pass

            # Try F11 for true fullscreen if the browser honors it
            if self.profile.fullscreen:
                try:
                    page.keyboard.press("F11")
                except Exception:
                    pass

            self.started_ok.emit(f"Session started for '{self.profile.name}'.")
            while not self._stop:
                time.sleep(0.2)

        except Exception as e:
            self.error.emit(f"Failed to start Camoufox: {e}")
        finally:
            try:
                if self._ctx is not None:
                    self._ctx.close()
                    try:
                        self._ctx.__exit__(None, None, None)
                    except Exception:
                        pass
            except Exception as e:
                self.error.emit(f"Error while stopping session: {e}")
            self.stopped.emit(f"Session stopped for '{self.profile.name}'.")

    def request_stop(self):
        self._stop = True


# ===== MainWindow Controller =====
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("camoufox_manager.ui", self)

        # Widgets from UI
        self.profileList: QtWidgets.QListWidget
        self.newProfileButton: QtWidgets.QPushButton
        self.deleteProfileButton: QtWidgets.QPushButton
        self.nameEdit: QtWidgets.QLineEdit
        self.spinW: QtWidgets.QSpinBox
        self.spinH: QtWidgets.QSpinBox
        self.fullscreenCheck: QtWidgets.QCheckBox
        self.proxyHostEdit: QtWidgets.QLineEdit
        self.proxyPortSpin: QtWidgets.QSpinBox
        self.proxyUserEdit: QtWidgets.QLineEdit
        self.proxyPassEdit: QtWidgets.QLineEdit
        self.geoipCheck: QtWidgets.QCheckBox
        self.storageEdit: QtWidgets.QLineEdit
        self.browseStorageButton: QtWidgets.QPushButton
        self.saveButton: QtWidgets.QPushButton
        self.launchButton: QtWidgets.QPushButton
        self.stopButton: QtWidgets.QPushButton

        # State
        self.profiles: List[Profile] = load_profiles()
        self.current_index: int = -1
        self.worker: Optional[CamoufoxWorker] = None

        # Signals
        self.profileList.itemSelectionChanged.connect(self._on_select_profile)
        self.newProfileButton.clicked.connect(self._new_profile)
        self.deleteProfileButton.clicked.connect(self._delete_profile)
        self.saveButton.clicked.connect(self._save_changes)
        self.browseStorageButton.clicked.connect(self._browse_storage)
        self.launchButton.clicked.connect(self._launch)
        self.stopButton.clicked.connect(self._stop)

        self.launchButton.setObjectName("primary")
        self.stopButton.setObjectName("danger")

        # Initial UI state
        self._refresh_list()
        if self.profiles:
            self.profileList.setCurrentRow(0)
        self._set_running(False)

        # Professional theme
        QtWidgets.QApplication.setStyle("Fusion")
        self._apply_palette()
        self.statusbar.showMessage("Ready")

    # ----- Styling
    def _apply_palette(self):
        p = QtGui.QPalette()
        base = QtGui.QColor(248, 249, 251)
        text = QtGui.QColor(33, 37, 41)
        highlight = QtGui.QColor(76, 110, 245)
        p.setColor(QtGui.QPalette.Window, base)
        p.setColor(QtGui.QPalette.Base, QtGui.QColor(255, 255, 255))
        p.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(245, 246, 248))
        p.setColor(QtGui.QPalette.WindowText, text)
        p.setColor(QtGui.QPalette.Text, text)
        p.setColor(QtGui.QPalette.ButtonText, text)
        p.setColor(QtGui.QPalette.Highlight, highlight)
        p.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
        self.setPalette(p)

    # ----- Helpers
    def _refresh_list(self):
        self.profileList.clear()
        for p in self.profiles:
            self.profileList.addItem(p.name)

    def _current(self) -> Optional[Profile]:
        if 0 <= self.current_index < len(self.profiles):
            return self.profiles[self.current_index]
        return None

    def _populate_form(self, p: Optional[Profile]):
        if not p:
            self.nameEdit.setText("")
            self.spinW.setValue(1280); self.spinH.setValue(800)
            self.fullscreenCheck.setChecked(False)
            self.proxyHostEdit.setText(""); self.proxyPortSpin.setValue(0)
            self.proxyUserEdit.setText(""); self.proxyPassEdit.setText("")
            self.geoipCheck.setChecked(False)
            self.storageEdit.setText("")
            return
        self.nameEdit.setText(p.name)
        self.spinW.setValue(p.viewport_width)
        self.spinH.setValue(p.viewport_height)
        self.fullscreenCheck.setChecked(p.fullscreen)
        self.proxyHostEdit.setText(p.proxy.host)
        self.proxyPortSpin.setValue(p.proxy.port)
        self.proxyUserEdit.setText(p.proxy.username)
        self.proxyPassEdit.setText(p.proxy.password)
        self.geoipCheck.setChecked(p.use_geoip)
        self.storageEdit.setText(p.persistent_dir)

    def _gather_form(self) -> Profile:
        p = self._current() or Profile()
        p.name = self.nameEdit.text().strip() or "Profile"
        p.viewport_width = int(self.spinW.value())
        p.viewport_height = int(self.spinH.value())
        p.fullscreen = self.fullscreenCheck.isChecked()
        p.proxy.host = self.proxyHostEdit.text().strip()
        p.proxy.port = int(self.proxyPortSpin.value())
        p.proxy.username = self.proxyUserEdit.text().strip()
        p.proxy.password = self.proxyPassEdit.text().strip()
        p.use_geoip = self.geoipCheck.isChecked()
        # Default storage dir C:\<ProfileName> if blank
        s = self.storageEdit.text().strip()
        if not s:
            s = os.path.join("C:\\", p.name)
        p.persistent_dir = s
        return p

    def _set_running(self, running: bool):
        # While running: disable Launch, enable Stop, lock editing for safety
        self.launchButton.setEnabled(not running)
        self.stopButton.setEnabled(running)
        for w in [
            self.profileList, self.newProfileButton, self.deleteProfileButton,
            self.nameEdit, self.spinW, self.spinH, self.fullscreenCheck,
            self.proxyHostEdit, self.proxyPortSpin, self.proxyUserEdit, self.proxyPassEdit,
            self.geoipCheck, self.storageEdit, self.browseStorageButton, self.saveButton
        ]:
            w.setEnabled(not running)

    # ----- Slots
    def _on_select_profile(self):
        self.current_index = self.profileList.currentRow()
        self._populate_form(self._current())

    def _new_profile(self):
        p = Profile(name=f"Profile {len(self.profiles)+1}")
        # default storage C:\<name>
        p.persistent_dir = os.path.join("C:\\", p.name)
        self.profiles.append(p)
        save_profiles(self.profiles)
        self._refresh_list()
        self.profileList.setCurrentRow(len(self.profiles)-1)
        self.statusbar.showMessage("New profile created", 3000)

    def _delete_profile(self):
        row = self.profileList.currentRow()
        if row < 0:
            return
        name = self.profiles[row].name
        if QtWidgets.QMessageBox.question(self, "Confirm Delete", f"Delete profile '{name}'?") != QtWidgets.QMessageBox.Yes:
            return
        del self.profiles[row]
        save_profiles(self.profiles)
        self._refresh_list()
        self._populate_form(None)
        self.current_index = -1
        self.statusbar.showMessage(f"Deleted '{name}'", 3000)

    def _save_changes(self):
        if self.current_index == -1:
            self._new_profile()
            return
        self.profiles[self.current_index] = self._gather_form()
        save_profiles(self.profiles)
        self._refresh_list()
        self.profileList.setCurrentRow(self.current_index)
        self.statusbar.showMessage("Profile saved", 3000)

    def _browse_storage(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Storage Directory")
        if d:
            self.storageEdit.setText(d)

    def _launch(self):
        if self.worker and self.worker.isRunning():
            self.statusbar.showMessage("A session is already running", 3000)
            return
        if self.current_index == -1:
            QtWidgets.QMessageBox.information(self, "No profile", "Create or select a profile first.")
            return

        prof = self._gather_form()
        # persist edits before launch
        self.profiles[self.current_index] = prof
        save_profiles(self.profiles)

        if not CAMOUFOX_OK:
            QtWidgets.QMessageBox.warning(self, "Camoufox not available",
                                          "Install with:\n  pip install -U 'camoufox[geoip]'\nThen run:\n  camoufox fetch")
            return

        # Decide launch size: fullscreen → use primary screen geometry; else use profile viewport
        if prof.fullscreen:
            screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
            launch_size = (screen.width(), screen.height())
        else:
            launch_size = (prof.viewport_width, prof.viewport_height)

        self.worker = CamoufoxWorker(prof, launch_size)
        self.worker.started_ok.connect(lambda m: self.statusbar.showMessage(m, 5000))
        self.worker.error.connect(lambda m: QtWidgets.QMessageBox.critical(self, "Session Error", m))
        self.worker.stopped.connect(self._on_stopped)
        self.worker.start()
        self._set_running(True)

    def _stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(5000)
            self.statusbar.showMessage("Stopping session…", 3000)
        else:
            self.statusbar.showMessage("No session to stop", 3000)

    def _on_stopped(self, msg: str):
        self.statusbar.showMessage(msg, 5000)
        self._set_running(False)

def apply_qss(app, path="dark.qss"):
    full = os.path.abspath(path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"QSS not found: {full}")
    with open(full, "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

def main():
    # HiDPI before QApplication
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    apply_qss(app, "dark.qss")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
