# MediaHub — The Ultimate LAN Media Hub Guide

Welcome to the professional deployment guide for MediaHub (formerly StreamDrop). This document covers setup, installation, and daily usage.

---

## 1. Prerequisites
Before you begin, ensure your machine has the following:
- **Python 3.10+**: [Download here](https://www.python.org/downloads/)
- **FFmpeg**: Essential for video transcoding. Ensure it is added to your system **PATH**.
  - *Windows*: Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin` folder to Environment Variables.

---

## 2. Local Development Setup
To run the server directly from source code:

1. **Clone/Extract** the project folder.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment**:
   Create a `.env` file in the root directory (use `.env.example` as a template):
   ```ini
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your_secure_password
   DATABASE_URL=sqlite+aiosqlite:///./hub.db
   SHARED_FOLDER=C:/Path/To/Your/Movies
   ```
4. **Launch the Control Panel**:
   ```bash
   python server_manager.py
   ```

---

## 3. Professional Installation (The EXE Way)
We use a two-stage process to create a professional Windows installer that won't be flagged by antivirus.

### Stage A: Build the Directory (`build.bat`)
Run the `build.bat` file in the root. This uses PyInstaller with the `--onedir` flag.
- **Output**: A `dist/MediaHub/` folder.
- **Why?**: This prevents Windows Defender from flagging the app as a "Trojan" (which often happens with single-file EXEs).

### Stage B: Create the Setup Wizard (`MediaHub.iss`)
1. Install [Inno Setup](https://jrsoftware.org/isdl.php).
2. Open `MediaHub.iss` in the Inno Setup Compiler.
3. Click **Compile**.
4. **Result**: A single `MediaHub_Install.exe` that installs the app to `Program Files` and adds a Desktop shortcut.

---

## 4. Usage Guide

### Desktop Control Panel
- **Start/Stop Server**: Toggles the FastAPI backend process.
- **Hardware Monitoring**: Real-time CPU and RAM bars show the impact of transcoding.
- **Status Indicator**: Shows when the server is ready for LAN connections.

### Accessing the Hub
Once the server is running, other devices on your Wi-Fi can connect via:
- **URL**: `http://<your-pc-ip>:8000`
- **PWA**: On mobile, open the URL and select "Add to Home Screen" to install it as a native-feeling app.

### Features
- **Media Gallery**: Instant playback with HLS transcoding for perfect scrubbing.
- **Document Editor**: Collaborative inline editing for `.txt` and `.md` files.
- **Audit Logs**: Administrators can track who logged in and which files were modified.
- **Remote Control**: Sync clipboard and playback state across all connected devices.

---

## 5. Directory Structure
```text
MediaHub/
├── core/               # The Stateless Engine
├── static/             # The PWA Frontend
├── server_manager.py   # Desktop Control Panel
├── build.bat           # Packaging Script
└── MediaHub.iss        # Installer Script
```

Happy Streaming! 🚀
