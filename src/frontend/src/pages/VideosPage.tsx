import { useEffect, useMemo, useState } from "react";
import { listVideos } from "../api/videos";
import type { Video } from "../types/video";
import VideoUpload from "../components/VideoUpload";
import VideoList from "../components/VideoList";
import CameraForm from "../components/CameraForm";

export default function VideosPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createFrom, setCreateFrom] = useState<Video | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setVideos(await listVideos());
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to load videos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const videosById = useMemo(() => Object.fromEntries(videos.map((v) => [v.id, v])), [videos]);

  return (
    <div className="container">
      <div className="grid page-grid">
        <VideoUpload
          onUploaded={(v) => {
            setVideos((prev) => [v, ...prev]);
          }}
        />
        <CameraForm
          videos={videos}
          defaultVideoId={createFrom?.id}
          onCreated={() => {
            setCreateFrom(null);
          }}
        />
      </div>

      {error && <div className="error" style={{ marginTop: 16 }}>{error}</div>}
      {loading && <div className="muted" style={{ marginTop: 16 }}>Loading…</div>}

      <div className="section-gap">
        <VideoList
          videos={videos}
          onDeleted={(id) => setVideos((prev) => prev.filter((v) => v.id !== id))}
          onCreateCamera={(video) => {
            setCreateFrom(videosById[video.id] ?? video);
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
      </div>
    </div>
  );
}

