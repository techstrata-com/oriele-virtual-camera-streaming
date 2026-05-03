# Architecture (MVP)

## Goals

- Users upload video files.
- Users create **cameras** (stream sessions) linked to `(client_id, video_id)` and optional encoding hints (`fps`, resolution, loop).
- Each camera can be started/stopped, paused/resumed; playback is **uploaded file → OpenCV decode → FFmpeg (stdin rawvideo) → RTSP via MediaMTX**, plus HTTP MJPEG preview served by the backend.

## Non-goals (for MVP)

- Full WebRTC/low-latency glass-to-glass optimization
- Distributed queue workers (Celery/RabbitMQ), Kubernetes, microservices
- Exact frame synchronization between RTSP subscribers and MJPEG preview

## Runtime components

- **FastAPI backend**: REST API, SQLite persistence, spawns isolated **stream worker** processes per running camera.
- **SQLite**: stores `videos` and `cameras` (each row represents one stream session; unique on `client_id` + `video_id`).
- **Stream worker** (`app.workers.stream_worker`): owns OpenCAP playback position and pause behavior; pushes raw frames to FFmpeg; FFmpeg publishes TCP RTSP to MediaMTX.
- **MediaMTX** (or compatible): accepts publisher per-path `/{camera_id}` matching `RTSP_HOST`/`RTSP_PORT`.
- **React frontend**: panel for uploads and camera management.

## Data layout

- `data/videos/<video_id>/<original_filename>`: stored uploads
- `data/thumbnails/<video_id>.jpg`: generated thumbnails
- `data/controls/<camera_id>/`: control files (e.g. `pause.flag`) for pause/resume
- `data/logs/camera_<camera_id>.log`: worker/ffmpeg logging from the backend
- `data/app.db`: SQLite database
