# virtual-camera-platform

Upload video files, create **virtual cameras**, and expose each as a Linux device such as `/dev/video10`. Each camera is owned by **`client_id` + `video_id`**. On Linux, devices are created dynamically with a **labeled** v4l2 node (`client_id - video filename`). **Generic unlabeled pre-created `/dev/video` pools are not assigned to users.**

---

## 1. Project overview

### What this project does

The **virtual-camera-platform** MVP lets you:

- Upload videos with metadata and thumbnails (SQLite under `data/`)
- Create cameras tied to a caller identity (`client_id`) and a video (`video_id`)
- Run a **worker** that streams decoded frames into a **virtual Video4Linux device** (`/dev/videoX`) using **pyvirtualcam** and **v4l2loopback**
- Optionally expose **RTSP** (FFmpeg → **MediaMTX**) and **HTTP live MJPEG** for other applications

### Main features

- FastAPI backend with Swagger at `/docs`
- React/Vite frontend; **`client_id` is stored in `localStorage`**
- Camera CRUD; **start / stop / restart** APIs
- **Create camera is idempotent** per `client_id` + `video_id` (same pair returns the same camera)
- **Pause / resume**: freezes the virtual camera stream without killing the worker; resume continues from the same position. **Stop** tears down the worker and RTSP sidecar processes.

### What is Linux-only

- Real **`/dev/videoX`** output via **v4l2loopback** and **pyvirtualcam**
- **Dynamic labeled** loopback devices via `v4l2loopback-ctl add -n "<label>" /dev/videoN` (v4l2loopback **0.13+**)

### What works on Windows or macOS (local testing only)

You can run the backend and frontend for API/UI development, but **production virtual camera devices and labeled loopback behavior target Linux**. Other platforms may use alternate code paths for streaming tests; treat them as **not** a substitute for Linux deployment validation.

---

## 2. Architecture

High-level flow:

1. **Upload video** — Client uploads a file; backend stores it and returns a **`video_id`**.
2. **Create camera** — Client sends `client_id`, `video_id`, and options. **`device_path: null`** means **auto** allocation on Linux (dynamic labeled device). The same **`client_id` + `video_id`** yields the **same camera id** (idempotent).
3. **Backend allocates a labeled v4l2loopback device** — Within `VIRTUAL_CAMERA_START_NR` … `VIRTUAL_CAMERA_END_NR`, the backend runs **`v4l2loopback-ctl add -n "<label>" /dev/videoN`** so the sysfs name is **`client_id - video filename`**. Unlabeled pre-created nodes in that range are **not** handed to users.
4. **Worker streams frames** — A subprocess **camera worker** reads the video and writes frames into **`/dev/videoX`** via pyvirtualcam.
5. **FFmpeg pushes RTSP to MediaMTX** — When RTSP is enabled and the camera is running, FFmpeg publishes to the RTSP server (default listener **`:8554`**).
6. **HTTP live** — **`GET /live/{camera_id}`** serves **MJPEG** from the running virtual camera pipeline.
7. **Consumers** — Other projects use **`rtsp://…/{camera_id}`** or **`http://…/live/{camera_id}`**, or read **`/dev/videoX`** directly on the host.

### Project layout

- `src/backend` — FastAPI, workers, services
- `src/frontend` — React UI
- `scripts` — Optional v4l2loopback helpers
- `data/` — Videos, thumbnails, logs, **SQLite database file**

---

## 3. Requirements

| Component | Notes |
|-----------|--------|
| **OS** | **Ubuntu 22.04 or 24.04** recommended for servers |
| **Python** | **3.10+** |
| **Node.js** | **18+** (with `npm`) |
| **FFmpeg** | On `PATH` or set `FFMPEG_BINARY` |
| **v4l2loopback** | Kernel module — package **`v4l2loopback-dkms`** |
| **v4l2loopback-utils** | Provides **`v4l2loopback-ctl`** |
| **v4l-utils** | `v4l2-ctl`, debugging |
| **MediaMTX** | RTSP server (separate install; see deployment) |
| **Git** | Clone the repository |
| **sudo, curl, unzip** | Deployment and MediaMTX download/extract |

Also: **OpenCV** (via `opencv-python`), **pyvirtualcam** (see `src/backend/requirements.txt`).

---

## 4. Linux server deployment from zero

Replace placeholders everywhere:

- **`SERVER_IP`** — Public or LAN IP of the server (or `localhost` for local-only tests)
- **`YOUR_USER`** — Unprivileged user that runs the backend (and owns the repo)
- **`YOUR_REPO_URL`** — Git remote URL for this project

### A. Update the server

