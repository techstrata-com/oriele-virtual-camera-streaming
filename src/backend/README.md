# Backend (FastAPI)

This backend provides:
- Video upload + metadata extraction + thumbnail generation
- Camera management (create/start/stop/restart) using a separate worker process
- Output to Linux virtual camera devices like `/dev/video10` via `pyvirtualcam` + `v4l2loopback`

## Requirements

- Linux (required for `/dev/video*` devices and `v4l2loopback`)
- Python 3.10+
- `v4l2loopback` kernel module loaded (see `../../scripts/`)

## Install

From `virtual-camera-platform/src/backend`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

From `virtual-camera-platform/src/backend`:

```bash
uvicorn app.main:app --reload
```

API will be at `http://localhost:8000`.

## API endpoints

- `GET /api/health`
- `POST /api/videos/upload`
- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `DELETE /api/videos/{video_id}`
- `GET /api/videos/{video_id}/thumbnail`
- `POST /api/cameras`
- `GET /api/cameras`
- `GET /api/cameras/{camera_id}`
- `POST /api/cameras/{camera_id}/start`
- `POST /api/cameras/{camera_id}/stop`
- `POST /api/cameras/{camera_id}/restart`
- `DELETE /api/cameras/{camera_id}`

## Curl examples

Health:

```bash
curl -s http://localhost:8000/api/health
```

Upload a video:

```bash
curl -F "file=@/path/to/video.mp4" http://localhost:8000/api/videos/upload
```

List videos:

```bash
curl -s http://localhost:8000/api/videos
```

Create camera:

```bash
curl -s -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Entry Gate Camera",
    "video_id": "YOUR_VIDEO_ID",
    "device_path": "/dev/video10",
    "fps": 30,
    "width": 1280,
    "height": 720,
    "loop": true
  }'
```

Start camera:

```bash
curl -s -X POST http://localhost:8000/api/cameras/YOUR_CAMERA_ID/start
```

Stop camera:

```bash
curl -s -X POST http://localhost:8000/api/cameras/YOUR_CAMERA_ID/stop
```

## Worker command example

From `virtual-camera-platform/src/backend`:

```bash
python -m app.workers.camera_worker \
  --camera-id test \
  --video-path ../../data/videos/test/some.mp4 \
  --device-path /dev/video10 \
  --fps 30 \
  --width 1280 \
  --height 720 \
  --loop
```

## Troubleshooting

- `/dev/video10` not found
  - Load the module: `../../scripts/load_virtual_cameras.sh`
  - Verify: `ls -la /dev/video*`
- Permission denied opening `/dev/video10`
  - Run with appropriate permissions or adjust udev rules (MVP suggestion: run your app as a user with access to video devices).
- `pyvirtualcam` cannot open device
  - Ensure `v4l2loopback` loaded with `exclusive_caps=1`
  - Ensure no other process is holding the same device
- `v4l2loopback` not loaded
  - Run: `sudo modprobe v4l2loopback ...` (see scripts)

