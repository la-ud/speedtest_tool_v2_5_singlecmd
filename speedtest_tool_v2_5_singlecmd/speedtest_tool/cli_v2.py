"""
CLI v2 (ASCII UI) — entrypoint:
python -m speedtest_tool.cli_v2 --mode advance
"""
from __future__ import annotations

import argparse
from .core import SpeedTester
from . import __version__
from .ui_ascii import run_with_ascii_progress, print_table_basic, print_table_advance, quality_ratings, print_ratings_table
import time

def main(argv=None):
    p = argparse.ArgumentParser(prog='speedtest_tool v2 (ascii)', description='Terminal speedtest v2 (ASCII UI)')
    p.add_argument('--mode', '-m', choices=['basic','advance'], default='basic')
    p.add_argument('--nearby', type=int, default=5)
    p.add_argument('--estimate', type=int, default=30, help='Estimate seconds per phase (download/upload)')
    p.add_argument('--version', action='store_true')
    args = p.parse_args(argv)

    if args.version:
        print(__version__); return

    tester = SpeedTester(prefer_nearby_top=args.nearby)

    while True:
        print(f"Starting speedtest v2.5 — mode={args.mode} — prefer_nearby={args.nearby}")
        def run_func():
            # explicitly request basic or advance from core
            return tester.run(mode=args.mode)
        result = run_with_ascii_progress(run_func, estimate_per_phase=args.estimate)
        if 'err' in result:
            print("Error during speedtest:", result['err'])
        else:
            res = result.get('res', {})
            # Strictly branch UI based on args.mode to avoid touching unavailable fields
            if args.mode == 'basic':
                print_table_basic(res)
            else:
                print_table_advance(res)
            ratings = quality_ratings(res.get('download_bps'), res.get('upload_bps'), res.get('ping_ms'))
            print_ratings_table(ratings)
        # prompt to rerun
        try:
            ans = input("\nRun another test? (y/N): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            ans = 'n'
        if ans not in ('y','yes'):
            print("Exiting. Thank you.")
            break

if __name__ == '__main__':
    main()
