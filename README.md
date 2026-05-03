# oriele-virtual-camera-streaming

Upload video files, create reusable **stream sessions**, and expose each session as:

- **RTSP**: `rtsp://SERVER_IP:8554/{camera_id}`
- **HTTP live MJPEG preview**: `http://SERVER_IP:8000/live/{camera_id}`

Each session is owned by **`client_id + video_id`**, so the same client/video pair **reuses** the same stream session while different clients can stream the same uploaded video **independently**.

This project no longer creates or uses OS-level virtual cameras.

---

## 1. Project overview

The app lets you:

- Upload videos with metadata and thumbnails (**SQLite under `data/`**)
- Create stream sessions tied to **`client_id + video_id`** (idempotent creation)
- Start a dedicated backend **`stream_worker`** per running session
- Publish RTSP via **FFmpeg → MediaMTX**
- Preview via **FastAPI MJPEG** at `GET /live/{camera_id}`
- Pause/resume **without killing** the worker
- Stop/restart/delete sessions

### Main features

- FastAPI backend with Swagger at `http://SERVER_IP:8000/docs`
- React/Vite frontend; `client_id` is stored in `localStorage`
- SQLite database stored in `data/app.db`
- MediaMTX RTSP integration (default `:8554`)
- FFmpeg-based RTSP publishing
- OpenCV-based frame reading in the stream worker
- Cross-platform backend process management (Windows/Linux/macOS)
- Create session idempotency by `client_id + video_id` (prevents concurrency issues)

### Platform support

The direct streaming backend can run on **Windows**, **Linux**, or **macOS** as long as:

- **FFmpeg** is installed and reachable (or configured via `FFMPEG_BINARY`)
- **MediaMTX** is running for RTSP output

Linux is recommended for production servers, but the app **no longer depends** on Linux-only virtual camera devices.

---

## 2. Architecture

### High-level flow

1. **Upload video**
   - Client uploads a video.
   - Backend stores it under `data/videos`.
   - Backend returns a `video_id`.

2. **Create stream session**
   - Client sends `client_id`, `video_id`, a name, and options (`fps`, `width`, `height`, `loop`).
   - Backend creates or reuses a camera/session row.
   - Same `client_id + video_id` returns the same `camera_id`.

3. **Start session**
   - Backend sets status to `starting`.
   - Backend spawns `app.workers.stream_worker`.
   - Worker reads the uploaded video via OpenCV.
   - Worker writes raw frames to **FFmpeg stdin**.
   - FFmpeg publishes RTSP to MediaMTX at path `/{camera_id}`.
   - Backend returns:
     - `rtsp_url`
     - `http_live_url`

4. **HTTP live preview**
   - `GET /live/{camera_id}` serves an MJPEG preview.
   - Preview respects pause/resume state.

5. **Pause / resume**
   - Pause creates `data/controls/{camera_id}/pause.flag`.
   - Worker repeats the last frame and does not advance playback.
   - Resume removes the flag; playback continues from the same position.

6. **Stop / restart**
   - Stop terminates the stream worker and its FFmpeg child.
   - Restart is stop + start.

### Diagram

```text
Uploaded video file
        ↓
stream_worker (OpenCV)
        ↓
FFmpeg stdin
        ↓
MediaMTX
        ↓
RTSP: rtsp://SERVER_IP:8554/{camera_id}

FastAPI /live/{camera_id}
        ↓
HTTP MJPEG preview
```

RTSP and HTTP preview are separate outputs and may not be frame-perfect synchronized unless later changed to a shared frame pipeline.

---

## 3. Project layout

- `src/backend` — FastAPI backend, stream worker, services
- `src/frontend` — React/Vite UI
- `data/videos` — uploaded videos
- `data/thumbnails` — generated thumbnails
- `data/controls` — pause/resume control flags (`pause.flag`)
- `data/logs` — per-camera worker/FFmpeg logs (`camera_<camera_id>.log`)
- `data/app.db` — SQLite database

Note: `scripts/` may contain legacy helpers, but they are not required for this architecture and are not documented here.

---

## 4. Requirements

| Component | Notes |
|-----------|------|
| **OS** | Windows, Linux, or macOS. Linux recommended for server deployment. |
| **Python** | 3.10+ |
| **Node.js** | 18+ (with `npm`) |
| **FFmpeg** | Must be installed and available on `PATH` or configured with `FFMPEG_BINARY` |
| **MediaMTX** | RTSP server (required for RTSP playback) |
| **Git** | Clone the repository |
| **curl / unzip** | Useful for deployment and MediaMTX install |

Python dependencies include: FastAPI, SQLAlchemy, OpenCV (`opencv-python`), `python-dotenv`, `python-multipart`.

---

## 5. Local development setup

### MediaMTX (RTSP server)

Start MediaMTX first:

**Windows (PowerShell):**

```powershell
cd "PATH_TO_MEDIAMTX_FOLDER"
.\mediamtx.exe
```

**Linux/macOS:**

```bash
cd /path/to/mediamtx
./mediamtx
```

You should see a log line similar to:

```text
RTSP listener opened on :8554
```

