# virtual-camera-platform (MVP)

Upload video files, create **virtual cameras**, and expose each as a Linux device like `/dev/video10`.

This MVP focuses on:
- Video upload + metadata + thumbnail
- Camera CRUD + start/stop (spawns a worker process)
- Output frames to `/dev/videoX` using `pyvirtualcam` and `v4l2loopback`
- Simple React admin panel

## Requirements

- **Linux** (required for `/dev/video*` and `v4l2loopback`)
- **Python 3.10+**
- **Node.js 18+**
- **v4l2loopback**
- OpenCV (via `opencv-python`)
- `pyvirtualcam`

## Project structure

- `src/backend`: FastAPI backend + worker
- `src/frontend`: React UI
- `scripts`: v4l2loopback helpers
- `data`: videos, thumbnails, logs, SQLite DB

## Setup: Linux virtual cameras (dynamic labeled devices)

Each camera gets a **human-readable v4l2 card label** (`client_id - video filename`) on its `/dev/videoX` node. The backend **creates** loopback devices at runtime with `v4l2loopback-ctl add -n "<label>" /dev/videoN` (v4l2loopback **0.13+**). **Generic pre-created pools of unlabeled `/dev/video10` … nodes are not used** for assignment—nodes must either already show that exact label under `/sys/class/video4linux/videoN/name`, or be created with it.

### Packages

- **v4l2loopback** (kernel module / DKMS) — must be loaded (`/sys/module/v4l2loopback`)
- **v4l2loopback-utils** (or equivalent) — provides **`v4l2loopback-ctl`**
- **v4l2-utils** optional — `v4l2-ctl --list-devices`

### Linux deployment and permissions

Creating devices requires **`v4l2loopback-ctl add`**, which normally needs **elevated privileges**.

**Option A — Run the backend as root**

Run `uvicorn` (or your systemd unit) as `root` so `v4l2loopback-ctl add` succeeds without extra wiring.

**Option B — Passwordless sudo for `v4l2loopback-ctl` only**

1. Install `sudo` and ensure the backend runs as a dedicated user (e.g. `vcam`).
2. Allow **non-interactive** invocation (`sudo -n`) so the API never blocks on a password:

Example **`/etc/sudoers.d/vcam-v4l2`** (adjust paths and user):

```text
vcam ALL=(root) NOPASSWD: /usr/bin/v4l2loopback-ctl
```

Validate with `sudo visudo -cf /etc/sudoers.d/vcam-v4l2`.

3. Set **`V4L2LOOPBACK_USE_SUDO=true`** so the backend runs:

`sudo -n /usr/bin/v4l2loopback-ctl add -n "<label>" /dev/videoN`

If `sudo -n` cannot run without a password, the API returns a clear error (no silent fallback).

**Option C** (future): a small privileged helper service or polkit rule—document your own integration if needed.

### Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `VIRTUAL_CAMERA_START_NR` | `10` | First `/dev/videoN` minor to scan |
| `VIRTUAL_CAMERA_END_NR` | `99` | Last minor |
| `VIRTUAL_CAMERA_DYNAMIC_CREATE` | `true` | **Required** for labeled per-client cameras (must stay enabled). If `false`, creation fails with an explanatory error. |
| `V4L2LOOPBACK_CTL_BINARY` | `v4l2loopback-ctl` | Absolute path if not on `PATH` |
| `V4L2LOOPBACK_USE_SUDO` | `false` | If `true`, invoke `sudo -n … v4l2loopback-ctl add …` |

### Helper scripts (optional)

Legacy scripts may load `modprobe v4l2loopback` without reserved minors—the backend still **creates** labeled nodes dynamically within the configured numeric range.

```bash
cd virtual-camera-platform
chmod +x scripts/*.sh
./scripts/setup_v4l2loopback.sh
```

## Run backend

```bash
cd virtual-camera-platform/src/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend: `http://localhost:8000`

## Run frontend

```bash
cd virtual-camera-platform/src/frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## Use the app

- Upload a video in the **Videos** page
- Create a camera: the UI sends a stable **client id** (stored in the browser); the **Linux** backend assigns a free `/dev/videoX` and a readable device label. Re-creating for the same client + video returns the same camera without consuming another device.
- Start the camera from the **Cameras** page

## Consume the virtual camera from another app

Example Python consumer:

```python
import cv2

cap = cv2.VideoCapture("/dev/video10")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    print(frame.shape)
```

## Notes

- The backend spawns worker processes using `subprocess.Popen`.
- Duplicate `(client_id, video_id)` camera rows are prevented on **new** SQLite databases via a unique constraint; older databases rely on application logic and migration defaults (`client_id='legacy'` for existing rows).

## RTSP and HTTP live streaming

When a camera is **running**, the backend can provide:

- **RTSP**: `rtsp://localhost:8554/{camera_id}` (via an external RTSP server)
- **HTTP live (MJPEG)**: `http://localhost:8000/live/{camera_id}`

### Requirements

- **FFmpeg** installed and available in `PATH` (or set `FFMPEG_BINARY`)
- **MediaMTX** (RTSP server) running (recommended)
- Linux virtual camera still requires **`v4l2loopback`**

### Run MediaMTX

- Download MediaMTX and run it (defaults to RTSP port `8554`):
  - `./mediamtx`

### Local test

1. Start MediaMTX.
2. Start backend:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

3. Start frontend:

```bash
npm run dev
```

4. Upload video.
5. Create camera.
6. Start camera.
7. Copy RTSP URL from the Cameras table and open it in VLC:
   - Media -> Open Network Stream -> `rtsp://localhost:8554/{camera_id}`
8. Open HTTP live in a browser:
   - `http://localhost:8000/live/{camera_id}`

### External/server test

1. Run backend:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

2. Run MediaMTX on the server.
3. Open ports:
   - `8000` for HTTP/API
   - `8554` for RTSP
4. Set env:

```bash
RTSP_PUBLIC_BASE_URL=rtsp://SERVER_IP:8554
HTTP_LIVE_PUBLIC_BASE_URL=http://SERVER_IP:8000
```

5. URLs become:
   - `rtsp://SERVER_IP:8554/{camera_id}`
   - `http://SERVER_IP:8000/live/{camera_id}`

