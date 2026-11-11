"""Preflight checks for the Windows Pepper gateway host."""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def report(ok: bool, name: str, detail: str) -> bool:
    mark = "OK" if ok else "FAIL"
    print(f"[{mark}] {name}: {detail}")
    return ok


def tcp_check(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} reachable"
    except OSError as exc:
        return False, f"{host}:{port} unreachable ({exc})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Pepper gateway deployment preflight")
    parser.add_argument("--runtime-only", action="store_true",
                        help="skip Pepper and cloud network probes")
    args = parser.parse_args()

    ok = True
    pepper_dir = Path(__file__).resolve().parent
    workspace = pepper_dir.parent.parent

    py_ok = sys.version_info >= (3, 9)
    ok &= report(py_ok, "Python 3", f"{sys.version.split()[0]} ({sys.executable})")

    try:
        import websocket  # noqa: F401
        ws_detail = f"websocket-client {getattr(websocket, '__version__', 'installed')}"
        ok &= report(True, "WebSocket", ws_detail)
    except ImportError as exc:
        ok &= report(False, "WebSocket", str(exc))

    audio_format = os.environ.get("PEPPER_AUDIO_FORMAT", "opus").lower()
    if audio_format == "opus":
        try:
            opus_bin = Path(os.environ.get(
                "PEPPER_OPUS_BIN",
                workspace / ".runtime" / "libopus" / "mingw32" / "bin",
            ))
            if os.name == "nt" and opus_bin.is_dir():
                os.environ["PATH"] = str(opus_bin) + os.pathsep + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(opus_bin))
            import opuslib
            opuslib.Encoder(16000, 1, "voip")
            opuslib.Decoder(16000, 1)
            ok &= report(True, "Opus", "encoder and decoder initialized")
        except Exception as exc:
            ok &= report(False, "Opus", str(exc))
    else:
        report(True, "Audio", f"format={audio_format} (server must support it)")

    sdk_env = os.environ.get("PEPPER_SDK_ENV")
    candidates = [Path(sdk_env)] if sdk_env else sorted(
        workspace.glob("pynaoqi-python2.7-*-win32-vs2013")
    )
    sdk = next((path for path in candidates if path.is_dir()), None)
    ok &= report(sdk is not None, "pynaoqi SDK", str(sdk or "not found"))

    py2_env = os.environ.get("PEPPER_PY2_EXE")
    py2_candidates = [Path(py2_env)] if py2_env else [
        workspace / ".runtime" / "Python27" / "python.exe",
        Path(r"D:\Python27\python.exe"),
        Path(r"C:\Python27\python.exe"),
    ]
    py2 = next((path for path in py2_candidates if path.is_file()), None)
    ok &= report(py2 is not None, "Python 2.7 x86", str(py2 or "not found"))
    if py2 is not None and sdk is not None:
        bridge_env = dict(os.environ)
        bridge_env["PYTHONPATH"] = str(sdk / "lib")
        bridge_env["PATH"] = os.pathsep.join(
            (str(sdk / "bin"), str(sdk / "lib"), bridge_env.get("PATH", ""))
        )
        probe = subprocess.run(
            [str(py2), "-c",
             "import platform,sys; assert sys.version_info[:2] == (2,7); "
             "assert platform.architecture()[0] == '32bit'; import qi,naoqi"],
            env=bridge_env,
            capture_output=True,
            text=True,
        )
        detail = "qi and naoqi imported" if probe.returncode == 0 else (
            probe.stderr.strip() or f"probe exited {probe.returncode}"
        )
        ok &= report(probe.returncode == 0, "NAOqi bridge runtime", detail)

    if args.runtime_only:
        return 0 if ok else 1

    pepper_host = os.environ.get("PEPPER_IP_ENV", "192.168.0.93")
    pepper_ok, detail = tcp_check(pepper_host, 9559)
    ok &= report(pepper_ok, "Pepper broker", detail)

    cloud_url = os.environ.get(
        "SUIYUE_CLOUD_WS", "ws://192.168.0.87:8000/xiaozhi/v1"
    )
    parsed = urlparse(cloud_url)
    cloud_host = parsed.hostname or ""
    cloud_port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    cloud_ok, detail = tcp_check(cloud_host, cloud_port)
    ok &= report(cloud_ok, "Cloud WebSocket", detail)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
