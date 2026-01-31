#!/usr/bin/env python3
"""
Telegram Chat Manager - Main Launcher
Supports CLI and Web (FastAPI) modes
"""

import sys
import os
import argparse
import webbrowser
import threading

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def main():
    parser = argparse.ArgumentParser(
        description="Telegram Chat Manager - Manage your Telegram chats locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              # Start web interface (default)
  python main.py --cli        # Start CLI mode
  python main.py --port 8080  # Use custom port
        """,
    )
    parser.add_argument(
        "--cli", action="store_true", help="Run in CLI mode (terminal interface)"
    )
    parser.add_argument(
        "--port", type=int, default=5000, help="Web server port (default: 5000)"
    )

    args = parser.parse_args()

    # Set data output directory
    os.environ["TELEGRAM_DATA_DIR"] = os.path.join(
        os.path.dirname(__file__), "data", "output"
    )

    if args.cli:
        # CLI Mode config
        pass
    else:
        # Web Mode - Configure logging for GUI startup
        if getattr(sys, "frozen", False):
            LOG_BASE = os.path.dirname(sys.executable)
        else:
            LOG_BASE = os.path.dirname(os.path.abspath(__file__))

        log_dir = os.path.join(LOG_BASE, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "app.log")

        # Redirect stdout/stderr to log file for windowed mode
        if args.cli is False:  # Meaning web/GUI mode
            sys.stdout = open(log_file, "a")
            sys.stderr = open(log_file, "a")

    if args.cli:
        print("Starting Telegram Chat Manager in CLI mode...")
        from cli_manager import main as cli_main

        cli_main()
    else:
        # Default to FastAPI web mode
        import socket
        import time
        import urllib.request

        # Helper to check if a port is our app
        def is_our_app(port):
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1
                ) as response:
                    if response.status == 200:
                        import json

                        data = json.loads(response.read())
                        return data.get("app") == "TelegramChatManager"
            except:
                return False
            return False

        # Find available port or open existing instance
        target_port = args.port
        max_retries = 10

        for i in range(max_retries):
            current_port = args.port + i
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("127.0.0.1", current_port))
            sock.close()

            if result == 0:
                # Port is busy
                print(f"[WARNING] Port {current_port} is busy.")
                if is_our_app(current_port):
                    print("[OK] Found existing instance of TelegramChatManager!")
                    print("[OPEN] Opening browser...")
                    # specific domain for better branding (resolves to 127.0.0.1)
                    webbrowser.open(
                        f"http://telegram-manager.localtest.me:{current_port}"
                    )
                    sys.exit(0)
                else:
                    print(
                        f"[ERROR] Port {current_port} is used by another application. Trying next..."
                    )
            else:
                # Port is free!
                target_port = current_port
                break

        print("Starting Telegram Chat Manager...")
        url = f"http://telegram-manager.localtest.me:{target_port}"
        print(f"[URL] Web interface: {url}")
        print("[INFO] Press Ctrl+C to stop the server")

        # Auto-open browser after a short delay
        def open_browser():
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()

        import uvicorn
        from fastapi_manager import app

        # Bind to 127.0.0.1 but user accesses via localtest.me
        uvicorn.run(app, host="127.0.0.1", port=target_port, log_level="info")


if __name__ == "__main__":
    main()
