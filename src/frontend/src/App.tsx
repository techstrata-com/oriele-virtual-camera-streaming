import { NavLink, Route, Routes } from "react-router-dom";
import VideosPage from "./pages/VideosPage";
import CamerasPage from "./pages/CamerasPage";
import CameraDetailPage from "./pages/CameraDetailPage";

export default function App() {
  return (
    <>
      <div className="container">
        <div className="topbar">
          <div className="brand">
            <b>Video streaming sessions</b>
            <span className="muted">Upload videos → start RTSP + HTTP live streams</span>
          </div>
          <nav className="nav">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
              Videos
            </NavLink>
            <NavLink to="/cameras" className={({ isActive }) => (isActive ? "active" : "")}>
              Streams
            </NavLink>
          </nav>
        </div>
      </div>
      <Routes>
        <Route path="/" element={<VideosPage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        <Route path="/cameras/:cameraId" element={<CameraDetailPage />} />
      </Routes>
    </>
  );
}