### Backend (FastAPI)

**Windows (PowerShell):**

```powershell
cd "PATH_TO_PROJECT\src\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Linux/macOS:**

```bash
cd src/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend (React/Vite)

```bash
cd src/frontend
npm install
npm run dev
```

### Useful URLs (local)

- Swagger: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`
- RTSP: `rtsp://localhost:8554/{camera_id}`
- HTTP live: `http://localhost:8000/live/{camera_id}`

---

## 6. Environment variables

### Backend `.env`

Create: `src/backend/.env`

Local example:

```env
FRONTEND_ORIGIN=http://localhost:5173

RTSP_ENABLED=true
RTSP_HOST=localhost
RTSP_PORT=8554
RTSP_PUBLIC_BASE_URL=rtsp://localhost:8554
HTTP_LIVE_PUBLIC_BASE_URL=http://localhost:8000

FFMPEG_BINARY=ffmpeg
STREAM_DEFAULT_FPS=30
```

Server example (clients connect via `SERVER_IP`):

```env
FRONTEND_ORIGIN=http://SERVER_IP:5173

RTSP_ENABLED=true
RTSP_HOST=localhost
RTSP_PORT=8554
RTSP_PUBLIC_BASE_URL=rtsp://SERVER_IP:8554
HTTP_LIVE_PUBLIC_BASE_URL=http://SERVER_IP:8000

FFMPEG_BINARY=ffmpeg
STREAM_DEFAULT_FPS=30
```

Explanation:

- `RTSP_HOST` / `RTSP_PORT` are used by the backend/FFmpeg to **publish** to MediaMTX.
- `RTSP_PUBLIC_BASE_URL` is what clients should use to **watch** RTSP.
- `HTTP_LIVE_PUBLIC_BASE_URL` is what clients should use for browser preview.
- If clients are outside the server, do **not** use `localhost` in public URLs.

The backend automatically loads `src/backend/.env` via `python-dotenv`. OS/systemd environment variables can override `.env`. Code defaults are used only when no env value exists.

### Frontend `.env`

Create: `src/frontend/.env`

Local:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Server:

```env
VITE_API_BASE_URL=http://SERVER_IP:8000
```

---

## 7. Linux server deployment from zero

Replace placeholders:

- `SERVER_IP` — public/LAN IP of the server
- `YOUR_USER` — user that runs the backend
- `YOUR_REPO_URL` — git URL of this repo

### A. Update server

```bash
sudo apt update
sudo apt upgrade -y
```

### B. Install packages

```bash
sudo apt install -y git python3 python3-venv python3-pip nodejs npm ffmpeg curl unzip
```

### C. Check versions

```bash
python3 --version
node --version
npm --version
ffmpeg -version
```

If `node --version` is lower than **18**, install Node.js 18+ using NodeSource or `nvm`.

### D. Clone project

```bash
cd /opt
sudo git clone <YOUR_REPO_URL> video-streaming-platform
sudo chown -R $USER:$USER /opt/video-streaming-platform
cd /opt/video-streaming-platform
```

### E. Backend setup

```bash
cd /opt/video-streaming-platform/src/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### F. Backend `.env`

Create `/opt/video-streaming-platform/src/backend/.env` using the server example above.

### G. Run backend manually

```bash
cd /opt/video-streaming-platform/src/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### H. Frontend setup

```bash
cd /opt/video-streaming-platform/src/frontend
npm install
```

Create `/opt/video-streaming-platform/src/frontend/.env`:

```env
VITE_API_BASE_URL=http://SERVER_IP:8000
```

Development:

```bash
npm run dev -- --host 0.0.0.0
```

Production build:

```bash
npm run build
```

### I. MediaMTX install

1. Download the correct archive for your CPU architecture from the MediaMTX releases page.
2. Extract to `/opt/mediamtx` and run:

```bash
cd /opt/mediamtx
./mediamtx
```

Check RTSP listener:

```bash
ss -ltnp | grep 8554
```

### J. Firewall (UFW)

```bash
sudo ufw allow 8000/tcp
sudo ufw allow 8554/tcp
sudo ufw reload
sudo ufw status
```

Optional (frontend dev server):

```bash
sudo ufw allow 5173/tcp
```

---

## 8. API usage examples

### Upload video

`POST /api/videos/upload`

```bash
curl -F "file=@/path/to/video.mp4" http://localhost:8000/api/videos/upload
```

### Create stream session (idempotent)

Endpoint stays `POST /api/cameras` (API naming kept for compatibility).

```json
{
  "client_id": "parking-client-001",
  "name": "Parking Entry Stream",
  "video_id": "VIDEO_ID_FROM_UPLOAD",
  "device_path": null,
  "fps": 30,
  "width": 1280,
  "height": 720,
  "loop": true
}
```

Notes:

- `client_id`: stable identifier for the caller/tenant/session.
- `video_id`: returned by upload.
- `device_path`: **deprecated and ignored**; keep `null` for backward compatibility.
- Same `client_id + video_id` returns the same `camera_id`.
- Different `client_id` with the same `video_id` creates a separate stream session.

### Start / pause / resume / stop / restart

