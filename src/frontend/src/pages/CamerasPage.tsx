import { useEffect, useMemo, useState } from "react";
import { listCameras } from "../api/cameras";
import { listVideos } from "../api/videos";
import type { Camera } from "../types/camera";
import type { Video } from "../types/video";
import CameraList from "../components/CameraList";
import CameraForm from "../components/CameraForm";

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      const [cs, vs] = await Promise.all([listCameras(), listVideos()]);
      setCameras(cs);
      setVideos(vs);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to load cameras.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const videoNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const v of videos) map[v.id] = v.name;
    return map;
  }, [videos]);

  return (
    <div className="container">
      <div className="grid page-grid">
        <CameraForm
          videos={videos}
          onCreated={(cam) =>
            setCameras((prev) => {
              const rest = prev.filter((c) => c.id !== cam.id);
              return [cam, ...rest];
            })
          }
        />
        <div className="panel tips-panel">
          <h2>Tips</h2>
          <div className="muted">
            - MediaMTX must be running for RTSP output
            <br />
            - FFmpeg must be installed and available to the backend
            <br />
            - Each <code>client_id</code> + video gets one reusable stream session (create is idempotent)
            <br />
            - Use HTTP Live for browser preview; use RTSP in VLC/OpenCV/etc.
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn" onClick={refresh}>
              Refresh
            </button>
          </div>
        </div>
      </div>

      {error && <div className="error" style={{ marginTop: 16 }}>{error}</div>}

      <div className="section-gap">
        <CameraList
          cameras={cameras}
          videoNameById={videoNameById}
          onChanged={(cam) =>
            setCameras((prev) => prev.map((c) => (c.id === cam.id ? cam : c)))
          }
          onDeleted={(id) => setCameras((prev) => prev.filter((c) => c.id !== id))}
        />
      </div>
    </div>
  );
}

