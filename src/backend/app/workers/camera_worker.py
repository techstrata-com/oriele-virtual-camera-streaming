from __future__ import annotations

import argparse
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import pyvirtualcam
from pyvirtualcam import PixelFormat


STOP = False


def _handle_signal(signum, frame):  # noqa: ARG001
    global STOP
    STOP = True
    print(f"[worker] Received signal {signum}, stopping...", flush=True)


@dataclass
class WorkerArgs:
    camera_id: str
    video_path: Path
    device_path: str
    fps: Optional[float]
    width: Optional[int]
    height: Optional[int]
    loop: bool


def parse_args(argv: list[str]) -> WorkerArgs:
    parser = argparse.ArgumentParser(description="Virtual camera worker")
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--video-path", required=True)
    parser.add_argument("--device-path", required=True)
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
        device_path=ns.device_path,
        fps=ns.fps,
        width=ns.width,
        height=ns.height,
        loop=loop,
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    print(f"[worker] camera_id={args.camera_id}", flush=True)
    print(f"[worker] video_path={args.video_path}", flush=True)
    print(f"[worker] device_path={args.device_path}", flush=True)
    print(f"[worker] fps={args.fps} width={args.width} height={args.height} loop={args.loop}", flush=True)

    if not args.video_path.exists():
        print("[worker] ERROR: video path does not exist", flush=True)
        return 2

    cap = cv2.VideoCapture(str(args.video_path))
    if not cap.isOpened():
        print("[worker] ERROR: OpenCV cannot open video", flush=True)
        return 3

    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS)
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or 640
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or 480

        fps = args.fps or (float(src_fps) if src_fps and src_fps > 0 else 30.0)
        out_w = args.width or src_w
        out_h = args.height or src_h

        print(f"[worker] source={src_w}x{src_h}@{src_fps} output={out_w}x{out_h}@{fps}", flush=True)

        with pyvirtualcam.Camera(
            width=out_w,
            height=out_h,
            fps=fps,
            device=args.device_path,
            fmt=PixelFormat.BGR,
            print_fps=False,
        ) as cam:
            print(f"[worker] pyvirtualcam started on {cam.device}", flush=True)

            while not STOP:
                ok, frame = cap.read()
                if not ok or frame is None:
                    if args.loop:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    print("[worker] end of video", flush=True)
                    break

                if frame.shape[1] != out_w or frame.shape[0] != out_h:
                    frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)

                cam.send(frame)
                cam.sleep_until_next_frame()

    except Exception as e:
        print(f"[worker] ERROR: {e}", flush=True)
        return 4
    finally:
        cap.release()
        print("[worker] stopped", flush=True)
        time.sleep(0.05)

    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    raise SystemExit(main(sys.argv[1:]))

