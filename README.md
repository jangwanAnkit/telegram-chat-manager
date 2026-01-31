# Telegram Chat Manager

A portable, self-hosted tool to manage your Telegram chats locally. Clean up unwanted groups, channels, and users with an easy-to-use web interface or CLI.

## Features

- 📊 **View Statistics** - See all your chats categorized (groups, channels, users)
- 🗑️ **Delete Chats** - Single or bulk deletion of unwanted chats
- 📥 **Export Data** - Export chat lists to **JSON** or **CSV**
- 🔍 **Spam Analysis** - Detect deleted accounts, bots, scam/fake users
- � **Session Persistence** - "Remember Me" functionality (auto-login)
- 🌐 **Web UI** - Modern dashboard with Dark Theme & Glassmorphism
- ⚡ **FastAPI Powered** - High-performance async backend
- 📱 **Responsive Design** - Works on mobile, tablet, and desktop
- 📦 **Single Executable** - Package as standalone .exe/binary


## 🚀 Quick Download & Run (No Install)

The easiest way to use the application without installing Python or dependencies.

1. **Download**: Get the latest release for your OS from the **Releases** page.
   - **Windows**: `TelegramChatManager.exe`
   - **Linux/Mac**: `TelegramChatManager`
2. **Run**:
   - **Windows**: Double-click the file. (If SmartScreen appears, click "More info" > "Run anyway").
   - **Linux/Mac**: Open terminal, make it executable (`chmod +x TelegramChatManager`), and run it (`./TelegramChatManager`).
3. **Start**: The web dashboard will open automatically in your browser at `http://localhost:5000`.

## Quick Start (Run from Source)

### Prerequisites

