"""
ASCII terminal UI for speedtest v2.5 — safe handling of basic vs advance modes.
No external UI dependencies.
"""
from __future__ import annotations

import sys
import time
import threading
from typing import Dict, Any, Optional

# ANSI colors
CSI = "\x1b["
RESET = CSI + "0m"
BOLD = CSI + "1m"
FG_GREEN = CSI + "32m"
FG_CYAN = CSI + "36m"
FG_MAGENTA = CSI + "35m"
FG_YELLOW = CSI + "33m"
FG_RED = CSI + "31m"

def human_bps(bps: Optional[float]) -> str:
    if bps is None:
        return "n/a"
    units = ["bps", "Kbps", "Mbps", "Gbps"]
    val = float(bps)
    i = 0
    while val >= 1000 and i < len(units) - 1:
        val /= 1000.0
        i += 1
    return f"{val:.2f} {units[i]}"

class ASCIIProgress:
    def __init__(self, label: str = "Running", total_seconds: Optional[int] = None):
        self.label = label
        self.total_seconds = total_seconds
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()
        # clear line
        sys.stdout.write("\r" + " " * 120 + "\r")
        sys.stdout.flush()

    def _run(self):
        start = time.time()
        spinner = ["|", "/", "-", "-"]
        si = 0
        try:
            while not self._stop.is_set():
                elapsed = int(time.time() - start)
                m, s = divmod(elapsed, 60)
                timer = f"{m:02d}:{s:02d}"
                if self.total_seconds and self.total_seconds > 0:
                    pct = min(1.0, elapsed / self.total_seconds)
                    barlen = 40
                    filled = int(pct * barlen)
                    bar = "[" + "=" * filled + " " * (barlen - filled) + "]"
                    remain = int(max(0, self.total_seconds - elapsed))
                    rm_m, rm_s = divmod(remain, 60)
                    remain_str = f"{rm_m:02d}:{rm_s:02d}"
                    color = FG_MAGENTA if pct < 0.6 else (FG_YELLOW if pct < 0.9 else FG_GREEN)
                    line = f"{BOLD}{self.label}{RESET} {color}{spinner[si % len(spinner)]}{RESET} {color}{bar}{RESET} elapsed={timer} est_left={remain_str}"
                else:
                    line = f"{BOLD}{self.label}{RESET} {spinner[si % len(spinner)]} elapsed={timer}"
                sys.stdout.write("\r" + line)
                sys.stdout.flush()
                si += 1
                time.sleep(0.2)
        except KeyboardInterrupt:
            self._stop.set()
            raise

def run_with_ascii_progress(func, estimate_per_phase: int = 30):
    """Run func() while showing ascii progress animation.
    func() is expected to perform blocking speedtest work (download+upload).
    Since core doesn't provide progress callbacks, this function runs func in a
    background thread and animates a progress bar until it's done.
    Returns a dict: {'res': ..., 'err': ...}"""
    prog = ASCIIProgress(label="Speedtest", total_seconds=estimate_per_phase * 2)
    result = {}
    def target():
        try:
            r = func()
            result['res'] = r
        except Exception as e:
            result['err'] = e
        finally:
            try:
                prog.stop()
            except Exception:
                pass
    th = threading.Thread(target=target, daemon=True)
    th.start()
    prog.start()
    th.join()
    return result

def print_table_basic(res: Dict[str,Any]):
    # safe printing for basic mode: only uses fields that basic mode guarantees
    lines = []
    lines.append("+----------------------+----------------------+")
    lines.append("| Metric               | Value                |")
    lines.append("+----------------------+----------------------+")
    lines.append(f"| Download             | {human_bps(res.get('download_bps')):20} |")
    lines.append(f"| Upload               | {human_bps(res.get('upload_bps')):20} |")
    lines.append(f"| Latency (ms)         | {str(res.get('ping_ms') or 'n/a'):20} |")
    lines.append("+----------------------+----------------------+")
    print("\n".join(lines))

def print_table_advance(res: Dict[str,Any]):
    # advance table builds on top of basic but checks fields safely
    print_table_basic(res)
    srv = res.get('server') or {}
    client = res.get('client') or {}
    lines = []
    lines.append("\nServer & Client:")
    lines.append("+----------------------+----------------------+")
    lines.append("| Field                | Value                |")
    lines.append("+----------------------+----------------------+")
    sponsor = srv.get('sponsor') or srv.get('name') or 'n/a'
    country = srv.get('country') or 'n/a'
    host = srv.get('host') or srv.get('url') or 'n/a'
    dist = srv.get('d') or 'n/a'
    lat = srv.get('lat')
    lon = srv.get('lon')
    coords = f"{lat},{lon}" if (lat is not None and lon is not None) else "n/a"
    lines.append(f"| Server Sponsor       | {str(sponsor):20} |")
    lines.append(f"| Server Country       | {str(country):20} |")
    lines.append(f"| Server Host          | {str(host):20} |")
    lines.append(f"| Server Distance (km) | {str(dist):20} |")
    lines.append(f"| Server Coords        | {coords:20} |")
    lines.append(f"| Client IP            | {str(client.get('ip') or 'n/a'):20} |")
    lines.append(f"| Client ISP           | {str(client.get('isp') or 'n/a'):20} |")
    lines.append("+----------------------+----------------------+")
    print("\n".join(lines))

def quality_ratings(download_bps: Optional[float], upload_bps: Optional[float], latency_ms: Optional[float]):
    def to_mbps(bps):
        if bps is None:
            return 0.0
        return float(bps) / 1_000_000.0
    dl = to_mbps(download_bps)
    ul = to_mbps(upload_bps)
    lat = latency_ms or 9999

    # Gaming: low latency important
    game = int(max(1, min(10, round((max(0, 150 - lat) / 150) * 8 + (min(dl, 100) / 100) * 2))))
    # Streaming: mostly download
    if dl >= 100:
        stream = 10
    elif dl >= 50:
        stream = 9
    elif dl >= 25:
        stream = 8
    elif dl >= 10:
        stream = 6
    elif dl >= 5:
        stream = 4
    else:
        stream = 2
    # Browsing
    browse = int(max(1, min(10, round((max(0, 300 - lat) / 300) * 6 + (min(dl, 50) / 50) * 4))))
    # Video call: upload + latency
    vc = int(max(1, min(10, round((max(0, 200 - lat) / 200) * 5 + (min(ul, 20) / 20) * 5))))
    return {
        "Gaming": game,
        "Streaming (HD/4K)": stream,
        "Browsing": browse,
        "Video Call": vc
    }

def print_ratings_table(ratings: Dict[str,int]):
    lines = []
    lines.append("\nQuality Ratings (1-10):")
    lines.append("+--------------------------+--------+")
    lines.append("| Use Case                 | Score  |")
    lines.append("+--------------------------+--------+")
    for k,v in ratings.items():
        lines.append(f"| {k:24} | {str(v):6} |")
    lines.append("+--------------------------+--------+")
    print("\n".join(lines))
