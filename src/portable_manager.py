#!/usr/bin/env python3
"""
Telegram Chat Manager - ZERO CONFIG Portable Version
Just double-click and it works! Pre-configured with your API credentials.
"""

import sys
import os
import json
import webbrowser
import threading
import time
from datetime import datetime

# Flask imports
from flask import Flask, render_template, request, jsonify, send_file

# Telethon imports
from telethon.sync import TelegramClient
from telethon.tl.types import Channel, Chat, User
from telethon.errors import SessionPasswordNeededError

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - EDIT THESE VALUES BEFORE DISTRIBUTING
# ═══════════════════════════════════════════════════════════════════════════════
# Get these from https://my.telegram.org/apps
PRE_CONFIGURED_API_ID = "YOUR_API_ID_HERE"  # Replace with your API ID (numbers only)
PRE_CONFIGURED_API_HASH = "YOUR_API_HASH_HERE"  # Replace with your API Hash
# ═══════════════════════════════════════════════════════════════════════════════

# Determine base directory
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Determine template directory based on where we're running from
if os.path.basename(BASE_DIR) == "src":
    # Running from src/ directory, templates should be in parent (project root)
    TEMPLATE_DIR = os.path.join(os.path.dirname(BASE_DIR), "templates")
else:
    TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

CONFIG_FILE = os.path.join(BASE_DIR, "telegram_config.json")


# Create Flask app with correct template folder
app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Global state
client = None
config = None
all_chats_cache = None
is_connected = False


def load_or_create_config():
    """Load existing config or create from pre-configured values"""
    global config

    # First, check if user already has a config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                return config
        except:
            pass

    # Check if pre-configured values are set
    if (
        PRE_CONFIGURED_API_ID != "YOUR_API_ID_HERE"
        and PRE_CONFIGURED_API_HASH != "YOUR_API_HASH_HERE"
    ):
        # Use pre-configured values
        config = {
            "api_id": PRE_CONFIGURED_API_ID,
            "api_hash": PRE_CONFIGURED_API_HASH,
            "phone": None,  # Will be asked on first run
        }
        return config

    return None


def save_config(api_id, api_hash, phone):
    """Save configuration to file"""
    config_data = {"api_id": api_id, "api_hash": api_hash, "phone": phone}
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=2)
    return config_data


