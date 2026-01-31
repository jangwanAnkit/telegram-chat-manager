from flask import Flask, render_template, request, jsonify, send_file
from telethon.sync import TelegramClient
from telethon.tl.types import Channel, Chat, User
from telethon.errors import SessionPasswordNeededError
import threading
import json
import os
from datetime import datetime

app = Flask(__name__)

# Global state
client = None
config = None
all_chats_cache = None
categorized_cache = None
analysis_cache = None

CONFIG_FILE = "telegram_config.json"


def load_config():
    """Load configuration from file"""
    global config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    return config


def save_config(api_id, api_hash, phone):
    """Save configuration to file"""
    config_data = {"api_id": api_id, "api_hash": api_hash, "phone": phone}
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=2)
    return config_data


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/setup", methods=["POST"])
def setup():
    """Initial setup - save credentials"""
    global config
    data = request.json
    config = save_config(data["api_id"], data["api_hash"], data["phone"])
    return jsonify({"success": True})


@app.route("/api/connect", methods=["POST"])
def connect():
    """Connect to Telegram"""
    global client, config

    if not config:
        load_config()

    if not config:
        return jsonify({"error": "Not configured. Run setup first."}), 400

    try:
        client = TelegramClient(config["phone"], config["api_id"], config["api_hash"])
        client.connect()

        if client.is_user_authorized():
            return jsonify({"status": "connected", "needs_code": False})
        else:
            client.send_code_request(config["phone"])
            return jsonify({"status": "waiting_code", "needs_code": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/verify", methods=["POST"])
def verify():
    """Verify with code and optional 2FA password"""
    global client

    data = request.json
    code = data.get("code")
    password = data.get("password")

    try:
        if password:
            client.sign_in(password=password)
        else:
            client.sign_in(config["phone"], code)
        return jsonify({"status": "connected"})
    except SessionPasswordNeededError:
        return jsonify({"status": "needs_password"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/chats")
def get_chats():
    """Get all chats"""
    global all_chats_cache, categorized_cache

    if not client or not client.is_connected():
        return jsonify({"error": "Not connected"}), 400

    try:
        chats = []
        stats = {"groups": 0, "channels": 0, "users": 0, "total": 0}

        for dialog in client.iter_dialogs():
            chat = dialog.entity
            chat_data = {"id": chat.id}

            if isinstance(chat, User):
                stats["users"] += 1
                chat_data["type"] = "user"
                chat_data["title"] = (
                    f"{chat.first_name or ''} {chat.last_name or ''}".strip()
                )
                chat_data["username"] = chat.username
                chat_data["is_deleted"] = chat.deleted
                chat_data["is_bot"] = getattr(chat, "bot", False)
                chat_data["is_scam"] = getattr(chat, "scam", False)
            elif isinstance(chat, Channel):
                if chat.broadcast:
                    stats["channels"] += 1
                    chat_data["type"] = "channel"
                else:
                    stats["groups"] += 1
                    chat_data["type"] = "supergroup"
                chat_data["title"] = chat.title
                chat_data["username"] = chat.username
                chat_data["members"] = getattr(chat, "participants_count", 0)
            elif isinstance(chat, Chat):
                stats["groups"] += 1
                chat_data["type"] = "group"
                chat_data["title"] = chat.title
                chat_data["members"] = getattr(chat, "participants_count", 0)
            else:
                chat_data["type"] = "unknown"
                chat_data["title"] = getattr(chat, "title", "Unknown")

            stats["total"] += 1
            chats.append(chat_data)

        all_chats_cache = chats
        categorized_cache = {
            "groups": [c for c in chats if c["type"] in ["group", "supergroup"]],
            "channels": [c for c in chats if c["type"] == "channel"],
            "users": [c for c in chats if c["type"] == "user"],
        }

        return jsonify({"chats": chats, "stats": stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/analyze")
def analyze():
    """Analyze users for spam"""
    global analysis_cache

    if not client or not client.is_connected():
        return jsonify({"error": "Not connected"}), 400

    try:
        analysis = {
            "deleted": [],
            "no_messages": [],
            "only_incoming": [],
            "bots": [],
            "scam": [],
            "fake": [],
            "active": [],
        }

        users = (
            [c for c in all_chats_cache if c["type"] == "user"]
            if all_chats_cache
            else []
        )

        if not users:
            # Fetch users from Telegram
            for dialog in client.iter_dialogs():
                if isinstance(dialog.entity, User):
                    users.append(dialog.entity)

        for i, user in enumerate(users):
            if isinstance(user, dict):
                # Already in cache format, fetch the actual entity
                continue

            if user.deleted:
                analysis["deleted"].append(
                    {
                        "id": user.id,
                        "title": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    }
                )
            elif getattr(user, "bot", False):
                analysis["bots"].append({"id": user.id, "title": user.first_name})
            elif getattr(user, "scam", False):
                analysis["scam"].append(
                    {
                        "id": user.id,
                        "title": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    }
                )
            elif getattr(user, "fake", False):
                analysis["fake"].append(
                    {
                        "id": user.id,
                        "title": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    }
                )
            else:
                # Check messages
                try:
                    messages = list(client.get_messages(user, limit=1))
                    if len(messages) == 0:
                        analysis["no_messages"].append(
                            {
                                "id": user.id,
                                "title": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                            }
                        )
                    else:
                        analysis["active"].append(
                            {
                                "id": user.id,
                                "title": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                            }
                        )
                except:
                    analysis["no_messages"].append(
                        {
                            "id": user.id,
                            "title": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                        }
                    )

        analysis_cache = analysis
        return jsonify(
            {
                "counts": {
                    "deleted": len(analysis["deleted"]),
                    "no_messages": len(analysis["no_messages"]),
                    "bots": len(analysis["bots"]),
                    "scam": len(analysis["scam"]),
                    "fake": len(analysis["fake"]),
                    "active": len(analysis["active"]),
                },
                "users": analysis,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/delete/<int:chat_id>", methods=["POST"])
def delete_chat(chat_id):
    """Delete a specific chat"""
    if not client or not client.is_connected():
        return jsonify({"error": "Not connected"}), 400

    try:
        entity = client.get_entity(chat_id)
        client.delete_dialog(entity)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/export/<type>")
def export(type):
    """Export chats to JSON"""
    if not client or not client.is_connected():
        return jsonify({"error": "Not connected"}), 400

    try:
        items = []

        for dialog in client.iter_dialogs():
            chat = dialog.entity

            if (
                type == "groups"
                and isinstance(chat, (Chat, Channel))
                and not getattr(chat, "broadcast", False)
            ):
                items.append(
                    {
                        "id": chat.id,
                        "title": chat.title,
                        "username": getattr(chat, "username", None),
                        "members": getattr(chat, "participants_count", 0),
                    }
                )
            elif type == "channels" and isinstance(chat, Channel) and chat.broadcast:
                items.append(
                    {
                        "id": chat.id,
                        "title": chat.title,
                        "username": getattr(chat, "username", None),
                        "members": getattr(chat, "participants_count", 0),
                    }
                )
            elif type == "users" and isinstance(chat, User):
                items.append(
                    {
                        "id": chat.id,
                        "first_name": chat.first_name,
                        "last_name": getattr(chat, "last_name", ""),
                        "username": chat.username,
                        "is_deleted": chat.deleted,
                        "is_bot": getattr(chat, "bot", False),
                        "is_scam": getattr(chat, "scam", False),
                        "is_fake": getattr(chat, "fake", False),
                    }
                )

        filename = f"{type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        return send_file(filename, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    print("=" * 80)
    print("TELEGRAM CHAT MANAGER - Web UI")
    print("=" * 80)
    print("\nOpen your browser and go to: http://localhost:5000")
    print("\n[WARN]  This runs ONLY on your local machine!")
    print("Your credentials never leave your computer.\n")

    # Create templates directory and HTML file
    os.makedirs("templates", exist_ok=True)

    with open("templates/index.html", "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Telegram Chat Manager</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        .header { background: #0088cc; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-card h3 { margin: 0 0 5px 0; color: #666; font-size: 14px; }
        .stat-card p { margin: 0; font-size: 24px; font-weight: bold; color: #0088cc; }
        button { padding: 10px 20px; margin: 5px; cursor: pointer; background: #0088cc; color: white; border: none; border-radius: 4px; font-size: 14px; }
        button:hover { background: #006699; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        button.secondary { background: #6c757d; }
        button.secondary:hover { background: #5a6268; }
        button.danger { background: #dc3545; }
        button.danger:hover { background: #c82333; }
        .chat-list { max-height: 500px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin: 10px 0; background: white; }
        .chat-item { padding: 12px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
        .chat-item:last-child { border-bottom: none; }
        .chat-info { flex: 1; }
        .chat-title { font-weight: bold; margin-bottom: 4px; }
        .chat-meta { font-size: 12px; color: #666; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 5px; }
        .badge-danger { background: #ffcdd2; color: #c62828; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .badge-info { background: #d1ecf1; color: #0c5460; }
        input, textarea { width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }
        .hidden { display: none; }
        .status { padding: 10px; border-radius: 4px; margin: 10px 0; }
        .status-success { background: #d4edda; color: #155724; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-info { background: #d1ecf1; color: #0c5460; }
        .setup-form { max-width: 500px; }
        .progress-bar { width: 100%; height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; background: #0088cc; transition: width 0.3s; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📱 Telegram Chat Manager</h1>
        <p>Manage your Telegram chats locally - your data stays on your computer</p>
    </div>

    <!-- Setup Section -->
    <div id="setup-section" class="card">
        <h2>🔧 First Time Setup</h2>
        <p>You need API credentials from Telegram. <a href="https://my.telegram.org/apps" target="_blank">Get them here</a></p>
        <div class="setup-form">
            <input type="text" id="api-id" placeholder="API ID (numbers only)" />
            <input type="text" id="api-hash" placeholder="API Hash" />
            <input type="text" id="phone" placeholder="Phone number (e.g., +1234567890)" />
            <button onclick="saveSetup()">Save Configuration</button>
        </div>
        <div id="setup-status"></div>
    </div>

    <!-- Connection Section -->
    <div id="connect-section" class="card hidden">
        <h2>🔌 Connect to Telegram</h2>
        <button onclick="connect()" id="connect-btn">Connect</button>
        <div id="code-section" class="hidden">
            <p>Enter the code sent to your Telegram:</p>
            <input type="text" id="code" placeholder="12345" />
            <button onclick="verifyCode()">Verify</button>
        </div>
        <div id="password-section" class="hidden">
            <p>Two-factor authentication enabled. Enter your password:</p>
            <input type="password" id="password" placeholder="Your 2FA password" />
            <button onclick="verifyPassword()">Verify</button>
        </div>
        <div id="connect-status"></div>
    </div>

    <!-- Main Interface -->
    <div id="main-section" class="card hidden">
        <h2>📊 Chat Statistics</h2>
        <div class="stats" id="stats">
            <div class="stat-card">
                <h3>Total Chats</h3>
                <p id="stat-total">-</p>
            </div>
            <div class="stat-card">
                <h3>Groups</h3>
                <p id="stat-groups">-</p>
            </div>
            <div class="stat-card">
                <h3>Channels</h3>
                <p id="stat-channels">-</p>
            </div>
            <div class="stat-card">
                <h3>Users</h3>
                <p id="stat-users">-</p>
            </div>
        </div>

        <h3>🎯 Quick Actions</h3>
        <button onclick="loadChats()">🔄 Refresh Chats</button>
        <button onclick="showGroups()" class="secondary">👥 Show Groups</button>
        <button onclick="showChannels()" class="secondary">📢 Show Channels</button>
        <button onclick="showUsers()" class="secondary">👤 Show Users</button>
        <button onclick="analyzeSpam()" class="danger">🚫 Analyze Spam</button>
        
        <h3>📥 Export</h3>
        <button onclick="exportData('groups')" class="secondary">Export Groups</button>
        <button onclick="exportData('channels')" class="secondary">Export Channels</button>
        <button onclick="exportData('users')" class="secondary">Export Users</button>

        <h3>📋 Chat List</h3>
        <div id="chats" class="chat-list">
            <p style="text-align: center; color: #666;">Click "Refresh Chats" to load your chats</p>
        </div>

        <div id="analysis-results" class="hidden">
            <h3>🔍 Analysis Results</h3>
            <div id="analysis-content"></div>
        </div>
    </div>

    <script>
        let currentChats = [];
        let isConnected = false;

        // Check if already configured
        async function checkConfig() {
            try {
                const response = await fetch('/api/chats');
                if (response.ok) {
                    showMain();
                    loadChats();
                }
            } catch (e) {
                // Not configured yet
            }
        }

        async function saveSetup() {
            const apiId = document.getElementById('api-id').value;
            const apiHash = document.getElementById('api-hash').value;
            const phone = document.getElementById('phone').value;

            const response = await fetch('/api/setup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_id: apiId, api_hash: apiHash, phone: phone })
            });

            if (response.ok) {
                document.getElementById('setup-section').classList.add('hidden');
                document.getElementById('connect-section').classList.remove('hidden');
                showStatus('setup-status', 'Configuration saved!', 'success');
            } else {
                showStatus('setup-status', 'Error saving configuration', 'error');
            }
        }

        async function connect() {
            document.getElementById('connect-btn').disabled = true;
            const response = await fetch('/api/connect', { method: 'POST' });
            const data = await response.json();

            if (data.error) {
                showStatus('connect-status', data.error, 'error');
                document.getElementById('connect-btn').disabled = false;
            } else if (data.needs_code) {
                document.getElementById('code-section').classList.remove('hidden');
                showStatus('connect-status', 'Code sent to your Telegram app', 'info');
            } else if (data.status === 'connected') {
                showMain();
            }
        }

        async function verifyCode() {
            const code = document.getElementById('code').value;
            const response = await fetch('/api/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: code })
            });
            const data = await response.json();

            if (data.status === 'needs_password') {
                document.getElementById('code-section').classList.add('hidden');
                document.getElementById('password-section').classList.remove('hidden');
                showStatus('connect-status', 'Two-factor authentication required', 'info');
            } else if (data.status === 'connected') {
                showMain();
            } else if (data.error) {
                showStatus('connect-status', data.error, 'error');
            }
        }

        async function verifyPassword() {
            const password = document.getElementById('password').value;
            const response = await fetch('/api/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: password })
            });
            const data = await response.json();

            if (data.status === 'connected') {
                showMain();
            } else if (data.error) {
                showStatus('connect-status', data.error, 'error');
            }
        }

        function showMain() {
            document.getElementById('setup-section').classList.add('hidden');
            document.getElementById('connect-section').classList.add('hidden');
            document.getElementById('main-section').classList.remove('hidden');
            isConnected = true;
        }

        async function loadChats() {
            const chatsDiv = document.getElementById('chats');
            chatsDiv.innerHTML = '<p style="text-align: center;">Loading...</p>';
            
            const response = await fetch('/api/chats');
            const data = await response.json();

            if (data.error) {
                chatsDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
                return;
            }

            currentChats = data.chats;
            displayChats(currentChats);
            updateStats(data.stats);
        }

        function updateStats(stats) {
            document.getElementById('stat-total').textContent = stats.total;
            document.getElementById('stat-groups').textContent = stats.groups;
            document.getElementById('stat-channels').textContent = stats.channels;
            document.getElementById('stat-users').textContent = stats.users;
        }

        function displayChats(chats) {
            const chatsDiv = document.getElementById('chats');
            if (chats.length === 0) {
                chatsDiv.innerHTML = '<p style="text-align: center; color: #666;">No chats found</p>';
                return;
            }

            chatsDiv.innerHTML = chats.map(chat => `
                <div class="chat-item">
                    <div class="chat-info">
                        <div class="chat-title">
                            ${chat.title}
                            ${chat.is_deleted ? '<span class="badge badge-danger">Deleted</span>' : ''}
                            ${chat.is_bot ? '<span class="badge badge-info">Bot</span>' : ''}
                            ${chat.is_scam ? '<span class="badge badge-danger">Scam</span>' : ''}
                        </div>
                        <div class="chat-meta">
                            ${chat.type} • ID: ${chat.id}
                            ${chat.username ? `• @${chat.username}` : ''}
                            ${chat.members ? `• ${chat.members} members` : ''}
                        </div>
                    </div>
                    <button class="danger" onclick="deleteChat(${chat.id})">Delete</button>
                </div>
            `).join('');
        }

        function showGroups() {
            const groups = currentChats.filter(c => c.type === 'group' || c.type === 'supergroup');
            displayChats(groups);
        }

        function showChannels() {
            const channels = currentChats.filter(c => c.type === 'channel');
            displayChats(channels);
        }

        function showUsers() {
            const users = currentChats.filter(c => c.type === 'user');
            displayChats(users);
        }

        async function deleteChat(id) {
            if (!confirm('Are you sure you want to delete this chat?')) return;
            
            const response = await fetch(`/api/delete/${id}`, { method: 'POST' });
            if (response.ok) {
                currentChats = currentChats.filter(c => c.id !== id);
                displayChats(currentChats);
            } else {
                const data = await response.json();
                alert('Error: ' + data.error);
            }
        }

        async function analyzeSpam() {
            const analysisDiv = document.getElementById('analysis-results');
            const contentDiv = document.getElementById('analysis-content');
            analysisDiv.classList.remove('hidden');
            contentDiv.innerHTML = '<p>Analyzing...</p>';
            
            const response = await fetch('/api/analyze');
            const data = await response.json();

            if (data.error) {
                contentDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
                return;
            }

            const counts = data.counts;
            contentDiv.innerHTML = `
                <div class="stats">
                    <div class="stat-card">
                        <h3>Deleted Users</h3>
                        <p style="color: #dc3545;">${counts.deleted}</p>
                    </div>
                    <div class="stat-card">
                        <h3>No Messages</h3>
                        <p style="color: #ffc107;">${counts.no_messages}</p>
                    </div>
                    <div class="stat-card">
                        <h3>Bots</h3>
                        <p style="color: #17a2b8;">${counts.bots}</p>
                    </div>
                    <div class="stat-card">
                        <h3>Scam Users</h3>
                        <p style="color: #dc3545;">${counts.scam}</p>
                    </div>
                    <div class="stat-card">
                        <h3>Fake Users</h3>
                        <p style="color: #dc3545;">${counts.fake}</p>
                    </div>
                    <div class="stat-card">
                        <h3>Active Chats</h3>
                        <p style="color: #28a745;">${counts.active}</p>
                    </div>
                </div>
                <h4>Suspicious Users (Click to view)</h4>
                <button onclick="showAnalysisCategory('deleted')" class="secondary">Deleted (${counts.deleted})</button>
                <button onclick="showAnalysisCategory('no_messages')" class="secondary">No Messages (${counts.no_messages})</button>
                <button onclick="showAnalysisCategory('scam')" class="danger">Scam (${counts.scam})</button>
                <button onclick="showAnalysisCategory('fake')" class="danger">Fake (${counts.fake})</button>
                <div id="analysis-users-list" class="chat-list" style="margin-top: 15px;"></div>
            `;

            window.analysisData = data.users;
        }

        function showAnalysisCategory(category) {
            const users = window.analysisData[category] || [];
            const listDiv = document.getElementById('analysis-users-list');
            
            if (users.length === 0) {
                listDiv.innerHTML = '<p>No users in this category</p>';
                return;
            }

            listDiv.innerHTML = users.map(u => `
                <div class="chat-item">
                    <div class="chat-info">
                        <div class="chat-title">${u.title}</div>
                        <div class="chat-meta">ID: ${u.id}</div>
                    </div>
                    <button class="danger" onclick="deleteChat(${u.id})">Delete</button>
                </div>
            `).join('');
        }

        function exportData(type) {
            window.open(`/api/export/${type}`, '_blank');
        }

        function showStatus(elementId, message, type) {
            const element = document.getElementById(elementId);
            element.className = `status status-${type}`;
            element.textContent = message;
        }

        // Initialize
        checkConfig();
    </script>
</body>
</html>""")

    app.run(host="127.0.0.1", port=5000, debug=False)