- Python 3.8 or higher
- Telegram API credentials (get from https://my.telegram.org/apps)

### Installation

```bash
# Clone or download the repository
cd telegram_user_mgmt

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
Web interface (default):
```bash
python main.py
# Opens at http://localhost:5000
```

Custom port:
```bash
python main.py --port 8080
```

CLI Mode (legacy):
```bash
python main.py --cli
```

## Usage Guide

### First Time Setup

1. **Get API Credentials**:
   - Visit https://my.telegram.org/apps
   - Login with your phone number
   - Click "API development tools"
   - Create app with:
     - App title: `Chat Manager`
     - Short name: `chatmgr`
     - Platform: `Desktop`
   - Copy your **API ID** and **API Hash**

2. **Enter Credentials**:
   - Open the web interface (browser opens automatically)
   - Enter API ID, API Hash
   - Click "Save Configuration"

3. **Connect**:
   - Enter your Phone Number and click "Connect"
   - You'll receive a code on your Telegram app
   - Enter the code (and 2FA password if enabled)
   - **"Remember Me"**: Your session is saved for auto-login on restart

4. **Manage Chats**:
   - View statistics dashboard
   - Filter by Groups, Channels, or Users
   - Filter by Groups, Channels, or Users
   - **Export**: Download as JSON or CSV
   - **Spam Analysis**: Find and bulk-delete "Ghost" accounts
   - **Delete**: Select multiple chats and delete them in one go

## Project Structure

```
telegram_user_mgmt/
├── main.py                    # Main launcher (Web and CLI modes)
├── build.py                   # Build script for packaging
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── TECH.md                    # Technical documentation for developers
├── .gitignore                # Git ignore rules
├── src/                      # Source code
│   ├── cli_manager.py       # CLI version (interactive terminal)
│   ├── fastapi_manager.py   # Web UI (FastAPI + modern dark theme)
│   └── portable_manager.py  # Pre-configurable portable version
├── data/                     # Data directory (gitignored)
│   └── output/              # Generated files
│       ├── *.json           # Exported chat lists
│       ├── *.session        # Telegram session files
│       └── telegram_config.json  # User credentials
├── templates/               # Web UI templates (auto-generated)
│   └── index.html          # Main interface HTML
└── scripts/                # Utility scripts
```

## Web Interface Features

### Dashboard
- **Statistics Cards**: Total chats, Groups, Channels, Users
- **Quick Actions**: Filter by category, export data, analyze spam
- **Responsive Layout**: Works on all screen sizes

### Chat Management
- **View All Chats**: Scrollable list with type icons and badges
- **Filter Options**: Show only Groups, Channels, or Users
- **Delete**: Click "Delete" button with confirmation dialog
- **Badges**: Visual indicators for Deleted, Bot, Scam, Verified accounts

### Spam Analysis
Automatically categorizes users:
- **Deleted Users**: Accounts that no longer exist
- **No Messages**: Empty chats with no interaction
- **Bots**: Automated accounts
- **Scam/Fake Users**: Flagged by Telegram
- **Active Chats**: Normal conversations

### Export
Download chat lists for offline analysis:
- **Formats**: JSON (raw data) or CSV (Excel compatible)
- **Types**: Groups, Channels, Users

## CLI Mode

Interactive terminal menu with options:
1. Show statistics
2. Analyze user chats (find spam/unused)
3. List all groups
4. List all channels
5. List deleted users
6. List users with no interaction
7. List scam/fake users
8. Export groups to JSON
9. Export channels to JSON
10. Export spam users to JSON
11. Export all users to JSON
12. Delete from JSON file
13. Interactive delete users (one by one)
14. Refresh data
15. Exit

## Building for Distribution

### Single Executable

Create a standalone executable with PyInstaller:

```bash
# Build web version (single file)
python build.py --mode web --onefile

# Build CLI version
python build.py --mode cli --onefile

# Build and create full distribution package
python build.py --clean --package
```

Output locations:
- **Windows**: `dist/TelegramChatManager.exe`
- **Mac/Linux**: `dist/TelegramChatManager`
- **Package**: `dist/TelegramChatManager-*.zip`

### Running the Executable

The executable is **portable** - no installation needed:
1. Download/copy the single file
2. Double-click to run
3. Browser opens automatically
4. Follow setup wizard

## Data Storage

All data is stored **locally** on your computer:

- **Credentials**: `data/output/telegram_config.json`
- **Session**: `data/output/*.session` (keeps you logged in)
- **Exports**: `data/output/*.json` (chat lists)

**Security Notes**:
- ✅ 100% local - no data sent to external servers
- ✅ Credentials never leave your machine
- ✅ Session files contain auth tokens - keep them secure
- ⚠️ Don't commit `data/output/` to git (already gitignored)

## Architecture Modes

### Web Mode (default)
- **Framework**: FastAPI + Uvicorn
- **Async**: Native async/await support
- **UI**: Dark theme with JetBrains Mono, glassmorphism design
- **Best For**: Stable Telegram API integration
- **Pros**: No event loop issues, better performance, auto API docs
- **Features**: Error handling middleware, request logging, health checks

### CLI Mode (`--cli`)
- **Interface**: Terminal/Command line
- **Best For**: Automation, scripting, power users
- **Pros**: No browser needed, scriptable

## Troubleshooting

### "TemplateNotFound: index.html" Error
**Solution**: Templates are auto-generated. Just restart the app:
```bash
python main.py
```

### Can't Connect to Telegram
- Check internet connection
- Verify API credentials are correct
- Ensure phone number format includes country code (e.g., `+1234567890`)
- Check if Telegram is blocked by firewall

### Browser Doesn't Open Automatically
- Manually visit: http://localhost:5000
- Check if port 5000 is available
- Try different port: `python main.py --port 8080`

### Windows Protected Your PC (SmartScreen)
- Click "More info"
- Click "Run anyway"
- This happens because the executable isn't code-signed

## Dependencies

Core:
- `telethon>=1.28.5` - Telegram API client
- `fastapi>=0.104.0` - Async web framework
- `uvicorn>=0.24.0` - ASGI server
- `pydantic>=2.5.0` - Data validation

Build:
- `pyinstaller>=5.13.0` - Create standalone executables

## Security & Privacy

- 🔒 **Local Only**: All processing happens on your machine
- 🔒 **No Cloud**: Nothing uploaded to external servers
- 🔒 **Open Source**: You can audit the code
- 🔒 **Session Based**: Uses Telegram's official session mechanism
- ⚠️ **Warning**: Deleted chats cannot be recovered!

## API Endpoints

Auto-generated API docs available at:
- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc

Main endpoints:
- `GET /` - Web interface
- `GET /health` - Health check
- `POST /api/setup` - Save credentials
- `POST /api/connect` - Connect to Telegram
- `POST /api/verify` - Verify with code
- `GET /api/chats` - Get all chats
- `GET /api/analyze` - Analyze spam users
- `POST /api/delete/{chat_id}` - Delete a chat
- `GET /api/export/{type}` - Export chats (groups/channels/users)

## Contributing

This is a personal tool that can be extended:
- Add new analysis features
- Improve UI/UX
- Add bulk operations
- Create additional export formats

See `TECH.md` for technical architecture details.

## License

MIT License - Use at your own risk.

**⚠️ Important Warnings**:
1. Deleted chats cannot be recovered
2. Always backup important data before bulk deletion
3. Keep your session files secure
4. This tool has full access to your Telegram account - use carefully

## Support

For issues or questions:
1. Check Troubleshooting section above
2. Review TECH.md for technical details
3. Check the code - it's fully open source

---
