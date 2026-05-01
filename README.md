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

## Setup: virtual camera devices

Install + load `v4l2loopback`:

```bash
cd virtual-camera-platform
chmod +x scripts/*.sh
./scripts/setup_v4l2loopback.sh
./scripts/load_virtual_cameras.sh
```

You should see `/dev/video10` … `/dev/video14`.

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
- Create a camera (choose `/dev/video10`, `/dev/video11`, etc.)
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

- No RTSP/WebRTC in this MVP.
- The backend spawns worker processes using `subprocess.Popen`.

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

