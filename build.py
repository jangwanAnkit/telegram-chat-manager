# Telegram Chat Manager - Build and Package Script
# Creates a single executable file for distribution

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


def print_banner():
    print("""
╔════════════════════════════════════════════════════════════════════════╗
║               TELEGRAM CHAT MANAGER - BUILD SYSTEM                     ║
║                      Package Builder v1.0                              ║
╚════════════════════════════════════════════════════════════════════════╝
    """)


def check_dependencies():
    """Check if required tools are installed"""
    print("📦 Checking dependencies...")

    try:
        import telethon
        import flask

        print("✅ Python dependencies OK")
    except ImportError:
        print("❌ Missing Python dependencies")
        print("   Run: pip install -r requirements.txt")
        return False

    try:
        subprocess.run(["pyinstaller", "--version"], capture_output=True, check=True)
        print("✅ PyInstaller OK")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller not found")
        print("   Run: pip install pyinstaller")
        return False

    return True


def clean_build_dirs():
    """Clean build and dist directories"""
    print("🧹 Cleaning build directories...")
    dirs_to_clean = ["build", "dist", "__pycache__", ".pytest_cache"]

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   Removed {dir_name}/")

    # Clean .pyc files
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".pyc") or file.endswith(".spec"):
                os.remove(os.path.join(root, file))


def create_executable(mode="web", onefile=True, windowed=False):
    """Create executable using PyInstaller"""
    print(f"🔨 Building executable (mode: {mode}, onefile: {onefile}, windowed: {windowed})...")

    if mode == "cli":
        script = "src/cli_manager.py"
        name = "TelegramChatManager-CLI"
    else:
        script = "main.py"
        name = "TelegramChatManager"

    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    
    # Windowed mode (no console) - for GUI apps
    if windowed and mode == "web":
        cmd.append("--windowed")

    # Add data directories
    cmd.extend(["--add-data", "src:src"])
    cmd.extend(["--add-data", "data:data"])
    cmd.extend(["--add-data", "templates:templates"])

    # Hidden imports - FastAPI stack
    hidden_imports = [
        # Telethon
        "telethon.sync",
        "telethon.tl.types",
        "telethon.tl.functions.messages",
        "telethon.tl.functions.channels",
        "telethon.errors",
        # FastAPI + Uvicorn (all submodules used)
        "fastapi",
        "fastapi.responses",
        "fastapi.middleware",
        "fastapi.staticfiles",
        "fastapi.exceptions",
        "uvicorn",
        "uvicorn.main",
        "uvicorn.config",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        # Starlette
        "starlette",
        "starlette.responses",
        "starlette.routing",
        "starlette.middleware",
        "starlette.exceptions",
        "starlette.staticfiles",
        # Pydantic
        "pydantic",
        "pydantic_core",
        # Jinja (still needed for templates)
        "jinja2",
        "jinja2.ext",
        # Async
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        # HTTP
        "h11",
    ]

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # Exclude unnecessary modules to reduce size
    excludes = [
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "PIL",
        "Pillow",
    ]

    for exc in excludes:
        cmd.extend(["--exclude-module", exc])

    cmd.extend(["--name", name])
    cmd.append(script)

    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Build successful")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return False


def create_distribution_package():
    """Create a distribution package with all necessary files"""
    print("📦 Creating distribution package...")

    dist_dir = Path("dist")
    package_dir = dist_dir / "TelegramChatManager-Package"

    # Create package structure
    package_dir.mkdir(parents=True, exist_ok=True)

    # Copy executable
    exe_name = "TelegramChatManager"
    if sys.platform == "win32":
        exe_name += ".exe"

    src_exe = dist_dir / exe_name
    if src_exe.exists():
        shutil.copy(src_exe, package_dir / exe_name)
        print(f"   Copied {exe_name}")

    # Copy README
    readme_file = "README.md"
    if os.path.exists(readme_file):
        shutil.copy(readme_file, package_dir / readme_file)
        print(f"   Copied {readme_file}")

    # Create data directory structure
    (package_dir / "data" / "output").mkdir(parents=True, exist_ok=True)

    # Create start scripts
    if sys.platform == "win32":
        start_script = package_dir / "START.bat"
        start_script.write_text(
            "@echo off\necho Starting Telegram Chat Manager...\nTelegramChatManager.exe\npause"
        )
    else:
        start_script = package_dir / "start.sh"
        start_script.write_text(
            '#!/bin/bash\necho "Starting Telegram Chat Manager..."\n./TelegramChatManager'
        )
        os.chmod(start_script, 0o755)

    print(f"✅ Package created at: {package_dir}")

    # Create ZIP archive
    zip_name = f"TelegramChatManager-{sys.platform}"
    shutil.make_archive(str(dist_dir / zip_name), "zip", package_dir)
    print(f"✅ ZIP archive created: {zip_name}.zip")


def main():
    parser = argparse.ArgumentParser(description="Build Telegram Chat Manager")
    parser.add_argument(
        "--mode",
        choices=["cli", "web"],
        default="web",
        help="Build mode: cli or web (default: web)",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        default=True,
        help="Create single executable file (default: True)",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Create directory distribution instead of single file",
    )
    parser.add_argument(
        "--clean", action="store_true", help="Clean build directories before building"
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Create distribution package after building",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Build as GUI app (no console window) - double-click to open",
    )

    args = parser.parse_args()

    print_banner()

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Clean if requested
    if args.clean:
        clean_build_dirs()

    # Determine if onefile or onedir
    onefile = not args.onedir

    # Build executable
    if create_executable(mode=args.mode, onefile=onefile, windowed=args.gui):
        print("\n✨ Build completed successfully!")
        print(f"📍 Executable location: dist/")

        # Create package if requested
        if args.package:
            create_distribution_package()

        print("\n🚀 Ready to distribute!")
        print("   Share the file(s) in the dist/ folder")
    else:
        print("\n❌ Build failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
