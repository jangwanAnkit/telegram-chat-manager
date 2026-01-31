# Telegram Chat Manager - Technical Documentation

## Overview

A self-hosted Python application for managing Telegram chats locally. Provides web UI and CLI interfaces to view, analyze, export, and delete Telegram chats (groups, channels, users).

## Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Chat Manager v2.0               │
├─────────────────────────────────────────────────────────────┤
│  Entry Point                                                │
│  └── main.py                                                │
│       ├── --cli → cli_manager.py (Terminal UI)              │
│       └── default → fastapi_manager.py (Web API)            │
├─────────────────────────────────────────────────────────────┤
│  Web Framework                                              │
│  ├── FastAPI + Uvicorn (async web server)                   │
│  ├── Error Handling Middleware (request logging, exceptions)│
│  └── Dark Theme UI (JetBrains Mono, glassmorphism)          │
├─────────────────────────────────────────────────────────────┤
│  Core Library                                               │
│  └── Telethon (Telegram MTProto API Client)                 │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                 │
│  ├── Config: data/output/telegram_config.json               │
│  ├── Session: data/output/*.session                         │
│  └── Exports: data/output/*.json                            │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

### Core Dependencies

| Component | Library | Purpose | Version |
|-----------|---------|---------|---------|
| **Telegram API** | `telethon` | MTProto client for Telegram | >=1.28.5 |
| **Web Framework** | `fastapi` | Async web server with auto-docs | >=0.104.0 |
| **ASGI Server** | `uvicorn` | Runs FastAPI application | >=0.24.0 |
| **Data Validation** | `pydantic` | Request/response models | >=2.5.0 |
| **Build Tool** | `pyinstaller` | Create standalone executables | >=5.13.0 |

### FastAPI Web Framework

```python
# FastAPI + Async Model with Error Handling
app = FastAPI()

# Custom exception handlers
@app.exception_handler(TelegramError)
async def telegram_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"error": exc.message})

# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    return await call_next(request)
```

**Features:**
- Native async/await support
- No event loop conflicts
- Automatic API documentation (Swagger, ReDoc)
- Custom exception handling middleware
- Request logging for debugging
- Health check endpoint (`/health`)
- Better performance with Pydantic validation

## Data Flow

### 1. Authentication Flow

```
User Input (API ID, Hash, Phone)
         ↓
POST /api/setup
         ↓
Save to telegram_config.json
         ↓
POST /api/connect
         ↓
TelegramClient.connect()
         ↓
Send code request → User receives SMS/App notification
         ↓
POST /api/verify (with code)
         ↓
client.sign_in() → Session file created
         ↓
Authorized ✓
```

### 2. Chat Data Flow

```
User requests chats
         ↓
GET /api/chats
         ↓
client.iter_dialogs() [async generator]
         ↓
Categorize entities:
   - User → Private chat
   - Channel + broadcast=True → Broadcast channel
   - Channel + megagroup=True → Supergroup
   - Chat → Basic group
         ↓
Return JSON with stats
         ↓
Frontend displays with filtering
```

### 3. Delete Flow

```
User clicks Delete button
         ↓
Confirmation dialog
         ↓
POST /api/delete/{chat_id}
         ↓
client.get_entity(chat_id)
         ↓
client.delete_dialog(entity)
         ↓
Refresh chat list
```

### 4. Export Flow

```
User clicks Export (JSON/CSV)
         ↓
GET /api/export/{type}?format={format}
         ↓
Iterate dialogs matching type
         ↓
Collect data (id, title, username, members, flags)
         ↓
Format:
  - JSON: Standard list of objects
  - CSV: Flattened structure (id, title, username, ...)
         ↓
Return FileResponse (download)
```

## File Structure

```
telegram_user_mgmt/
│
├── Entry Points
│   ├── main.py              # Main launcher, mode selector
│   └── build.py             # PyInstaller build script
│
├── Application Modes (src/)
│   ├── cli_manager.py       # Terminal UI, 15 menu options
│   ├── fastapi_manager.py   # Web app with dark theme UI
│   └── portable_manager.py  # Pre-configured portable version
│
├── Configuration
│   ├── requirements.txt     # Python dependencies
│   ├── .gitignore          # Git exclusions
│   └── telegram_chat_manager.spec  # PyInstaller spec
│
├── Documentation
│   ├── README.md           # User documentation
│   └── TECH.md            # This file - technical reference
│
├── Runtime Generated (data/output/)
│   ├── telegram_config.json    # API credentials (user-specific)
│   ├── *.session              # Telegram session (auth token)
│   ├── *_YYYYMMSS_HHMMSS.json # Exported chat lists
│   └── deletion_log_*.json    # Deletion operation logs
│
└── Auto-Generated (templates/)
    └── index.html           # Web UI HTML (created at runtime)
```

## Key Technical Decisions

### 1. Why Templates Are Generated at Runtime

**Problem:** Want single-file distribution
**Solution:** Embed HTML as Python string, write to disk on startup

```python
HTML_TEMPLATE = """<!DOCTYPE html>..."""  # Embedded in .py file

def create_templates():
    with open("templates/index.html", "w") as f:
        f.write(HTML_TEMPLATE)
```

**Benefits:**
- Single .exe can be distributed
- No external file dependencies
- Template always matches code version

**Drawbacks:**
- Slightly larger Python files
- First-run file creation

### 3. Session Management & Persistence
- **Config**: Stores API Keys + Phone Number (v1.1) in `telegram_config.json`
- **Session File**: `data/output/+1234.session` (Telethon SQlite)
- **Auto-Connect**: On startup, checks config for phone. If exists -> `TelegramClient(..., session_file)` -> `client.connect()`

**Security Model:**
- **Logout**: Calls `await client.log_out()` (Server invalidation) + Deletes local session file
- **Reset**: Wipes config + all session files + logs out from server
- **Credentials**: Stored locally in JSON/SQLite. No external transmission.

### 4. Async Strategy

```python
# FastAPI runs on asyncio natively
# Direct await works perfectly

await client.connect()
await client.send_code_request(phone)
```

### 5. Smart Startup & Instance Detection (v2.1)

`main.py` implements intelligent startup logic:

```
Start Application
       ↓
Try port 5000
       ↓
Port busy? ──No──> Start server on 5000
       │
      Yes
       ↓
Call /health on port 5000
       ↓
Response has "app": "TelegramChatManager"?
       │
      Yes → Open browser to existing instance → Exit
       │
       No → Try port 5001 (repeat up to 5009)
```

**Key Points:**
- Uses `localtest.me` domain (e.g., `telegram-manager.localtest.me:5000`)
- `*.localtest.me` is a public wildcard DNS that resolves to `127.0.0.1`
- No admin rights needed (no `/etc/hosts` editing)
- Graceful shutdown via `/api/shutdown` endpoint + UI button

### 6. Logging

- **File**: `logs/app.log` (next to executable)
- **Console**: Also logs to stdout (visible in terminal mode)
- Captures startup errors, connection issues, and request logs

## API Endpoints

Auto-generated docs at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

#### Health Check
```
GET /health
  Response: {"status": "healthy", "version": "2.0.0", "connected": false}
```

#### Authentication
```
POST /api/setup
  Body: {"api_id": "12345", "api_hash": "abc...", "phone": "+1234567890"}
  
POST /api/connect
  Response: {"status": "waiting_code", "needs_code": true}
  
POST /api/verify
  Body: {"code": "12345"} or {"password": "2fa_pass"}
  Response: {"status": "connected"}
```

#### Data Operations
```
GET /api/chats
  Response: {
    "chats": [...],
    "stats": {"total": 100, "groups": 30, "channels": 20, "users": 50}
  }

GET /api/analyze
  Response: {
    "counts": {"deleted": 5, "bots": 3, "scam": 2, ...},
    "users": {"deleted": [...], "bots": [...], ...}
  }

POST /api/delete/{chat_id}
  Response: {"success": true}

GET /api/export/{type}
  type: "groups" | "channels" | "users"
  Response: File download (JSON)
```

## Data Models

### Chat Types

```python
# User (Private chat)
{
    "id": 123456789,
    "type": "user",
    "title": "John Doe",
    "username": "johndoe",
    "is_deleted": false,
    "is_bot": false,
    "is_scam": false,
    "is_verified": false
}

# Group/Supergroup
{
    "id": -123456789,
    "type": "supergroup",  # or "group"
    "title": "My Group",
    "username": "mygroup",  # optional
    "members": 150
}

# Channel
{
    "id": -987654321,
    "type": "channel",
    "title": "News Channel",
    "username": "newschannel",
    "members": 5000
}
```

### Analysis Categories

```python
{
    "deleted": [users_with_deleted_accounts],
    "no_messages": [users_with_empty_chats],
    "only_incoming": [users_never_replied_to],
    "bots": [bot_accounts],
    "scam": [accounts_flagged_scam],
    "fake": [accounts_flagged_fake],
    "active": [normal_conversations]
}
```

## Security Considerations

### Data Storage
- ✅ All data local (data/output/)
- ✅ Credentials in JSON (not encrypted, but local only)
- ✅ Sessions in .session files (Telegram's format)
- ✅ Gitignored (never committed)

### Telegram API
- Uses official Telethon library
- MTProto protocol (Telegram's native)
- Rate limiting handled by library
- No proxy/VPN required

### Risks
- ⚠️ Session files contain auth tokens - keep secure
- ⚠️ Deletion is permanent - no undo
- ⚠️ Full account access - don't share session files

## Build Process

### PyInstaller Configuration

```python
# build.py
pyinstaller --onefile \
    --add-data "src:src" \
    --add-data "data:data" \
    --add-data "templates:templates" \
    --hidden-import telethon.sync \
    --hidden-import telethon.tl.types \
    --exclude-module matplotlib \
    --exclude-module numpy \
    ...
```

### Output
- Windows: `dist/TelegramChatManager.exe` (~20MB)
- Mac/Linux: `dist/TelegramChatManager` (~15MB)

### Distribution
- Single file executable
- No Python installation needed
- Portable (runs from USB)

## Testing Strategy

### Manual Testing Checklist
1. Setup flow (enter credentials)
2. Connection (receive code)
3. Authorization (enter code)
4. Load chats (view statistics)
5. Filter chats (groups/channels/users)
6. Export (download JSON)
7. Delete (remove chat)
8. Analyze spam (run analysis)

### Edge Cases
- Invalid API credentials
- Wrong verification code
- 2FA enabled accounts
- Large chat lists (>1000)
- Network interruptions
- Deleted session files

## Future Improvements

### Technical Debt
### Technical Debt
- [x] Remove Flask version (Done: v2.0 is FastAPI only)
- [x] Add proper error handling middleware
- [x] Implement request logging
- [ ] Add unit tests
- [ ] Type hints throughout

### Features
- [ ] Bulk delete from JSON file
- [ ] Search/filter by name
- [ ] Pagination for large chat lists
- [ ] Dark mode toggle
- [ ] Multi-language support
- [ ] Docker container

### Performance
- [ ] Cache chat lists
- [ ] Lazy loading for large lists
- [ ] Progress bars for long operations
- [ ] Background task queue

## Common Issues & Solutions

### "No event loop in thread"
**Cause:** Legacy Flask threading + asyncio conflict
**Fix:** Removed Flask. Now using native FastAPI (ASGI) implementation.

### TemplateNotFound
**Cause:** templates/index.html deleted
**Fix:** Auto-regenerates on startup, or restart app

### "Cannot connect to Telegram"
**Cause:** Network, firewall, or wrong credentials
**Fix:** Check internet, verify API credentials, check phone format

### Session Expired
**Cause:** Session file outdated or deleted
**Fix:** Delete .session file, re-authenticate

## Development Guidelines

### Adding New Features
1. Update `fastapi_manager.py` for web features
2. Add endpoint with proper error handling (use custom exceptions)
3. Update frontend HTML template if needed
4. Test web and CLI modes
5. Update README.md and TECH.md

### Code Style
- Use async/await for new code
- Add type hints where possible
- Handle exceptions gracefully
- Log errors for debugging
- Keep functions focused and small

### Git Workflow
- `data/output/` is gitignored (user data)
- `templates/` is auto-generated (don't commit)
- `build/` and `dist/` are gitignored
- Test before committing

## Resources

### Documentation
- Telethon: https://docs.telethon.dev/
- FastAPI: https://fastapi.tiangolo.com/
- Flask: https://flask.palletsprojects.com/

### Telegram API
- Get API credentials: https://my.telegram.org/apps
- MTProto docs: https://core.telegram.org/mtproto

### Build Tools
- PyInstaller: https://pyinstaller.org/

---

**For LLM Agents:**
This document provides full context. When modifying code:
1. Use async/await for all Telegram operations
2. Use custom exception classes (TelegramError, NotConnectedError)
3. Update embedded HTML template for UI changes
4. Test data flow end-to-end
5. Keep security considerations in mind
