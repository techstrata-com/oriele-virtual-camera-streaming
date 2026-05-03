# Backend (FastAPI)

This backend provides:

- Video upload + metadata extraction + thumbnail generation
- Camera (stream session) management: create/start/stop/restart/pause/resume
- Each running camera is a **direct file → RTSP** pipeline: a small **stream worker** reads the uploaded file with OpenCV, writes raw frames to **FFmpeg stdin**, and FFmpeg publishes to **MediaMTX** (configurable `RTSP_HOST` / `RTSP_PORT`)
- **HTTP MJPEG** preview at `GET /live/{camera_id}` (same uploaded file, respects pause via `data/controls/{camera_id}/pause.flag`)

## Requirements

- Python 3.10+
- **FFmpeg** on `PATH` or set `FFMPEG_BINARY`
- **MediaMTX** (or compatible RTSP server) listening at `RTSP_HOST:RTSP_PORT` so each path `/{camera_id}` accepts a publish

Linux, macOS, and Windows are supported for the backend worker and FFmpeg paths. **Virtual cameras, v4l2loopback, `/dev/videoX`, and pyvirtualcam are not used.**

## Install

From `src/backend`:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional environment (see project root `.env` examples):

- `RTSP_ENABLED` — default `true` (must be enabled to start a stream)
- `RTSP_HOST`, `RTSP_PORT` — MediaMTX publish address (default `localhost` / `8554`)
- `RTSP_PUBLIC_BASE_URL` — optional public RTSP base for clients (e.g. `rtsp://192.168.1.10:8554`)
- `HTTP_LIVE_PUBLIC_BASE_URL` — optional public base for MJPEG links
- `FFMPEG_BINARY` — path to `ffmpeg` if not on `PATH`
- `STREAM_DEFAULT_FPS` — used when a camera has no `fps` set (default `30`)

## Run

From `src/backend`:

```bash
uvicorn app.main:app --reload
```

API: `http://localhost:8000`

## API endpoints

- `GET /api/health`
- `POST /api/videos/upload`
- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `DELETE /api/videos/{video_id}`
- `GET /api/videos/{video_id}/thumbnail`
- `POST /api/cameras` — body includes `client_id`, `video_id`, optional `fps`/`width`/`height`/`loop`; `device_path` is ignored (deprecated)
- `GET /api/cameras`
- `GET /api/cameras/{camera_id}`
- `POST /api/cameras/{camera_id}/start`
- `POST /api/cameras/{camera_id}/stop`
- `POST /api/cameras/{camera_id}/restart`
- `POST /api/cameras/{camera_id}/pause`
- `POST /api/cameras/{camera_id}/resume`
- `DELETE /api/cameras/{camera_id}`
- `GET /api/cameras/{camera_id}/stream-urls`
- `GET /live/{camera_id}`

## Curl examples

Health:

```bash
curl -s http://localhost:8000/api/health
```

Upload:

```bash
curl -F "file=@/path/to/video.mp4" http://localhost:8000/api/videos/upload
```

Create camera (idempotent on `(client_id, video_id)`):

```bash
curl -s -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "parking-client-001",
    "name": "Entry Gate Camera",
    "video_id": "YOUR_VIDEO_ID",
    "device_path": null,
    "fps": 30,
    "width": 1280,
    "height": 720,
    "loop": true
  }'
```

Start:

```bash
curl -s -X POST http://localhost:8000/api/cameras/YOUR_CAMERA_ID/start
```

RTSP in VLC (after MediaMTX is running):

`rtsp://localhost:8554/YOUR_CAMERA_ID`

## Stream worker (manual test)

From `src/backend` (MediaMTX must be up):

```bash
python -m app.workers.stream_worker \
  --camera-id test-path \
  --video-path ../../data/videos/.../file.mp4 \
  --control-dir ../../data/controls/test-path \
  --rtsp-push-url rtsp://localhost:8554/test-path \
  --ffmpeg-binary ffmpeg \
  --fps 30 \
  --width 1280 \
  --height 720 \
  --loop
```

## Troubleshooting

- **Start returns 400** — check `data/logs/camera_{id}.log` for FFmpeg errors; confirm MediaMTX is listening and `FFMPEG_BINARY` is correct.
- **RTSP disabled** — set `RTSP_ENABLED=1` in `.env`.
- **Stale “running” in DB** — `GET /api/cameras/{id}` runs process sync and may set status to `failed` if the worker died.
