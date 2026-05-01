# API (MVP)

Base URL: `http://localhost:8000`

## Health

- `GET /api/health`

## Videos

- `POST /api/videos/upload` (multipart form field: `file`)
- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `DELETE /api/videos/{video_id}`
- `GET /api/videos/{video_id}/thumbnail`

## Cameras

- `POST /api/cameras`
- `GET /api/cameras`
- `GET /api/cameras/{camera_id}`
- `POST /api/cameras/{camera_id}/start`
- `POST /api/cameras/{camera_id}/stop`
- `POST /api/cameras/{camera_id}/restart`
- `DELETE /api/cameras/{camera_id}`

