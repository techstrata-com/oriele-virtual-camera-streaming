export type CameraStatus =
  | "created"
  | "stopped"
  | "starting"
  | "running"
  | "stopping"
  | "failed";

export type Camera = {
  id: string;
  name: string;
  video_id: string;
  device_path: string;
  status: CameraStatus;
  pid?: number | null;
  rtsp_pid?: number | null;
  rtsp_url?: string | null;
  http_live_url?: string | null;
  fps?: number | null;
  width?: number | null;
  height?: number | null;
  loop: boolean;
  created_at: string;
  updated_at: string;
  last_started_at?: string | null;
  last_stopped_at?: string | null;
};

export type CameraStreamUrls = {
  camera_id: string;
  status: CameraStatus;
  rtsp_url: string | null;
  http_live_url: string | null;
  available: boolean;
  message?: string;
};

export type CameraCreate = {
  name: string;
  video_id: string;
  device_path: string;
  fps?: number | null;
  width?: number | null;
  height?: number | null;
  loop: boolean;
};