```bash
sudo apt update
sudo apt upgrade -y
```

### B. Install packages

```bash
sudo apt install -y git python3 python3-venv python3-pip nodejs npm ffmpeg v4l2loopback-dkms v4l2loopback-utils v4l-utils sudo curl unzip
```

### C. Check versions

```bash
python3 --version
node --version
npm --version
ffmpeg -version
```

If `node --version` reports lower than **18**, install **Node.js 18+** using [NodeSource](https://github.com/nodesource/distributions) or **nvm** instead of relying on the default Ubuntu `apt` packages.

**Reason:** `sudo apt install nodejs npm` may install an older Node.js on some Ubuntu releases; the frontend expects Node.js **18+**.

### D. Load the v4l2loopback module

```bash
sudo modprobe v4l2loopback
lsmod | grep v4l2loopback
ls /sys/module/v4l2loopback
```

### E. Clone the project

```bash
cd /opt
sudo git clone <YOUR_REPO_URL> virtual-camera-platform
sudo chown -R $USER:$USER /opt/virtual-camera-platform
cd /opt/virtual-camera-platform
```

### F. Set up the backend

```bash
cd /opt/virtual-camera-platform/src/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### G. Backend environment file

Create the file:

```bash
nano /opt/virtual-camera-platform/src/backend/.env
```

Example (adjust **`SERVER_IP`** and paths as needed):

```env
FRONTEND_ORIGIN=http://SERVER_IP:5173

RTSP_ENABLED=true
RTSP_HOST=localhost
RTSP_PORT=8554
RTSP_PUBLIC_BASE_URL=rtsp://SERVER_IP:8554
HTTP_LIVE_PUBLIC_BASE_URL=http://SERVER_IP:8000

FFMPEG_BINARY=ffmpeg

VIRTUAL_CAMERA_START_NR=10
VIRTUAL_CAMERA_END_NR=99
VIRTUAL_CAMERA_DYNAMIC_CREATE=true
V4L2LOOPBACK_CTL_BINARY=v4l2loopback-ctl
V4L2LOOPBACK_USE_SUDO=true
```

**`SERVER_IP`** must match how clients reach the server (browser, VLC, other services). For TLS or reverse proxies, set `FRONTEND_ORIGIN` and public URLs to match your real scheme/host.

The backend loads **`src/backend/.env`** automatically via **`python-dotenv`**. Real **OS/systemd** environment variables take priority over `.env`; values in **`config.py`** are defaults used only when neither the OS environment nor `.env` provides a setting.

After changing **`src/backend/.env`**, restart the backend. With systemd:

```bash
sudo systemctl restart virtual-camera-backend
```

For a manual `uvicorn` run, stop the process and start it again.

| Variable | Role |
|----------|------|
| `FRONTEND_ORIGIN` | CORS / frontend origin |
| `RTSP_*`, `HTTP_LIVE_PUBLIC_BASE_URL` | URLs shown to users or used by integrations |
| `FFMPEG_BINARY` | FFmpeg executable |
| `VIRTUAL_CAMERA_*` | Minor range and **required** dynamic creation for labeled devices |
| `V4L2LOOPBACK_*` | Control binary path; **`V4L2LOOPBACK_USE_SUDO=true`** when using passwordless sudo (see below) |

### H. Permissions for dynamic labeled virtual cameras

Creating devices requires:

```bash
v4l2loopback-ctl add -n "<label>" /dev/videoN
```

Choose **one** approach.

#### Option A — Run the backend as root

Run `uvicorn` (or systemd) as **`root`** so `v4l2loopback-ctl add` succeeds without sudo configuration. **Not recommended** for production unless you accept the security tradeoff.

#### Option B — Passwordless sudo only for `v4l2loopback-ctl` (recommended pattern)

1. Note the real path to the binary:

```bash
which v4l2loopback-ctl
```

2. Edit a dedicated sudoers drop-in (use **`visudo`**):

```bash
sudo visudo -f /etc/sudoers.d/vcam-v4l2
```

Example line (replace **`YOUR_USER`** and path if different):

```text
YOUR_USER ALL=(root) NOPASSWD: /usr/bin/v4l2loopback-ctl
```

3. Validate:

```bash
sudo visudo -cf /etc/sudoers.d/vcam-v4l2
sudo -n v4l2loopback-ctl --help
```

4. Set **`V4L2LOOPBACK_USE_SUDO=true`** in `.env` so the backend runs non-interactive:

`sudo -n … v4l2loopback-ctl add …`

If `sudo -n` cannot run without a password, the API should **fail with a clear error** (no silent fallback to unlabeled devices).

**Future option:** a small privileged helper or polkit rule—document your own integration if you add one.

### I. Run the backend manually

```bash
cd /opt/virtual-camera-platform/src/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- API root: `http://SERVER_IP:8000`
- **Swagger:** `http://SERVER_IP:8000/docs`
- **HTTP live:** `http://SERVER_IP:8000/live/{camera_id}`

### J. Set up the frontend

```bash
cd /opt/virtual-camera-platform/src/frontend
npm install
```

Create `src/frontend/.env`:

```bash
nano /opt/virtual-camera-platform/src/frontend/.env
```

```env
VITE_API_BASE_URL=http://SERVER_IP:8000
```

**Development** (bind on all interfaces):

```bash
npm run dev -- --host 0.0.0.0
```

**Production build** (static files to serve with nginx or similar):

```bash
npm run build
```

### K. Install and run MediaMTX

1. Download the correct **Linux** archive for your server **CPU architecture** from the [MediaMTX releases](https://github.com/bluenviron/mediamtx/releases) page (pick the current release; filenames and version tags change over time). For most VPS hosts, use the **Linux amd64** build. On **ARM** servers (for example Raspberry Pi or ARM cloud instances), choose the matching **ARM** asset instead.
2. Extract to **`/opt/mediamtx`** (layout should include the `mediamtx` binary at `/opt/mediamtx/mediamtx`).
3. Run:

```bash
cd /opt/mediamtx
./mediamtx
```

You should see a log line similar to:

```text
RTSP listener opened on :8554
```

Confirm something is listening on RTSP **TCP** port **8554**:

```bash
ss -ltnp | grep 8554
```

You should see a listener bound to port **8554** (process name may show as `mediamtx`).

Keep MediaMTX running whenever you need RTSP. For production, use the **systemd** unit in [Systemd setup](#systemd-setup).

### L. Firewall (UFW)

Minimum for API + HTTP live + RTSP:

```bash
sudo ufw allow 8000/tcp
sudo ufw allow 8554/tcp
sudo ufw reload
sudo ufw status
```

Optional (development frontend, extra MediaMTX ports):

```bash
sudo ufw allow 5173/tcp
sudo ufw allow 8888/tcp
sudo ufw allow 8889/tcp
sudo ufw reload
sudo ufw status
```

| Port | Typical use |
|------|-------------|
| **8000** | Backend API + **HTTP live MJPEG** |
| **8554** | **RTSP** (MediaMTX) |
| **5173** | Vite dev server only |
| **8888 / 8889** | Often used by MediaMTX defaults (HLS / WebRTC, etc.) — open only if you use those features |

### M. Full test flow

1. Open the frontend (`http://SERVER_IP:5173` in dev, or your static hosting URL).
2. **Upload** a video on the Videos page.
3. **Create camera** with `device_path: null` for Linux auto allocation.
4. Confirm devices and label:

```bash
ls -l /dev/video*
cat /sys/class/video4linux/video10/name
```

(Adjust `video10` to the minor your deployment used.) **Expected name format:** `client-id - video-name.mp4`

5. **Start** the camera from the UI or API.
6. **RTSP in VLC:** `Media → Open Network Stream` → `rtsp://SERVER_IP:8554/{camera_id}`
7. **HTTP live in a browser:** `http://SERVER_IP:8000/live/{camera_id}`

---

## 5. API usage examples

### Create camera (idempotent)

`POST /api/cameras`

Example body:

```json
{
  "client_id": "parking-client-001",
  "name": "Parking Entry Camera",
  "video_id": "VIDEO_ID_FROM_UPLOAD",
  "device_path": null,
  "fps": 30,
  "width": 1280,
  "height": 720,
  "loop": true
}
```

- **`client_id`** — Caller / user / session / project identifier (stable for that tenant).
- **`name`** — Display name in the UI.
- **`video_id`** — Returned by the upload API after a successful upload.
- **`device_path`** — Use **`null`** on Linux for **automatic** dynamic labeled device creation. Do not point at generic unlabeled pool devices for multi-tenant assignment.
- **Same `client_id` + `video_id`** → **same camera id** (idempotent).
- **Different `client_id`** + **same `video_id`** → **new** virtual camera (separate device allocation).

### Pause and resume

| Action | Method | Path |
|--------|--------|------|
| Pause | `POST` | `/api/cameras/{camera_id}/pause` |
| Resume | `POST` | `/api/cameras/{camera_id}/resume` |

**Pause** freezes the virtual camera stream (and HTTP live behavior) **without** killing the worker. **Resume** continues from the **same** playback position. **Stop** (`POST /api/cameras/{camera_id}/stop`) stops the worker and RTSP-related processes.

Start / stop / restart:

- `POST /api/cameras/{camera_id}/start`
- `POST /api/cameras/{camera_id}/stop`
- `POST /api/cameras/{camera_id}/restart`

Full route list and schemas: **`http://SERVER_IP:8000/docs`**.

---

## 6. Systemd setup

### Backend service

Create `/etc/systemd/system/virtual-camera-backend.service`:

```ini
[Unit]
Description=Virtual Camera Platform Backend
After=network.target

[Service]
User=YOUR_USER
WorkingDirectory=/opt/virtual-camera-platform/src/backend
EnvironmentFile=/opt/virtual-camera-platform/src/backend/.env
ExecStart=/opt/virtual-camera-platform/src/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable virtual-camera-backend
sudo systemctl start virtual-camera-backend
sudo systemctl status virtual-camera-backend
journalctl -u virtual-camera-backend -f
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

Adjust **`User=`** for MediaMTX if you do not want it running as root (match your install permissions).

---

## 7. Debugging commands

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
for f in /sys/class/video4linux/video*/name; do echo "$f: $(cat $f)"; done
ps aux | grep camera_worker
ps aux | grep ffmpeg
journalctl -u virtual-camera-backend -f
journalctl -u mediamtx -f
```

Manual cleanup (use with care):

```bash
pkill -f ffmpeg
pkill -f camera_worker
```

---

## 8. Production notes

- Do **not** use **`--reload`** in production.
- Prefer **one backend process** unless you implement cross-process locking for shared resources (devices, DB assumptions).
- **Dynamic v4l2loopback creation** needs **privileges** (root or constrained sudo).
- **MediaMTX** must be running for **RTSP** output.
- **FFmpeg** must be installed and callable (`FFMPEG_BINARY`).
- If the backend **cannot create** the labeled device, it should **fail clearly**—do **not** assign **generic unlabeled** `/dev/video*` nodes to clients.
- Each logical camera is uniquely defined by **`client_id` + `video_id`** for creation/idempotency.

---

## 9. Expected URLs

| Service | URL |
|---------|-----|
| Backend API | `http://SERVER_IP:8000` |
| Swagger | `http://SERVER_IP:8000/docs` |
| Frontend (dev) | `http://SERVER_IP:5173` |
| RTSP | `rtsp://SERVER_IP:8554/{camera_id}` |
| HTTP live (MJPEG) | `http://SERVER_IP:8000/live/{camera_id}` |

---

## 10. Consume `/dev/video` from another app

Example (Python + OpenCV):

```python
import cv2

cap = cv2.VideoCapture("/dev/video10")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    print(frame.shape)
```

Use the **`/dev/videoN`** minor assigned to your camera on that host.

---

## 11. Helper scripts (optional)

Legacy scripts may load `modprobe v4l2loopback` without reserved minors; the backend still **creates** labeled nodes dynamically inside the configured numeric range.

```bash
cd /opt/virtual-camera-platform
chmod +x scripts/*.sh
./scripts/setup_v4l2loopback.sh
```

---

## 12. Implementation notes

- The backend spawns worker processes with **`subprocess.Popen`**.
- Duplicate **`(client_id, video_id)`** rows are prevented on **new** SQLite databases via a unique constraint; older databases may rely on application logic and migration defaults (`client_id='legacy'` for existing rows).

---

## Common deployment mistakes

- Using **`localhost`** in public RTSP or HTTP URLs. For clients outside the server, set **`RTSP_PUBLIC_BASE_URL`** and **`HTTP_LIVE_PUBLIC_BASE_URL`** to the real server **IP or hostname** (or TLS URL behind a proxy).
- Forgetting to **restart the backend** after editing **`src/backend/.env`**.
- Installing an **old Node.js** from `apt` only; the frontend needs **Node.js 18+** (see version check in **Section 4C**).
- Running **multiple backend worker processes** without cross-process locking (devices and SQLite assumptions).
- **MediaMTX** not running while expecting **RTSP** playback.
- Backend user **not allowed** to run **`v4l2loopback-ctl add`** (missing sudoers / wrong `V4L2LOOPBACK_USE_SUDO` setup).
- **v4l2loopback** kernel module not loaded (`modprobe` / boot persistence).

---

## Local quick start (development)

**Backend:**

```bash
cd virtual-camera-platform/src/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend:**

```bash
cd virtual-camera-platform/src/frontend
npm install
npm run dev
```

Use **`http://localhost:8000/docs`** and configure `.env` files for your machine. Full production deployment on Linux follows **Section 4** above.
