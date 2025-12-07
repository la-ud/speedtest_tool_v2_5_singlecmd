import subprocess
import sys

def choose_mode():
    try:
        print("\nSelect mode:")
        print("  1) basic (download/upload, latency)")
        print("  2) advance (server, ip, MB used)")
        choice = input("Choose 1 or 2 (default 1): ").strip()
        if choice == "2":
            return "advance"
        return "basic"
    except (KeyboardInterrupt, EOFError):
        return "basic"

def main():
    mode = choose_mode()
    extra = sys.argv[1:]
    cmd = [sys.executable, "-m", "speedtest_tool.cli_v2", "--mode", mode] + extra
    try:
        rc = subprocess.call(cmd)
        sys.exit(rc)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        print("Failed to execute speedtest:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
