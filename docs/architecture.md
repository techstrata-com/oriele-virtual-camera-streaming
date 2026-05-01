# Architecture (MVP)

## Goals

- Users upload video files.
- Users create virtual cameras linked to a video.
- Each camera can be started/stopped, and streams frames to a Linux virtual camera device like `/dev/video10`.

## Non-goals (for MVP)

- RTSP/WebRTC streaming
- FFmpeg pipelines
- Celery/RabbitMQ, Kubernetes, microservices

## Runtime components

- **FastAPI backend**: REST API + business logic + spawns worker processes.
- **SQLite**: stores `videos` and `cameras`.
- **Worker process** (`app.workers.camera_worker`): reads video frames with OpenCV and pushes them to `/dev/videoX` using `pyvirtualcam`.
- **v4l2loopback**: kernel module that creates `/dev/video10`, `/dev/video11`, etc.
- **React frontend**: basic panel for uploads and camera management.

## Data layout

- `data/videos/<video_id>/<original_filename>`: stored uploads
- `data/thumbnails/<video_id>.jpg`: generated thumbnails
- `data/app.db`: SQLite database

