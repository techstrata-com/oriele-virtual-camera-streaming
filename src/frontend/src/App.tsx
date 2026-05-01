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
            <b>Virtual Camera Platform</b>
            <span className="muted">Upload videos → expose as /dev/videoX</span>
          </div>
          <nav className="nav">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
              Videos
            </NavLink>
            <NavLink to="/cameras" className={({ isActive }) => (isActive ? "active" : "")}>
              Cameras
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