- `POST /api/cameras/{camera_id}/start`
- `POST /api/cameras/{camera_id}/pause`
- `POST /api/cameras/{camera_id}/resume`
- `POST /api/cameras/{camera_id}/stop`
- `POST /api/cameras/{camera_id}/restart`

Pause/resume behavior:

- Pause freezes the stream by making the worker repeat the last frame while keeping RTSP alive.
- Resume continues from the same playback position.
- Stop terminates the worker and FFmpeg child process.

Stream URLs:

- `GET /api/cameras/{camera_id}/stream-urls`
- `GET /live/{camera_id}`

Full route list and schemas: `http://SERVER_IP:8000/docs`

---

## 9. Testing flow

1. Start MediaMTX.
2. Start backend.
3. Start frontend.
4. Upload a video.
5. Create a stream session.
6. Confirm list shows stopped session (no device path).
7. Start stream.
8. Confirm the returned camera has:
   - `status = running`
   - `rtsp_pid != null`
   - `rtsp_url`
   - `http_live_url`
9. Open HTTP live: `http://localhost:8000/live/{camera_id}`
10. Open RTSP in VLC: `rtsp://localhost:8554/{camera_id}`
11. Pause → verify preview/RTSP freezes.
12. Resume → verify stream continues.
13. Stop → verify URLs unavailable.
14. Create same client/video again → verify same session id is reused.
15. Create different client/same video → verify a different session id.

Remember: HTTP preview and RTSP may not be perfectly synchronized because HTTP preview is a separate MJPEG path.

---

## 10. Systemd setup (Linux)

### Backend service

Create `/etc/systemd/system/video-streaming-backend.service`:

```ini
[Unit]
Description=Video Streaming Platform Backend
After=network.target

[Service]
User=YOUR_USER
WorkingDirectory=/opt/video-streaming-platform/src/backend
EnvironmentFile=/opt/video-streaming-platform/src/backend/.env
ExecStart=/opt/video-streaming-platform/src/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable video-streaming-backend
sudo systemctl start video-streaming-backend
sudo systemctl status video-streaming-backend
journalctl -u video-streaming-backend -f
```

### MediaMTX service

Create `/etc/systemd/system/mediamtx.service`:

```ini
[Unit]
Description=MediaMTX RTSP Server
After=network.target

[Service]
WorkingDirectory=/opt/mediamtx
ExecStart=/opt/mediamtx/mediamtx
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
sudo systemctl status mediamtx
journalctl -u mediamtx -f
```

---

## 11. Debugging commands

### Linux

```bash
ps aux | grep stream_worker
ps aux | grep ffmpeg
ps aux | grep mediamtx
journalctl -u video-streaming-backend -f
journalctl -u mediamtx -f
tail -f /opt/video-streaming-platform/data/logs/camera_<camera_id>.log
```

Manual cleanup (use with care):

```bash
pkill -f app.workers.stream_worker
pkill -f ffmpeg
pkill -f mediamtx
```

### Windows (PowerShell)

```powershell
taskkill /F /IM ffmpeg.exe
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*app.workers.stream_worker*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
taskkill /F /IM mediamtx.exe
```

Inspect processes:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like "*ffmpeg*" -or $_.CommandLine -like "*stream_worker*" -or $_.Name -like "*mediamtx*" } |
  Select-Object ProcessId, Name, CommandLine
```

---

## 12. Production notes

- Do not use `--reload` in production.
- MediaMTX must be running for RTSP output.
- FFmpeg must be installed and callable (`FFMPEG_BINARY`).
- Use real server IP/domain in public URLs; avoid `localhost` in `RTSP_PUBLIC_BASE_URL` / `HTTP_LIVE_PUBLIC_BASE_URL`.
- Prefer running a single backend process with SQLite unless you implement stronger cross-process coordination.
- Each stream session is uniquely identified by `client_id + video_id`.
- Start uses a `starting` status to avoid duplicate worker creation.
- Multiple concurrent sessions consume CPU (OpenCV + FFmpeg); size the server accordingly.

---

## 13. Expected URLs

| Service | URL |
|---------|-----|
| Backend API | `http://SERVER_IP:8000` |
| Swagger | `http://SERVER_IP:8000/docs` |
| Frontend dev | `http://SERVER_IP:5173` |
| RTSP | `rtsp://SERVER_IP:8554/{camera_id}` |
| HTTP live MJPEG | `http://SERVER_IP:8000/live/{camera_id}` |

---

## 14. Common deployment mistakes

- Using `localhost` in public RTSP/HTTP URLs when clients are outside the server.
- Forgetting to restart the backend after editing `src/backend/.env`.
- Installing an old Node.js from apt (frontend requires Node.js 18+).
- MediaMTX not running while expecting RTSP playback.
- FFmpeg not installed or not on `PATH` (or `FFMPEG_BINARY` not set correctly).
- Opening HTTP live without starting the stream first.
- Trying to play RTSP directly in a browser (use VLC or an RTSP-capable client).
- Running too many streams on a weak CPU.
- Expecting HTTP MJPEG preview and RTSP to be frame-perfect synchronized.
