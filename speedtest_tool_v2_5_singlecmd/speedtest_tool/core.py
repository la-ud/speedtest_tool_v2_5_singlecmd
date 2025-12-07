"""
Core runner that wraps speedtest-cli (Speedtest.net) library.
It prefers nearby servers by selecting randomly among the N nearest servers
when possible. It performs download/upload and returns structured results.

Note: speedtest-cli does not expose per-byte progress callbacks in its
public API, so the package runs the operations in background threads and
provides a UI module that shows elapsed time and an estimated progress bar.
"""
from __future__ import annotations

import speedtest
import random
import threading
from typing import Optional, Dict, Any, List


class SpeedTester:
    def __init__(self, prefer_nearby_top: int = 5):
        self.prefer_nearby_top = max(1, prefer_nearby_top)
        self._st: Optional[speedtest.Speedtest] = None

    def _init_speedtest(self) -> None:
        """Create Speedtest object and attempt to select a nearby server."""
        st = speedtest.Speedtest()
        self._st = st
        # Try to fetch server list and prefer nearby
        servers = {}
        try:
            servers = st.get_servers()
        except Exception:
            # Could not fetch servers; fall back to builtin best-server
            try:
                st.get_best_server()
            except Exception:
                pass
            return

        # Flatten server dict
        server_list: List[Dict[str, Any]] = []
        for _, lst in servers.items():
            server_list.extend(lst)

        # If distance present, sort by it
        with_distance = [s for s in server_list if s.get('d') is not None]
        if with_distance:
            with_distance.sort(key=lambda x: float(x.get('d', 1e9)))
            top = with_distance[: self.prefer_nearby_top]
            chosen = random.choice(top)
            # Choose this server (speedtest lib expects a list of server dicts)
            try:
                st.get_best_server([chosen])
            except Exception:
                # fallback to library default
                try:
                    st.get_best_server()
                except Exception:
                    pass
        else:
            try:
                st.get_best_server()
            except Exception:
                pass

    def run(self, mode: str = 'basic') -> Dict[str, Any]:
        """Run speedtest in the selected mode. Returns a dict of results.

        mode: 'basic' or 'advance'
        """
        mode = mode.lower()
        if mode not in ('basic', 'advance'):
            raise ValueError("mode must be 'basic' or 'advance'")

        if self._st is None:
            self._init_speedtest()
        st = self._st or speedtest.Speedtest()

        results: Dict[str, Any] = {
            'download_bps': None,
            'upload_bps': None,
            'ping_ms': None,
            'server': None,
            'client': None,
            'errors': {},
        }

        # We'll run download then upload sequentially but in threads to allow UI to update.
        download_out: Dict[str, Any] = {}
        upload_out: Dict[str, Any] = {}

        def _do_download():
            try:
                download_out['bits'] = st.download()
            except Exception as e:
                results['errors']['download'] = str(e)

        def _do_upload():
            try:
                # pre_allocate may raise on some platforms; allow default
                upload_out['bits'] = st.upload(pre_allocate=False)
            except Exception as e:
                results['errors']['upload'] = str(e)

        # Optional ping measurement depends on st.results
        # Start download
        d_thread = threading.Thread(target=_do_download, daemon=True)
        d_thread.start()
        d_thread.join()

        # Start upload
        u_thread = threading.Thread(target=_do_upload, daemon=True)
        u_thread.start()
        u_thread.join()

        if 'bits' in download_out:
            results['download_bps'] = float(download_out['bits'])
        if 'bits' in upload_out:
            results['upload_bps'] = float(upload_out['bits'])

        # Try to read ping/server/client from st.results
        try:
            rs = st.results
            # st.results may be an object with attributes or a dict-like object
            ping = getattr(rs, 'ping', None)
            if ping is None:
                try:
                    ping = rs.get('ping')
                except Exception:
                    ping = None
            results['ping_ms'] = ping

            try:
                server = getattr(rs, 'server', None)
                if server is None and hasattr(rs, 'dict'):
                    server = rs.dict().get('server')
                if server is None and isinstance(rs, dict):
                    server = rs.get('server')
                results['server'] = server
            except Exception:
                results['server'] = None

            try:
                client = getattr(rs, 'client', None)
                if client is None and hasattr(rs, 'dict'):
                    client = rs.dict().get('client')
                if client is None and isinstance(rs, dict):
                    client = rs.get('client')
                results['client'] = client
            except Exception:
                results['client'] = None

        except Exception:
            # ignore
            pass

        # If mode basic, prune additional details
        if mode == 'basic':
            return {
                'download_bps': results['download_bps'],
                'upload_bps': results['upload_bps'],
                'ping_ms': results['ping_ms'],
                'errors': results['errors'],
            }

        return results
