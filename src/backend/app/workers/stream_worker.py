from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2

STOP = False


def _handle_signal(signum, frame):  # noqa: ARG001
    global STOP
    STOP = True
    print(f"[stream_worker] signal {signum}, stopping...", flush=True)


def _even_dim(v: int) -> int:
    return max(2, int(v) - (int(v) % 2))


def _pause_path(control_dir: Path) -> Path:
    return control_dir / "pause.flag"


def _build_ffmpeg_cmd(
    *,
    ffmpeg_binary: str,
    out_w: int,
    out_h: int,
    fps: float,
    rtsp_push_url: str,
) -> list[str]:
    return [
        ffmpeg_binary,
        "-y",
        "-loglevel",
        "warning",
        "-probesize",
        "32",
        "-analyzeduration",
        "0",
        "-fflags",
        "nobuffer",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{out_w}x{out_h}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-bf",
        "0",
        "-pix_fmt",
        "yuv420p",
        "-rtsp_transport",
        "tcp",
        "-f",
        "rtsp",
        rtsp_push_url,
    ]


def _terminate_ffmpeg(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    try:
        if proc.stdin:
            proc.stdin.close()
    except BrokenPipeError:
        pass
    except Exception:
        pass
    try:
        proc.terminate()
        proc.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    try:
        proc.kill()
        proc.wait(timeout=2)
    except Exception:
        pass


def _write_frame(ff: subprocess.Popen, frame) -> None:
    if ff.stdin is None:
        raise RuntimeError("FFmpeg stdin is not available")
    data = frame if isinstance(frame, (bytes, bytearray)) else frame.tobytes()
    ff.stdin.write(data)
    ff.stdin.flush()


@dataclass
class WorkerArgs:
    camera_id: str
    video_path: Path
    control_dir: Path
    rtsp_push_url: str
    ffmpeg_binary: str
    fps: Optional[float]
    width: Optional[int]
    height: Optional[int]
    loop: bool


def parse_args(argv: list[str]) -> WorkerArgs:
    parser = argparse.ArgumentParser(description="Direct file-to-RTSP stream worker (OpenCV + FFmpeg)")
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--video-path", required=True)
    parser.add_argument("--control-dir", required=True)
    parser.add_argument("--rtsp-push-url", required=True)
    parser.add_argument("--ffmpeg-binary", required=True)
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    loop_group = parser.add_mutually_exclusive_group()
    loop_group.add_argument("--loop", action="store_true", default=True)
    loop_group.add_argument("--no-loop", action="store_true", default=False)

    ns = parser.parse_args(argv)
    loop = True if ns.loop and not ns.no_loop else False

    return WorkerArgs(
        camera_id=ns.camera_id,
        video_path=Path(ns.video_path),
        control_dir=Path(ns.control_dir),
        rtsp_push_url=ns.rtsp_push_url.strip(),
        ffmpeg_binary=ns.ffmpeg_binary.strip() or "ffmpeg",
        fps=ns.fps,
        width=ns.width,
        height=ns.height,
        loop=loop,
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    print(
        f"[stream_worker] camera_id={args.camera_id} video={args.video_path} "
        f"rtsp={args.rtsp_push_url} loop={args.loop}",
        flush=True,
    )

    if not args.video_path.exists():
        print("[stream_worker] ERROR: video path does not exist", flush=True)
        return 2

    control_dir = args.control_dir
    try:
        control_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[stream_worker] ERROR: control dir: {e}", flush=True)
        return 2

    cap = cv2.VideoCapture(str(args.video_path))
    if not cap.isOpened():
        print("[stream_worker] ERROR: OpenCV cannot open video", flush=True)
        return 3

    ff: Optional[subprocess.Popen] = None
    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS)
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or 640
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or 480

        fps = float(args.fps) if args.fps and float(args.fps) > 0 else (float(src_fps) if src_fps and src_fps > 0 else 30.0)
        if fps <= 0:
            fps = 30.0

        out_w = args.width or src_w
        out_h = args.height or src_h
        out_w = _even_dim(out_w)
        out_h = _even_dim(out_h)

        print(f"[stream_worker] source={src_w}x{src_h}@{src_fps} output={out_w}x{out_h}@{fps}", flush=True)

        cmd = _build_ffmpeg_cmd(
            ffmpeg_binary=args.ffmpeg_binary,
            out_w=out_w,
            out_h=out_h,
            fps=fps,
            rtsp_push_url=args.rtsp_push_url,
        )
        print("[stream_worker] FFMPEG_CMD: " + " ".join(cmd), flush=True)

        ff = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            # Inherit stderr so FFmpeg startup errors show up in the worker logs
            # (backend captures worker stdout/stderr to data/logs/camera_{id}.log).
            stderr=None,
            stdout=subprocess.DEVNULL,
        )
        if ff.stdin is None:
            print("[stream_worker] ERROR: failed to open FFmpeg stdin", flush=True)
            return 4
        # Give FFmpeg a moment to fail fast (bad URL, missing codec, etc.)
        time.sleep(0.25)
        if ff.poll() is not None:
            print(f"[stream_worker] ERROR: FFmpeg exited early rc={ff.returncode}", flush=True)
            return 6

        pause_file = _pause_path(control_dir)
        last_frame = None
        frame_delay = 1.0 / fps

        while not STOP:
            paused = False
            try:
                paused = pause_file.exists()
            except OSError:
                paused = False

            if paused:
                if last_frame is None:
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        if frame.shape[1] != out_w or frame.shape[0] != out_h:
                            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)
                        last_frame = frame
                if last_frame is not None and ff.poll() is None:
                    try:
                        _write_frame(ff, last_frame)
                    except BrokenPipeError:
                        print("[stream_worker] FFmpeg stdin closed while paused", flush=True)
                        return 5
                time.sleep(frame_delay)
                continue

            ok, frame = cap.read()
            if not ok or frame is None:
                if args.loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                print("[stream_worker] end of video (no loop)", flush=True)
                break

            if frame.shape[1] != out_w or frame.shape[0] != out_h:
                frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)

            last_frame = frame
            if ff.poll() is not None:
                print(f"[stream_worker] ERROR: FFmpeg exited rc={ff.returncode}", flush=True)
                return 6
            try:
                _write_frame(ff, frame)
            except BrokenPipeError:
                print("[stream_worker] FFmpeg stdin closed", flush=True)
                return 5
            time.sleep(frame_delay)

        return 0
    except FileNotFoundError as e:
        print(f"[stream_worker] ERROR: {e}", flush=True)
        return 4
    except Exception as e:
        print(f"[stream_worker] ERROR: {e}", flush=True)
        return 4
    finally:
        cap.release()
        _terminate_ffmpeg(ff)
        print("[stream_worker] stopped", flush=True)
        time.sleep(0.05)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    raise SystemExit(main(sys.argv[1:]))
