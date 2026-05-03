export type CameraStatus =
  | "created"
  | "stopped"
  | "starting"
  | "running"
  | "paused"
  | "stopping"
  | "failed";

export type Camera = {
  id: string;
  name: string;
  client_id: string;
  video_id: string;
  // Legacy fields (deprecated by backend; kept for compatibility)
  device_path?: string | null;
  device_label?: string | null;
  status: CameraStatus;
  pid?: number | null; // legacy (old worker pid)
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
  client_id: string;
  name: string;
  video_id: string;
  device_path?: string | null;
  fps?: number | null;
  width?: number | null;
  height?: number | null;
  loop: boolean;
};