# HTML Template - Beautiful Modern UI
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Chat Manager</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header { 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 40px;
            border-radius: 20px;
            margin-bottom: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        
        .header h1 { 
            font-size: 42px; 
            margin-bottom: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .header p { 
            font-size: 18px; 
            color: #666;
            max-width: 600px;
            margin: 0 auto;
        }
        
        .card { 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        
        .card h2 { 
            color: #333; 
            margin-bottom: 20px; 
            font-size: 28px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .card h3 { 
            color: #555; 
            margin: 25px 0 15px 0; 
            font-size: 20px;
        }
        
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin: 30px 0; 
        }
        
        .stat-card { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            color: white;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .stat-card:hover { 
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(102, 126, 234, 0.5);
        }
        
        .stat-card h3 { 
            margin: 0 0 10px 0; 
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            opacity: 0.9;
            color: white;
        }
        
        .stat-card p { 
            margin: 0; 
            font-size: 42px; 
            font-weight: bold;
        }
        
        button { 
            padding: 14px 28px;
            margin: 8px;
            cursor: pointer;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 600;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        
        button:hover { 
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
        }
        
        button:active { 
            transform: translateY(0);
        }
        
        button:disabled { 
            background: #ccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        button.secondary { 
            background: #6c757d;
        }
        
        button.secondary:hover { 
            background: #5a6268;
            box-shadow: 0 8px 25px rgba(108, 117, 125, 0.5);
        }
        
        button.danger { 
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
        }
        
        button.danger:hover { 
            box-shadow: 0 8px 25px rgba(255, 107, 107, 0.5);
        }
        
        button.small {
            padding: 8px 16px;
            font-size: 13px;
        }
        
        .chat-list { 
            max-height: 600px;
            overflow-y: auto;
            border-radius: 15px;
            background: #f8f9fa;
            padding: 20px;
            margin: 20px 0;
        }
        
        .chat-item { 
            padding: 20px;
            background: white;
            border-radius: 12px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            transition: all 0.3s;
        }
        
        .chat-item:hover { 
            transform: translateX(5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        
        .chat-item:last-child { 
            margin-bottom: 0;
        }
        
        .chat-info { 
            flex: 1;
        }
        
        .chat-title { 
            font-weight: 700;
            font-size: 17px;
            margin-bottom: 6px;
            color: #333;
        }
        
        .chat-meta { 
            font-size: 14px;
            color: #666;
        }
        
        .badge { 
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            margin-left: 8px;
            font-weight: 600;
        }
        
        .badge-danger { 
            background: #fee2e2;
            color: #dc2626;
        }
        
        .badge-warning { 
            background: #fef3c7;
            color: #d97706;
        }
        
        .badge-info { 
            background: #dbeafe;
            color: #2563eb;
        }
        
        .badge-success {
            background: #d1fae5;
            color: #059669;
        }
        
        input { 
            width: 100%;
            padding: 15px;
            margin: 10px 0;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .hidden { 
            display: none !important;
        }
        
        .status { 
            padding: 15px 20px;
            border-radius: 10px;
            margin: 20px 0;
            font-weight: 500;
        }
        
        .status-success { 
            background: #d1fae5;
            color: #065f46;
            border: 1px solid #a7f3d0;
        }
        
        .status-error { 
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }
        
        .status-info { 
            background: #dbeafe;
            color: #1e40af;
            border: 1px solid #bfdbfe;
        }
        
        .help-text {
            color: #6b7280;
            font-size: 15px;
            margin: 15px 0;
            line-height: 1.6;
        }
        
        .help-text a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        
        .help-text a:hover {
            text-decoration: underline;
        }
        
        .setup-form { 
            max-width: 500px;
            margin: 0 auto;
        }
        
        .progress-bar { 
            width: 100%;
            height: 10px;
            background: #e5e7eb;
            border-radius: 5px;
            overflow: hidden;
            margin: 20px 0;
        }
        
        .progress-fill { 
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
            border-radius: 5px;
        }
        
        .filter-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 20px 0;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #9ca3af;
        }
        
        .empty-state p {
            font-size: 18px;
        }
        
        .tabs {
            display: flex;
            border-bottom: 2px solid #e5e7eb;
            margin-bottom: 30px;
            gap: 10px;
        }
        
        .tab {
            padding: 15px 25px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            font-weight: 600;
            color: #6b7280;
            transition: all 0.3s;
            border-radius: 8px 8px 0 0;
        }
        
        .tab:hover {
            color: #667eea;
            background: #f3f4f6;
        }
        
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
            background: #f3f4f6;
        }
        
        .footer {
            text-align: center;
            padding: 30px;
            color: rgba(255,255,255,0.8);
            font-size: 14px;
        }
        
        .footer a {
            color: white;
            text-decoration: underline;
        }
        
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        
        .feature-card {
            background: #f9fafb;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
        }
        
        .feature-card h4 {
            color: #333;
            margin-bottom: 10px;
            font-size: 18px;
        }
        
        .feature-card p {
            color: #6b7280;
            font-size: 14px;
        }
        
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* ====================
           RESPONSIVE STYLES
           ==================== */

        /* Large tablets and small laptops (1024px and below) */
        @media (max-width: 1024px) {
            .container {
                max-width: 100%;
            }
            .stats {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        /* Tablets (768px and below) */
        @media (max-width: 768px) {
            body {
                padding: 15px;
            }
            .header {
                padding: 30px 20px;
            }
            .header h1 {
                font-size: 32px;
            }
            .card {
                padding: 20px;
            }
            .stats {
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
            }
            .stat-card p {
                font-size: 32px;
            }
            .chat-item {
                padding: 15px;
            }
            .tab {
                padding: 12px 18px;
                font-size: 15px;
            }
        }

        /* Large phones (640px and below) */
        @media (max-width: 640px) {
            .header h1 {
                font-size: 28px;
            }
            .header p {
                font-size: 15px;
            }
            .stats {
                grid-template-columns: 1fr 1fr;
            }
            .stat-card {
                padding: 20px 15px;
            }
            .chat-item {
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
            }
            .chat-item button {
                align-self: stretch;
                width: 100%;
            }
        }

        /* Small phones (480px and below) */
        @media (max-width: 480px) {
            body {
                padding: 10px;
            }
            .header {
                padding: 25px 15px;
                border-radius: 15px;
            }
            .header h1 {
                font-size: 24px;
            }
            .header p {
                font-size: 14px;
            }
            .card {
                padding: 15px;
                border-radius: 15px;
            }
            .card h2 {
                font-size: 22px;
            }
            .stats {
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }
            .stat-card {
                padding: 15px 10px;
            }
            .stat-card h3 {
                font-size: 11px;
            }
            .stat-card p {
                font-size: 24px;
            }
            button {
                padding: 12px 20px;
                font-size: 14px;
                margin: 4px;
            }
            button.small {
                padding: 8px 12px;
                font-size: 12px;
            }
            .filter-buttons {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
            }
            .filter-buttons button {
                flex: 1 1 calc(50% - 6px);
                min-width: 130px;
                margin: 0;
            }
            .chat-list {
                max-height: 400px;
                border-radius: 10px;
                padding: 10px;
            }
            .chat-item {
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 8px;
            }
            .chat-title {
                font-size: 15px;
            }
            .chat-meta {
                font-size: 12px;
            }
            input, textarea {
                padding: 12px;
                font-size: 16px;
                border-radius: 8px;
            }
            .tab {
                padding: 10px 14px;
                font-size: 14px;
            }
            .tabs {
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }
            .footer {
                font-size: 12px;
                padding: 20px 10px;
            }
            .empty-state {
                padding: 40px 15px;
            }
            .feature-grid {
                grid-template-columns: 1fr;
                gap: 15px;
            }
        }

        /* Very small phones (360px and below) */
        @media (max-width: 360px) {
            .header h1 {
                font-size: 20px;
            }
            .stats {
                grid-template-columns: 1fr;
                gap: 8px;
            }
            .stat-card {
                padding: 12px 10px;
            }
            .stat-card p {
                font-size: 20px;
            }
            button {
                padding: 10px 16px;
                font-size: 13px;
            }
            .filter-buttons button {
                flex: 1 1 100%;
            }
        }

        /* Landscape orientation on mobile */
        @media (max-height: 500px) and (orientation: landscape) {
            .header {
                padding: 20px;
            }
            .stats {
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
            }
            .chat-list {
                max-height: 200px;
            }
        }

        /* Touch device optimizations */
        @media (hover: none) and (pointer: coarse) {
            button {
                min-height: 44px;
            }
            button.small {
                min-height: 36px;
            }
            .chat-item {
                padding: 15px;
            }
            .tab {
                padding: 12px 16px;
            }
            input, textarea, select {
                min-height: 44px;
            }
        }

        /* Print styles */
        @media print {
            body {
                background: white;
            }
            .header {
                background: #667eea;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            button, .footer, .tabs {
                display: none;
            }
            .card {
                break-inside: avoid;
                box-shadow: none;
                border: 1px solid #ddd;
                background: white;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 Telegram Chat Manager</h1>
            <p>Clean up your Telegram account - Delete unwanted chats, groups, and channels with ease</p>
        </div>

        <!-- Setup Section -->
        <div id="setup-section" class="card">
            <h2>🔧 Welcome! Let's Get Started</h2>
            
            <div class="tabs">
                <div class="tab active" onclick="showTab('setup')">Quick Setup</div>
                <div class="tab" onclick="showTab('help')">Need Help?</div>
            </div>
            
            <div id="setup-tab">
                <div class="setup-form">
                    <div id="api-config-section">
                        <label style="font-weight: 600; color: #333; display: block; margin-bottom: 8px;">Your Phone Number</label>
                        <input type="text" id="phone" placeholder="e.g., +1234567890" />
                        <div class="help-text" style="font-size: 13px; color: #9ca3af;">
                            Include your country code (e.g., +1 for US, +44 for UK, +91 for India)
                        </div>
                    </div>
                    
                    <button onclick="saveSetup()" style="width: 100%; margin-top: 20px; padding: 18px;">
                        🚀 Start Managing My Chats
                    </button>
                </div>
            </div>
            
            <div id="help-tab" class="hidden">
                <div class="help-text" style="max-width: 700px; margin: 0 auto;">
                    <h3 style="margin-bottom: 15px; color: #333;">How does this work?</h3>
                    <p style="margin-bottom: 20px;">
                        This application runs entirely on your computer. Your data never leaves your device.
                        We connect directly to Telegram's API to help you manage your chats.
                    </p>
                    
                    <h3 style="margin-bottom: 15px; color: #333;">What do I need?</h3>
                    <ul style="margin-left: 20px; line-height: 2; color: #4b5563;">
                        <li>Your phone number with country code</li>
                        <li>A code that Telegram will send you (for verification)</li>
                        <li>That's it! No API credentials needed for this version.</li>
                    </ul>
                    
                    <div style="background: #fef3c7; padding: 20px; border-radius: 10px; margin-top: 25px;">
                        <strong style="color: #92400e;">⚠️ Important Security Note:</strong>
                        <p style="margin-top: 10px; color: #92400e;">
                            This app creates a session file to stay logged in. Keep this file secure and don't share it with anyone.
                            It's saved in the same folder as this application.
                        </p>
                    </div>
                </div>
            </div>
            
            <div id="setup-status"></div>
        </div>

        <!-- Connection Section -->
        <div id="connect-section" class="card hidden">
            <h2>🔌 Connect to Telegram</h2>
            <div class="help-text">
                Click "Connect" to start. You'll receive a code on your Telegram app within seconds.
            </div>
            <button onclick="connect()" id="connect-btn" style="padding: 18px 40px; font-size: 18px;">
                📡 Connect to Telegram
            </button>
            
            <div id="code-section" class="hidden" style="margin-top: 30px; padding: 30px; background: #f9fafb; border-radius: 15px;">
                <label style="font-weight: 600; display: block; margin-bottom: 10px; font-size: 16px;">
                    Enter the code sent to your Telegram:
                </label>
                <div style="display: flex; gap: 15px; align-items: center;">
                    <input type="text" id="code" placeholder="12345" style="max-width: 200px; text-align: center; font-size: 20px; letter-spacing: 5px;" />
                    <button onclick="verifyCode()">✓ Verify Code</button>
                </div>
            </div>
            
            <div id="password-section" class="hidden" style="margin-top: 30px; padding: 30px; background: #fef3c7; border-radius: 15px;">
                <label style="font-weight: 600; display: block; margin-bottom: 10px; color: #92400e;">
                    🔐 Two-factor authentication enabled
                </label>
                <p style="margin-bottom: 15px; color: #92400e;">Enter your 2FA password:</p>
                <div style="display: flex; gap: 15px;">
                    <input type="password" id="password" placeholder="Your 2FA password" style="max-width: 300px;" />
                    <button onclick="verifyPassword()">✓ Verify</button>
                </div>
            </div>
            
            <div id="connect-status"></div>
        </div>

        <!-- Main Interface -->
        <div id="main-section" class="card hidden">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; flex-wrap: wrap; gap: 15px;">
                <h2 style="margin: 0;">📊 Your Chat Statistics</h2>
                <button onclick="loadChats()" class="secondary" style="margin: 0;">
                    🔄 Refresh Data
                </button>
            </div>
            
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
                    <h3>Private Chats</h3>
                    <p id="stat-users">-</p>
                </div>
            </div>

            <h3>🎯 Quick Actions</h3>
            <div class="filter-buttons">
                <button onclick="showGroups()">👥 Groups</button>
                <button onclick="showChannels()">📢 Channels</button>
                <button onclick="showUsers()">👤 Users</button>
                <button onclick="showAll()" class="secondary">📋 Show All</button>
                <button onclick="analyzeSpam()" class="danger">🚫 Find Spam</button>
            </div>
            
            <h3>📥 Export Your Data</h3>
            <div class="help-text">
                Download your chat list as a backup or for bulk editing in JSON format
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 10px;">
                <button onclick="exportData('groups')" class="secondary small">Export Groups</button>
                <button onclick="exportData('channels')" class="secondary small">Export Channels</button>
                <button onclick="exportData('users')" class="secondary small">Export Users</button>
            </div>

            <h3>📋 Your Chats <span id="chat-count" style="font-weight: normal; color: #9ca3af; font-size: 16px;"></span></h3>
            <div id="chats" class="chat-list">
                <div class="empty-state">
                    <p style="font-size: 48px; margin-bottom: 15px;">📱</p>
                    <p>Click "Refresh Data" above to load your chats</p>
                </div>
            </div>

            <div id="analysis-results" class="hidden">
                <h3>🔍 Spam Analysis Results</h3>
                <div id="analysis-content"></div>
            </div>
        </div>

        <div class="footer">
            <p>🔒 100% Private & Secure • Your data never leaves your computer • <a href="https://my.telegram.org/apps" target="_blank">About Telegram API</a></p>
        </div>
    </div>

    <script>
        let currentChats = [];
        let isConnected = false;
        let currentFilter = 'all';

        function showTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
            if (tab === 'setup') {
                document.getElementById('setup-tab').classList.remove('hidden');
                document.getElementById('help-tab').classList.add('hidden');
            } else {
                document.getElementById('setup-tab').classList.add('hidden');
                document.getElementById('help-tab').classList.remove('hidden');
            }
        }

        async function saveSetup() {
            const phone = document.getElementById('phone').value.trim();

            if (!phone) {
                showStatus('setup-status', 'Please enter your phone number', 'error');
                return;
            }

            if (!phone.match(/^\+[1-9]\d{1,14}$/)) {
                showStatus('setup-status', 'Please enter a valid phone number with country code (e.g., +1234567890)', 'error');
                return;
            }

            showStatus('setup-status', 'Saving...', 'info');
            
            try {
                const response = await fetch('/api/setup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone: phone })
                });

                if (response.ok) {
                    document.getElementById('setup-section').classList.add('hidden');
                    document.getElementById('connect-section').classList.remove('hidden');
                    showStatus('connect-status', '✓ Setup complete! Click "Connect to Telegram" to continue.', 'success');
                } else {
                    const data = await response.json();
                    showStatus('setup-status', '❌ ' + (data.error || 'Error saving configuration'), 'error');
                }
            } catch (e) {
                showStatus('setup-status', '❌ Network error. Please try again.', 'error');
            }
        }

        async function connect() {
            document.getElementById('connect-btn').disabled = true;
            document.getElementById('connect-btn').innerHTML = 'Connecting<span class="loading-spinner"></span>';
            
            try {
                const response = await fetch('/api/connect', { method: 'POST' });
                const data = await response.json();

                if (data.error) {
                    showStatus('connect-status', '❌ ' + data.error, 'error');
                    document.getElementById('connect-btn').disabled = false;
                    document.getElementById('connect-btn').textContent = '📡 Connect to Telegram';
                } else if (data.needs_code) {
                    document.getElementById('code-section').classList.remove('hidden');
                    showStatus('connect-status', '✓ Code sent! Check your Telegram app.', 'success');
                    document.getElementById('code').focus();
                } else if (data.status === 'connected') {
                    showMain();
                }
            } catch (e) {
                showStatus('connect-status', '❌ Connection error. Please try again.', 'error');
                document.getElementById('connect-btn').disabled = false;
                document.getElementById('connect-btn').textContent = '📡 Connect to Telegram';
            }
        }

        async function verifyCode() {
            const code = document.getElementById('code').value.trim();
            if (!code) {
                showStatus('connect-status', 'Please enter the code', 'error');
                return;
            }

            try {
                const response = await fetch('/api/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: code })
                });
                const data = await response.json();

                if (data.status === 'needs_password') {
                    document.getElementById('code-section').classList.add('hidden');
                    document.getElementById('password-section').classList.remove('hidden');
                    showStatus('connect-status', '🔐 Two-factor authentication required', 'info');
                    document.getElementById('password').focus();
                } else if (data.status === 'connected') {
                    showMain();
                } else if (data.error) {
                    showStatus('connect-status', '❌ ' + data.error, 'error');
                }
            } catch (e) {
                showStatus('connect-status', '❌ Verification error', 'error');
            }
        }

        async function verifyPassword() {
            const password = document.getElementById('password').value;
            if (!password) {
                showStatus('connect-status', 'Please enter your password', 'error');
                return;
            }

            try {
                const response = await fetch('/api/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: password })
                });
                const data = await response.json();

                if (data.status === 'connected') {
                    showMain();
                } else if (data.error) {
                    showStatus('connect-status', '❌ ' + data.error, 'error');
                }
            } catch (e) {
                showStatus('connect-status', '❌ Verification error', 'error');
            }
        }

        function showMain() {
            document.getElementById('setup-section').classList.add('hidden');
            document.getElementById('connect-section').classList.add('hidden');
            document.getElementById('main-section').classList.remove('hidden');
            isConnected = true;
            loadChats();
        }

        async function loadChats() {
            const chatsDiv = document.getElementById('chats');
            chatsDiv.innerHTML = '<div class="empty-state"><div class="loading-spinner" style="width: 40px; height: 40px; margin-bottom: 20px;"></div><p>Loading your chats...</p></div>';
            
            try {
                const response = await fetch('/api/chats');
                const data = await response.json();

                if (data.error) {
                    chatsDiv.innerHTML = `<div class="empty-state"><p style="color: #dc2626;">❌ Error: ${data.error}</p></div>`;
                    return;
                }

                currentChats = data.chats;
                updateStats(data.stats);
                showAll();
            } catch (e) {
                chatsDiv.innerHTML = `<div class="empty-state"><p style="color: #dc2626;">❌ Network error. Please try again.</p></div>`;
            }
        }

        function updateStats(stats) {
            animateNumber('stat-total', stats.total);
            animateNumber('stat-groups', stats.groups);
            animateNumber('stat-channels', stats.channels);
            animateNumber('stat-users', stats.users);
        }

        function animateNumber(elementId, target) {
            const element = document.getElementById(elementId);
            const duration = 1000;
            const start = 0;
            const startTime = performance.now();
            
            function update(currentTime) {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const easeOutQuart = 1 - Math.pow(1 - progress, 4);
                const current = Math.floor(start + (target - start) * easeOutQuart);
                element.textContent = current.toLocaleString();
                
                if (progress < 1) {
                    requestAnimationFrame(update);
                }
            }
            
            requestAnimationFrame(update);
        }

        function displayChats(chats) {
            const chatsDiv = document.getElementById('chats');
            document.getElementById('chat-count').textContent = chats.length > 0 ? `(${chats.length.toLocaleString()} shown)` : '';
            
            if (chats.length === 0) {
                chatsDiv.innerHTML = '<div class="empty-state"><p>No chats in this category</p></div>';
                return;
            }

            chatsDiv.innerHTML = chats.map(chat => {
                let badges = '';
                if (chat.is_deleted) badges += '<span class="badge badge-danger">Deleted</span>';
                if (chat.is_bot) badges += '<span class="badge badge-info">Bot</span>';
                if (chat.is_scam) badges += '<span class="badge badge-danger">Scam</span>';
                if (chat.is_fake) badges += '<span class="badge badge-danger">Fake</span>';
                if (chat.is_verified) badges += '<span class="badge badge-success">Verified</span>';
                
                let typeIcon = '';
                let typeLabel = '';
                if (chat.type === 'group') { typeIcon = '👥'; typeLabel = 'Group'; }
                else if (chat.type === 'supergroup') { typeIcon = '👥'; typeLabel = 'Supergroup'; }
                else if (chat.type === 'channel') { typeIcon = '📢'; typeLabel = 'Channel'; }
                else if (chat.type === 'user') { typeIcon = '👤'; typeLabel = 'User'; }
                else { typeIcon = '💬'; typeLabel = 'Chat'; }
                
                return `
                <div class="chat-item">
                    <div class="chat-info">
                        <div class="chat-title">${typeIcon} ${chat.title} ${badges}</div>
                        <div class="chat-meta">
                            ${typeLabel} • ID: ${chat.id}
                            ${chat.username ? `• @${chat.username}` : ''}
                            ${chat.members ? `• ${chat.members.toLocaleString()} members` : ''}
                        </div>
                    </div>
                    <button class="danger small" onclick="deleteChat(${chat.id}, '${chat.title.replace(/'/g, "\\'")}')">Delete</button>
                </div>
            `}).join('');
        }

        function showGroups() {
            currentFilter = 'groups';
            const groups = currentChats.filter(c => c.type === 'group' || c.type === 'supergroup');
            displayChats(groups);
        }

        function showChannels() {
            currentFilter = 'channels';
            const channels = currentChats.filter(c => c.type === 'channel');
            displayChats(channels);
        }

        function showUsers() {
            currentFilter = 'users';
            const users = currentChats.filter(c => c.type === 'user');
            displayChats(users);
        }

        function showAll() {
            currentFilter = 'all';
            displayChats(currentChats);
        }

        async function deleteChat(id, title) {
            if (!confirm(`⚠️ Are you sure you want to delete "${title}"?\\n\\nThis action cannot be undone!`)) return;
            
            try {
                const response = await fetch(`/api/delete/${id}`, { method: 'POST' });
                if (response.ok) {
                    currentChats = currentChats.filter(c => c.id !== id);
                    if (currentFilter === 'all') displayChats(currentChats);
                    else if (currentFilter === 'groups') showGroups();
                    else if (currentFilter === 'channels') showChannels();
                    else if (currentFilter === 'users') showUsers();
                    
                    // Update stats
                    const response2 = await fetch('/api/chats');
                    const data = await response2.json();
                    updateStats(data.stats);
                } else {
                    const data = await response.json();
                    alert('❌ Error: ' + data.error);
                }
            } catch (e) {
                alert('❌ Network error. Please try again.');
            }
        }

        async function analyzeSpam() {
            const analysisDiv = document.getElementById('analysis-results');
            const contentDiv = document.getElementById('analysis-content');
            analysisDiv.classList.remove('hidden');
            contentDiv.innerHTML = '<div class="empty-state"><div class="loading-spinner" style="width: 40px; height: 40px; margin-bottom: 20px;"></div><p>Analyzing your chats...</p></div>';
            analysisDiv.scrollIntoView({ behavior: 'smooth' });
            
            try {
                const response = await fetch('/api/analyze');
                const data = await response.json();

                if (data.error) {
                    contentDiv.innerHTML = `<div class="empty-state"><p style="color: #dc2626;">❌ Error: ${data.error}</p></div>`;
                    return;
                }

                const counts = data.counts;
                contentDiv.innerHTML = `
                    <div class="stats" style="margin-top: 20px;">
                        <div class="stat-card" style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);">
                            <h3>Deleted Users</h3>
                            <p>${counts.deleted}</p>
                        </div>
                        <div class="stat-card" style="background: linear-gradient(135deg, #feca57 0%, #ff9f43 100%);">
                            <h3>No Messages</h3>
                            <p>${counts.no_messages}</p>
                        </div>
                        <div class="stat-card" style="background: linear-gradient(135deg, #48dbfb 0%, #0abde3 100%);">
                            <h3>Bots</h3>
                            <p>${counts.bots}</p>
                        </div>
                        <div class="stat-card" style="background: linear-gradient(135deg, #ff9ff3 0%, #f368e0 100%);">
                            <h3>Scam</h3>
                            <p>${counts.scam}</p>
                        </div>
                        <div class="stat-card" style="background: linear-gradient(135deg, #54a0ff 0%, #2e86de 100%);">
                            <h3>Fake</h3>
                            <p>${counts.fake}</p>
                        </div>
                        <div class="stat-card" style="background: linear-gradient(135deg, #1dd1a1 0%, #10ac84 100%);">
                            <h3>Active</h3>
                            <p>${counts.active}</p>
                        </div>
                    </div>
                    <h4 style="margin-top: 30px; margin-bottom: 15px;">Select a category to view users:</h4>
                    <div style="display: flex; flex-wrap: wrap; gap: 10px;">
                        <button onclick="showAnalysisCategory('deleted')" class="danger small">🗑️ Deleted (${counts.deleted})</button>
                        <button onclick="showAnalysisCategory('no_messages')" class="secondary small">📭 No Messages (${counts.no_messages})</button>
                        <button onclick="showAnalysisCategory('bots')" class="secondary small">🤖 Bots (${counts.bots})</button>
                        <button onclick="showAnalysisCategory('scam')" class="danger small">🚫 Scam (${counts.scam})</button>
                        <button onclick="showAnalysisCategory('fake')" class="danger small">⚠️ Fake (${counts.fake})</button>
                    </div>
                    <div id="analysis-users-list" class="chat-list" style="margin-top: 20px;"></div>
                `;

                window.analysisData = data.users;
            } catch (e) {
                contentDiv.innerHTML = `<div class="empty-state"><p style="color: #dc2626;">❌ Network error</p></div>`;
            }
        }

        function showAnalysisCategory(category) {
            const users = window.analysisData[category] || [];
            const listDiv = document.getElementById('analysis-users-list');
            
            if (users.length === 0) {
                listDiv.innerHTML = '<div class="empty-state"><p>No users in this category</p></div>';
                return;
            }

            listDiv.innerHTML = users.map(u => `
                <div class="chat-item">
                    <div class="chat-info">
                        <div class="chat-title">👤 ${u.title}</div>
                        <div class="chat-meta">ID: ${u.id}</div>
                    </div>
                    <button class="danger small" onclick="deleteChat(${u.id}, '${u.title.replace(/'/g, "\\'")}')">Delete</button>
                </div>
            `).join('');
            listDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function exportData(type) {
            window.open(`/api/export/${type}`, '_blank');
        }

        function showStatus(elementId, message, type) {
            const element = document.getElementById(elementId);
            element.className = `status status-${type}`;
            element.innerHTML = message;
            
            // Auto-hide success messages after 5 seconds
            if (type === 'success') {
                setTimeout(() => {
                    element.style.opacity = '0';
                    element.style.transition = 'opacity 0.5s';
                    setTimeout(() => {
                        element.className = 'hidden';
                        element.style.opacity = '1';
                    }, 500);
                }, 5000);
            }
        }

        // Check if already configured on load
        async function checkConfig() {
            try {
                const response = await fetch('/api/chats');
                if (response.ok) {
                    const data = await response.json();
                    if (!data.error) {
                        showMain();
                    }
                }
            } catch (e) {
                // Not connected yet, stay on setup page
            }
        }

        // Initialize
        window.onload = checkConfig;
    </script>
</body>
</html>"""


# Create templates directory and save HTML at startup
def create_templates():
    # Use the same TEMPLATE_DIR that Flask is configured with
    os.makedirs(TEMPLATE_DIR, exist_ok=True)

    template_path = os.path.join(TEMPLATE_DIR, "index.html")
    if not os.path.exists(template_path):
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(HTML_TEMPLATE)


# Initialize templates on module load
create_templates()


@app.route("/")
def index():
    # Ensure template exists (recreate if deleted)
    create_templates()
    return render_template("index.html")


@app.route("/api/setup", methods=["POST"])
def setup():
    """Initial setup - save phone number (API credentials are pre-configured)"""
    global config
    data = request.json

    # Check if API credentials are pre-configured
    if (
        PRE_CONFIGURED_API_ID == "YOUR_API_ID_HERE"
        or PRE_CONFIGURED_API_HASH == "YOUR_API_HASH_HERE"
    ):
        return jsonify(
            {
                "error": "This version requires pre-configuration. Please edit the script and add your API credentials."
            }
        ), 400

    config = save_config(PRE_CONFIGURED_API_ID, PRE_CONFIGURED_API_HASH, data["phone"])
    return jsonify({"success": True})


@app.route("/api/connect", methods=["POST"])
def connect():
    """Connect to Telegram"""
    global client, config, is_connected

    if not config:
        load_or_create_config()

    if not config:
        return jsonify({"error": "Not configured. Run setup first."}), 400

    try:
        # Convert api_id to int if it's a string
        api_id = config["api_id"]
        if isinstance(api_id, str):
            api_id = int(api_id)

        session_file = os.path.join(BASE_DIR, config["phone"].replace("+", ""))
        client = TelegramClient(session_file, api_id, config["api_hash"])
        client.loop.run_until_complete(client.connect())

        if client.loop.run_until_complete(client.is_user_authorized()):
            is_connected = True
            return jsonify({"status": "connected", "needs_code": False})
        else:
            client.loop.run_until_complete(client.send_code_request(config["phone"]))
            return jsonify({"status": "waiting_code", "needs_code": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/verify", methods=["POST"])
def verify():
    """Verify with code and optional 2FA password"""
    global client, is_connected

    data = request.json
    code = data.get("code")
    password = data.get("password")

    try:
        if password:
            client.loop.run_until_complete(client.sign_in(password=password))
        else:
            client.loop.run_until_complete(client.sign_in(config["phone"], code))
        is_connected = True
        return jsonify({"status": "connected"})
    except SessionPasswordNeededError:
        return jsonify({"status": "needs_password"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/chats")
def get_chats():
    """Get all chats"""
    global all_chats_cache

    if not client or not client.is_connected():
        return jsonify({"error": "Not connected"}), 400

    try:
        chats = []
        stats = {"groups": 0, "channels": 0, "users": 0, "total": 0}

        async def collect_dialogs():
            result = []
            async for dialog in client.iter_dialogs():
                result.append(dialog)
            return result

        dialogs = client.loop.run_until_complete(collect_dialogs())
        for dialog in dialogs:
            chat = dialog.entity
            chat_data = {"id": chat.id}

            if isinstance(chat, User):
                stats["users"] += 1
                chat_data["type"] = "user"
                chat_data["title"] = (
                    f"{chat.first_name or ''} {chat.last_name or ''}".strip()
                    or "Unknown"
                )
                chat_data["username"] = chat.username
                chat_data["is_deleted"] = chat.deleted
                chat_data["is_bot"] = getattr(chat, "bot", False)
                chat_data["is_scam"] = getattr(chat, "scam", False)
                chat_data["is_fake"] = getattr(chat, "fake", False)
                chat_data["is_verified"] = getattr(chat, "verified", False)
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
                chat_data["is_verified"] = getattr(chat, "verified", False)
                chat_data["is_scam"] = getattr(chat, "scam", False)
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
        return jsonify({"chats": chats, "stats": stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/analyze")
def analyze():
    """Analyze users for spam"""
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

        users_checked = 0

        async def collect_dialogs():
            result = []
            async for dialog in client.iter_dialogs():
                result.append(dialog)
            return result

        dialogs = client.loop.run_until_complete(collect_dialogs())
        for dialog in dialogs:
            if isinstance(dialog.entity, User):
                user = dialog.entity
                users_checked += 1

                user_data = {
                    "id": user.id,
                    "title": f"{user.first_name or ''} {user.last_name or ''}".strip()
                    or "Unknown",
                }

                if user.deleted:
                    analysis["deleted"].append(user_data)
                elif getattr(user, "bot", False):
                    analysis["bots"].append(
                        {"id": user.id, "title": user.first_name or "Unknown Bot"}
                    )
                elif getattr(user, "scam", False):
                    analysis["scam"].append(user_data)
                elif getattr(user, "fake", False):
                    analysis["fake"].append(user_data)
                else:
                    # Check messages (limit to first 50 users for speed)
                    if users_checked <= 50:
                        try:
                            messages = client.loop.run_until_complete(
                                client.get_messages(user, limit=1)
                            )
                            if len(messages) == 0:
                                analysis["no_messages"].append(user_data)
                            else:
                                analysis["active"].append(user_data)
                        except:
                            analysis["no_messages"].append(user_data)
                    else:
                        analysis["active"].append(user_data)

        return jsonify(
            {
                "counts": {
                    "deleted": len(analysis["deleted"]),
                    "no_messages": len(analysis["no_messages"]),
                    "only_incoming": len(analysis["only_incoming"]),
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
        entity = client.loop.run_until_complete(client.get_entity(chat_id))
        client.loop.run_until_complete(client.delete_dialog(entity))
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

        async def collect_dialogs():
            result = []
            async for dialog in client.iter_dialogs():
                result.append(dialog)
            return result

        dialogs = client.loop.run_until_complete(collect_dialogs())
        for dialog in dialogs:
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
                        "type": "supergroup" if isinstance(chat, Channel) else "group",
                    }
                )
            elif type == "channels" and isinstance(chat, Channel) and chat.broadcast:
                items.append(
                    {
                        "id": chat.id,
                        "title": chat.title,
                        "username": getattr(chat, "username", None),
                        "members": getattr(chat, "participants_count", 0),
                        "type": "channel",
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
        filepath = os.path.join(BASE_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def open_browser():
    """Automatically open browser after a short delay"""
    time.sleep(2.5)
    webbrowser.open("http://127.0.0.1:5000")


def print_banner():
    """Print a beautiful startup banner"""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "📱 TELEGRAM CHAT MANAGER" + " " * 35 + "║")
    print("╠" + "═" * 78 + "╣")
    print("║  🚀 Starting application..." + " " * 54 + "║")
    print("║  🌐 Opening browser automatically..." + " " * 45 + "║")
    print(
        "║  🔒 Your data stays on your computer - 100% private & secure"
        + " " * 20
        + "║"
    )
    print("╚" + "═" * 78 + "╝")
    print()
    print("✨ Your browser will open in a few seconds...")
    print("📍 If it doesn't open automatically, visit: http://127.0.0.1:5000")
    print()
    print("⚠️  To stop the application, press Ctrl+C or close this window")
    print()
    print("─" * 80)
    print()


def main():
    # Load config on startup
    load_or_create_config()

    # Print beautiful banner
    print_banner()

    # Open browser in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Flask app
    try:
        # Use threaded=True for better performance
        app.run(
            host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True
        )
    except KeyboardInterrupt:
        print()
        print("\n👋 Shutting down...")
        if client:
            client.disconnect()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
