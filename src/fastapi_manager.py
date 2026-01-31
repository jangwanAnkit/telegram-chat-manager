#!/usr/bin/env python3
"""
Telegram Chat Manager - FastAPI Version
Fully async web interface with proper async/await support
"""

import sys
import os
import json
import csv
import io
import webbrowser
import threading
import time
import asyncio
import logging
import traceback
import glob
from datetime import datetime
from contextlib import asynccontextmanager

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Telethon imports
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User
from telethon.errors import SessionPasswordNeededError

# Configure logging
# Configure logging - File AND Console
# Setup logs directory under BASE_DIR (which handles frozen/unfrozen)
if getattr(sys, "frozen", False):
    LOG_BASE = os.path.dirname(sys.executable)
else:
    LOG_BASE = os.path.dirname(os.path.abspath(__file__))

log_dir = os.path.join(LOG_BASE, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "app.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger("fastapi_manager")

# File paths (work in executable's directory)
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Determine template directory based on where we're running from
if os.path.basename(BASE_DIR) == "src":
    TEMPLATE_DIR = os.path.join(os.path.dirname(BASE_DIR), "templates")
else:
    TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

CONFIG_FILE = os.path.join(BASE_DIR, "telegram_config.json")

# Global state
client = None
config = None
all_chats_cache = None
is_connected = False
current_session_file = None

# App version
APP_VERSION = "2.0.0"

# HTML Template (embedded) - Dark Theme with JetBrains Mono
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>Telegram Chat Manager</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* CSS Variables - Dark Theme */
        :root {
            --bg-primary: #0a0a0a;
            --bg-secondary: #111111;
            --bg-tertiary: #1a1a1a;
            --bg-elevated: #222222;
            
            --accent-primary: #3b82f6;
            --accent-secondary: #60a5fa;
            --accent-gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            --accent-glow: rgba(59, 130, 246, 0.4);
            
            --text-primary: #f5f5f5;
            --text-secondary: #a1a1aa;
            --text-tertiary: #71717a;
            
            --success: #22c55e;
            --success-bg: rgba(34, 197, 94, 0.1);
            --warning: #f59e0b;
            --warning-bg: rgba(245, 158, 11, 0.1);
            --danger: #ef4444;
            --danger-bg: rgba(239, 68, 68, 0.1);
            --info: #3b82f6;
            --info-bg: rgba(59, 130, 246, 0.1);
            
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.08);
            --glass-hover: rgba(255, 255, 255, 0.06);
            
            --radius-sm: 6px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 24px;
            
            --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 24px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 8px 40px rgba(0, 0, 0, 0.5);
            
            --transition-fast: 150ms ease;
            --transition-normal: 250ms ease;
            --transition-slow: 350ms ease;
        }

        /* Reset & Base */
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        html {
            scroll-behavior: smooth;
        }

        body {
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        /* Background Pattern */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 20%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 50%);
            pointer-events: none;
            z-index: -1;
        }

        /* Container */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 16px 24px;
        }

        /* Header - Compact version */
        .header {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 0;
            margin-bottom: 16px;
        }

        .header.hidden-on-dashboard {
            display: none;
        }

        .logo {
            font-size: 28px;
            filter: drop-shadow(0 0 12px var(--accent-glow));
        }

        .header h1 {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: -0.3px;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .header p {
            display: none; /* Hide subtitle for compact mode */
        }

        /* Full header for setup screens */
        .header.full {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 32px 0;
            margin-bottom: 20px;
        }

        .header.full .logo {
            font-size: 40px;
            margin-bottom: 12px;
        }

        .header.full h1 {
            font-size: 24px;
            margin-bottom: 6px;
        }

        .header.full p {
            display: block;
            color: var(--text-secondary);
            font-size: 13px;
        }

        /* Cards */
        .card {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg);
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: var(--shadow-sm);
            transition: all var(--transition-normal);
            animation: fadeIn 0.4s ease-out forwards;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.12);
        }

        .card h2 {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .card h2 .icon {
            font-size: 24px;
        }

        /* Statistics Grid - Compact inline */
        .stats {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin: 12px 0;
        }

        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            padding: 10px 16px;
            text-align: center;
            transition: all var(--transition-normal);
            cursor: default;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .stat-card:hover {
            border-color: var(--accent-primary);
            box-shadow: 0 0 12px var(--accent-glow);
        }

        .stat-card h3 {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-tertiary);
            font-weight: 500;
        }

        .stat-card p {
            font-size: 18px;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        /* Compact toolbar */
        .toolbar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: var(--bg-secondary);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            margin-bottom: 12px;
        }

        .toolbar-section {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .toolbar-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-tertiary);
            margin-right: 4px;
        }

        .toolbar-divider {
            width: 1px;
            height: 24px;
            background: var(--glass-border);
            margin: 0 8px;
        }

        /* Selection bar */
        .selection-bar {
            display: none;
            align-items: center;
            gap: 12px;
            padding: 10px 16px;
            background: var(--accent-primary);
            border-radius: var(--radius-sm);
            margin-bottom: 12px;
            color: white;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--shadow-md);
        }

        .selection-bar.visible {
            display: flex;
        }

        .selection-count {
            font-weight: 600;
        }

        /* Buttons */
        button {
            font-family: 'JetBrains Mono', monospace;
            padding: 12px 20px;
            margin: 4px;
            background: var(--accent-primary);
            color: white;
            border: none;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all var(--transition-fast);
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        button:hover {
            background: var(--accent-secondary);
            transform: translateY(-1px);
            box-shadow: 0 4px 16px var(--accent-glow);
        }

        button:active {
            transform: translateY(0);
        }

        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        button.secondary {
            background: var(--bg-tertiary);
            border: 1px solid var(--glass-border);
        }

        button.secondary:hover {
            background: var(--bg-secondary);
            border-color: var(--text-tertiary);
            box-shadow: none;
        }
        
        button.secondary.active {
            background: var(--accent-primary);
            color: white;
            border-color: var(--accent-primary); 
        }

        button.danger {
            background: var(--danger);
        }

        button.danger:hover {
            background: #dc2626;
            box-shadow: 0 4px 16px rgba(239, 68, 68, 0.4);
        }

        button.small {
            padding: 6px 12px;
            font-size: 11px;
        }

        button.xs {
            padding: 4px 8px;
            font-size: 10px;
        }

        button.ghost {
            background: transparent;
            color: var(--text-secondary);
        }

        button.ghost:hover {
            background: var(--glass-hover);
            color: var(--text-primary);
            box-shadow: none;
        }

        /* Action Buttons Group */
        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 16px 0;
        }

        /* Inputs */
        input {
            font-family: 'JetBrains Mono', monospace;
            width: 100%;
            padding: 14px 16px;
            margin: 8px 0;
            background: var(--bg-secondary);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            font-size: 14px;
            transition: all var(--transition-fast);
        }

        input:focus {
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }

        input::placeholder {
            color: var(--text-tertiary);
        }

        label {
            display: block;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 4px;
            margin-top: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        label:first-child {
            margin-top: 0;
        }

        /* Chat List */
        .chat-list {
            max-height: 480px;
            overflow-y: auto;
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            margin: 16px 0;
            background: var(--bg-secondary);
        }

        .chat-list::-webkit-scrollbar {
            width: 8px;
        }

        .chat-list::-webkit-scrollbar-track {
            background: var(--bg-secondary);
            border-radius: 4px;
        }

        .chat-list::-webkit-scrollbar-thumb {
            background: var(--bg-tertiary);
            border-radius: 4px;
        }

        .chat-list::-webkit-scrollbar-thumb:hover {
            background: var(--text-tertiary);
        }

        .chat-item {
            padding: 10px 16px;
            border-bottom: 1px solid var(--glass-border);
            display: flex;
            align-items: center;
            transition: all var(--transition-fast);
            gap: 12px;
        }

        .chat-item:last-child {
            border-bottom: none;
        }

        .chat-item:hover {
            background: var(--glass-hover);
        }

        .chat-item.selected {
            background: rgba(59, 130, 246, 0.15);
            border-left: 3px solid var(--accent-primary);
        }

        /* Checkbox styling */
        .chat-checkbox {
            width: 18px;
            height: 18px;
            accent-color: var(--accent-primary);
            cursor: pointer;
            flex-shrink: 0;
        }

        .chat-info {
            flex: 1;
            min-width: 0;
        }

        .chat-title {
            font-weight: 500;
            font-size: 13px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }

        .chat-meta {
            font-size: 11px;
            color: var(--text-tertiary);
            margin-top: 2px;
            font-family: 'JetBrains Mono', monospace;
        }

        .chat-item:last-child {
            border-bottom: none;
        }

        .chat-item:hover {
            background: var(--glass-hover);
        }



        /* Badges - Compact */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 9px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }


        .badge-danger {
            background: var(--danger-bg);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .user-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            background: var(--bg-tertiary);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            font-size: 13px;
            color: var(--text-secondary);
            position: absolute;
            right: 24px;
            top: 24px;
            border: 1px solid #ffffff1a;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 8px var(--success);
        }

        .badge-info {
            background: var(--info-bg);
            color: var(--info);
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

        .badge-success {
            background: var(--success-bg);
            color: var(--success);
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .badge-warning {
            background: var(--warning-bg);
            color: var(--warning);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        /* Status Messages */
        .status {
            padding: 14px 18px;
            border-radius: var(--radius-sm);
            margin: 16px 0;
            font-size: 13px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-success {
            background: var(--success-bg);
            color: var(--success);
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .status-error {
            background: var(--danger-bg);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .status-info {
            background: var(--info-bg);
            color: var(--info);
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

        /* Tabs */
        .tabs {
            display: flex;
            border-bottom: 1px solid var(--glass-border);
            margin-bottom: 24px;
            gap: 8px;
        }

        .tab {
            padding: 12px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            font-weight: 500;
            font-size: 13px;
            color: var(--text-tertiary);
            transition: all var(--transition-fast);
        }

        .tab:hover {
            color: var(--text-secondary);
        }

        .tab.active {
            color: var(--accent-primary);
            border-bottom-color: var(--accent-primary);
        }

        /* Section Headers */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .section-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .section-title .count {
            font-weight: 400;
            color: var(--text-tertiary);
            font-size: 14px;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 32px 20px;
            color: var(--text-tertiary);
            font-size: 12px;
        }

        .footer a {
            color: var(--accent-secondary);
            text-decoration: none;
            transition: color var(--transition-fast);
        }

        .footer a:hover {
            color: var(--accent-primary);
        }

        .footer .version {
            margin-top: 8px;
            opacity: 0.6;
        }

        /* Hidden */
        .hidden {
            display: none !important;
        }

        /* Loading Skeleton */
        .skeleton {
            background: linear-gradient(90deg, var(--bg-tertiary) 25%, var(--bg-elevated) 50%, var(--bg-tertiary) 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: var(--radius-sm);
        }

        @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        .skeleton-text {
            height: 16px;
            margin: 8px 0;
        }

        .skeleton-stat {
            height: 48px;
        }

        /* Animations */
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .pulse {
            animation: pulse 2s infinite;
        }

        /* Loading Indicator */
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 48px 20px;
            color: var(--text-secondary);
        }

        .loading .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid var(--glass-border);
            border-top-color: var(--accent-primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 16px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Help Section */
        .help-content {
            line-height: 2;
        }

        .help-content ol {
            margin-left: 24px;
            color: var(--text-secondary);
        }

        .help-content li {
            margin: 8px 0;
        }

        .help-content a {
            color: var(--accent-secondary);
            text-decoration: none;
        }

        .help-content a:hover {
            text-decoration: underline;
        }

        .help-content strong {
            color: var(--text-primary);
        }

        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 48px 20px;
            color: var(--text-tertiary);
        }

        .empty-state .icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        .empty-state p {
            font-size: 14px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .container {
                padding: 12px;
            }

            .header, .header.full {
                padding: 16px 0;
            }

            .header.full h1 {
                font-size: 20px;
            }

            .logo, .header.full .logo {
                font-size: 28px;
            }
            
            .user-badge {
                top: 12px;
                right: 12px;
                font-size: 11px;
                padding: 4px 8px;
            }

            .card {
                padding: 16px;
            }

            .stats {
                flex-direction: column;
                gap: 8px;
            }

            .stat-card {
                width: 100%;
                justify-content: center;
            }

            .toolbar {
                flex-direction: column;
                align-items: stretch;
            }

            .toolbar-section {
                flex-wrap: wrap;
            }

            .toolbar-divider {
                display: none;
            }

            .chat-item {
                flex-wrap: wrap;
            }

            .chat-item button {
                width: auto;
            }

            button {
                padding: 10px 14px;
            }
        }

        /* Print */
        @media print {
            body::before {
                display: none;
            }
            .card {
                background: white;
                color: black;
            }
        }

        /* Messages */
        #code-section, #password-section {
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: var(--radius-md);
            border: 1px solid var(--glass-border);
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="header full" id="header">
            <div class="logo">⚡</div>
            <div class="header-content">
                <h1>Telegram Chat Manager</h1>
                <p>Clean up your Telegram — safely and privately</p>
            </div>
            <div id="user-badge" class="user-badge hidden">
                <span class="status-dot"></span>
                <span id="user-phone"></span>
            </div>
            
            <button id="shutdown-btn" onclick="shutdownServer()" class="ghost xs" style="position: absolute; top: 10px; left: 10px; opacity: 0.5;" title="Shutdown Server">
                <span class="icon">⏻</span>
            </button>
        </header>

        <div id="setup-section" class="card">
            <h2><span class="icon">🔧</span> App Configuration</h2>
            <div class="tabs">
                <div class="tab active" onclick="showTab('setup')">API Credentials</div>
                <div class="tab" onclick="showTab('help')">Help</div>
            </div>
            
            <div id="setup-tab">
                <div style="max-width: 480px;">
                    <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 13px;">
                        Configure the application with your Telegram API credentials once. 
                        You can connect different accounts later without re-entering these.
                    </p>

                    <label>API ID</label>
                    <input type="text" id="api-id" placeholder="12345678" autocomplete="off" />
                    
                    <label>API Hash</label>
                    <input type="text" id="api-hash" placeholder="a1b2c3d4e5f6g7h8i9j0..." autocomplete="off" />
                    
                    <button onclick="saveConfig()" style="width: 100%; margin-top: 20px;">
                        Save Configuration →
                    </button>
                </div>
            </div>
            
            <div id="help-tab" class="hidden">
                <div class="help-content">
                    <h3 style="margin-bottom: 16px; color: var(--text-primary);">Getting API Credentials</h3>
                    <ol>
                        <li>Visit <a href="https://my.telegram.org/apps" target="_blank">my.telegram.org/apps</a></li>
                        <li>Login with your phone number</li>
                        <li>Click "API development tools"</li>
                        <li>Fill in: App title: <strong>Chat Manager</strong>, Short name: <strong>chatmgr</strong></li>
                        <li>Copy your <strong>API ID</strong> and <strong>API Hash</strong></li>
                    </ol>
                </div>
            </div>
            <div id="setup-status"></div>
        </div>

        <div id="connect-section" class="card hidden">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <h2><span class="icon">🔌</span> Connect Account</h2>
                <button onclick="resetApp()" class="ghost xs" style="color: var(--danger);">Reset Config</button>
            </div>
            
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Enter your phone number to sign in. Your session will be saved locally.
            </p>

            <div id="phone-entry">
                <label>Phone Number</label>
                <div style="display: flex; gap: 12px; max-width: 400px;">
                    <input type="text" id="phone" placeholder="+1234567890" autocomplete="tel" />
                    <button onclick="connect()" id="connect-btn" style="min-width: 120px;">
                        Connect
                    </button>
                </div>
            </div>
            
            <div id="code-section" class="hidden" style="margin-top: 24px;">
                <label>Verification Code</label>
                <p style="color: var(--text-tertiary); font-size: 12px; margin-bottom: 8px;">Check your Telegram app for the code</p>
                <div style="display: flex; gap: 12px; max-width: 320px;">
                    <input type="text" id="code" placeholder="12345" style="font-size: 18px; letter-spacing: 4px; text-align: center;" />
                    <button onclick="verifyCode()">Verify</button>
                </div>
            </div>
            
            <div id="password-section" class="hidden" style="margin-top: 24px;">
                <label>Two-Factor Password</label>
                <p style="color: var(--text-tertiary); font-size: 12px; margin-bottom: 8px;">Enter your 2FA password</p>
                <div style="display: flex; gap: 12px; max-width: 360px;">
                    <input type="password" id="password" placeholder="••••••••" />
                    <button onclick="verifyPassword()">Verify</button>
                </div>
            </div>
            <div id="connect-status"></div>
        </div>

        <div id="main-section" class="hidden">
            <div class="toolbar">
                <div class="toolbar-section">
                    <span class="toolbar-label">Stats</span>
                    <div class="stats" id="stats">
                        <div class="stat-card">
                            <h3>Total</h3>
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
                </div>
                
                <div class="toolbar-divider"></div>
                
                <div class="toolbar-section">
                    <span class="toolbar-label">Filter</span>
                    <button onclick="setFilter('all', this)" class="secondary xs active" id="btn-all">All</button>
                    <button onclick="setFilter('groups', this)" class="secondary xs" id="btn-groups">Groups</button>
                    <button onclick="setFilter('channels', this)" class="secondary xs" id="btn-channels">Channels</button>
                    <button onclick="setFilter('users', this)" class="secondary xs" id="btn-users">Users</button>
                </div>
                
                <div class="toolbar-divider"></div>
                
                <div class="toolbar-section">
                    <span class="toolbar-label">Export</span>
                    <select id="export-format" onchange="updateExportButtons()" style="background:var(--bg-tertiary); color:var(--text-primary); border:1px solid var(--glass-border); border-radius:4px; padding:2px 4px; font-size:11px; margin-right:4px;">
                        <option value="csv">CSV</option>
                        <option value="json">JSON</option>
                    </select>
                    <button onclick="exportData('groups')" class="ghost xs">Groups</button>
                    <button onclick="exportData('channels')" class="ghost xs">Channels</button>
                    <button onclick="exportData('users')" class="ghost xs">Users</button>
                </div>
                
                <div class="toolbar-divider"></div>
                
                <div class="toolbar-section">
                    <button onclick="analyzeSpam()" class="danger xs">🚫 Find Spam</button>
                    <button onclick="loadChats()" class="secondary xs">↻ Refresh</button>
                    <button onclick="logout()" class="secondary xs" style="border-color: var(--danger-bg); color: var(--danger);">Log Out</button>
                </div>
            </div>

            <div class="selection-bar" id="selection-bar">
                <span class="selection-count"><span id="selected-count">0</span> selected</span>
                <button onclick="deleteSelected()" class="danger small">🗑️ Delete Selected</button>
                <button onclick="clearSelection()" class="ghost small">✕ Clear</button>
            </div>

            <div class="section-header">
                <div class="section-title">
                    <span>📋</span> Chats
                    <span class="count" id="chat-count"></span>
                </div>
                <label style="display: flex; align-items: center; gap: 6px; font-size: 11px; margin: 0; text-transform: none;">
                    <input type="checkbox" id="select-all" onchange="toggleSelectAll()" class="chat-checkbox">
                    Select All
                </label>
            </div>
            
            <!-- Search Box -->
            <div style="margin-bottom: 12px;">
                <input type="text" id="search-input" placeholder="🔍 Search by name..." oninput="filterBySearch()" style="padding: 10px 14px; font-size: 12px;">
            </div>
            
            <!-- Offline Banner -->
            <div id="offline-banner" class="hidden" style="background: var(--warning-bg); color: var(--warning); padding: 10px 16px; border-radius: var(--radius-md); margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                <span>⚠️</span> You are offline. Some features may not work.
            </div>
            
            <div id="chats" class="chat-list">
                <div class="empty-state">
                    <div class="icon">📭</div>
                    <p>Click "Refresh" to load your chats</p>
                </div>
            </div>
            
            <!-- Undo Toast -->
            <div id="undo-toast" class="hidden" style="position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); background: var(--bg-elevated); border: 1px solid var(--glass-border); padding: 12px 20px; border-radius: var(--radius-lg); display: flex; align-items: center; gap: 12px; box-shadow: var(--shadow-lg); z-index: 1000;">
                <span id="undo-message">Chat deleted</span>
                <button onclick="undoDelete()" class="ghost xs" style="color: var(--accent-primary);">Undo</button>
                <span id="undo-countdown" style="font-size: 11px; color: var(--text-tertiary);">10s</span>
            </div>
            
            <!-- Progress Modal -->
            <div id="progress-modal" class="hidden" style="position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1001;">
                <div style="background: var(--bg-secondary); border: 1px solid var(--glass-border); border-radius: var(--radius-lg); padding: 24px; min-width: 300px; text-align: center;">
                    <h3 style="margin-bottom: 16px;">Deleting Chats...</h3>
                    <div style="background: var(--bg-tertiary); border-radius: 999px; height: 8px; overflow: hidden; margin-bottom: 12px;">
                        <div id="progress-bar" style="background: var(--accent-primary); height: 100%; width: 0%; transition: width 0.3s;"></div>
                    </div>
                    <p id="progress-text" style="font-size: 13px; color: var(--text-secondary);">0 / 0</p>
                    <button onclick="cancelBulkDelete()" class="danger xs" style="margin-top: 16px;">Cancel</button>
                </div>
            </div>

            <div id="analysis-results" class="hidden" style="margin-top: 24px;">
                <div class="section-title" style="margin-bottom: 16px;">
                    <span>🔍</span> Spam Analysis
                </div>
                <div id="analysis-content"></div>
            </div>
        </div>

        <footer class="footer">
            <p>Built by <a href="https://ankitjang.one/" target="_blank">Ankit Jangwan</a> · 🔒 Your data stays on your computer · <a href="https://my.telegram.org/apps" target="_blank">Get API Credentials</a></p>
            <p class="version">v2.0.0</p>
        </footer>
    </div>

    <script>
        let currentChats = [];
        let currentFilter = 'all';
        let selectedChats = new Set();
        let searchQuery = '';
        let bulkDeleteCancelled = false;
        let lastDeletedChat = null;
        let undoTimeout = null;
        let displayLimit = 50;  // Pagination: show 50 chats at a time
        
        // Offline detection
        window.addEventListener('offline', () => {
            document.getElementById('offline-banner').classList.remove('hidden');
        });
        window.addEventListener('online', () => {
            document.getElementById('offline-banner').classList.add('hidden');
        });

        function updateSelectionBar() {
            const bar = document.getElementById('selection-bar');
            const count = document.getElementById('selected-count');
            count.textContent = selectedChats.size;
            bar.classList.toggle('visible', selectedChats.size > 0);
        }

        function toggleChatSelection(id) {
            if (selectedChats.has(id)) {
                selectedChats.delete(id);
            } else {
                selectedChats.add(id);
            }
            updateSelectionBar();
            updateChatItemStyles();
        }

        function toggleSelectAll() {
            const checkbox = document.getElementById('select-all');
            const visibleChats = getFilteredChats();
            
            if (checkbox.checked) {
                visibleChats.forEach(c => selectedChats.add(c.id));
            } else {
                selectedChats.clear();
            }
            
            updateSelectionBar();
            updateChatItemStyles();
        }

        function clearSelection() {
            selectedChats.clear();
            document.getElementById('select-all').checked = false;
            updateSelectionBar();
            updateChatItemStyles();
        }

        function updateChatItemStyles() {
            document.querySelectorAll('.chat-item').forEach(item => {
                const id = parseInt(item.dataset.id);
                const checkbox = item.querySelector('.chat-checkbox');
                if (selectedChats.has(id)) {
                    item.classList.add('selected');
                    if (checkbox) checkbox.checked = true;
                } else {
                    item.classList.remove('selected');
                    if (checkbox) checkbox.checked = false;
                }
            });
        }

        function getFilteredChats() {
            let chats = currentChats;
            
            // Apply type filter
            if (currentFilter === 'groups') chats = chats.filter(c => c.type === 'group' || c.type === 'supergroup');
            else if (currentFilter === 'channels') chats = chats.filter(c => c.type === 'channel');
            else if (currentFilter === 'users') chats = chats.filter(c => c.type === 'user');
            
            // Apply search filter
            if (searchQuery) {
                const q = searchQuery.toLowerCase();
                chats = chats.filter(c => 
                    c.title.toLowerCase().includes(q) || 
                    (c.username && c.username.toLowerCase().includes(q))
                );
            }
            
            return chats;
        }
        
        function filterBySearch() {
            searchQuery = document.getElementById('search-input').value.trim();
            displayLimit = 50;  // Reset pagination on new search
            displayChats(getFilteredChats());
        }

        async function deleteSelected() {
            if (selectedChats.size === 0) return;
            
            const count = selectedChats.size;
            if (!confirm(`Delete ${count} chat${count > 1 ? 's' : ''}?\n\nYou'll have 10 seconds to undo.`)) return;
            
            // Gather data for all selected chats
            const toDeleteIds = [...selectedChats];
            const storedItems = [];
            
            toDeleteIds.forEach(id => {
                const found = findChatById(id);
                if (found) storedItems.push({ ...found, id });
            });
            
            // Optimistic deletion
            const bulkId = Date.now();
            
            // Remove from all sources
            storedItems.forEach(item => {
                if (item.source === 'main') {
                    currentChats = currentChats.filter(c => c.id !== item.id);
                } else if (item.source === 'analysis') {
                    window.analysisData[item.category] = window.analysisData[item.category].filter(c => c.id !== item.id);
                }
            });
            
            selectedChats.clear();
            refreshViews();
            updateSelectionBar();
            
            // Show undo toast
            showUndoToast(`${count} chats`, bulkId);
            
            // Schedule actual delete
            const timeoutId = setTimeout(async () => {
                // Background process
                pendingDeletes.delete(bulkId);
                
                document.getElementById('progress-modal').classList.remove('hidden');
                document.getElementById('progress-bar').style.width = '0%';
                document.getElementById('progress-text').textContent = `Syncing deletions... 0 / ${count}`;
                
                let deleted = 0, failed = 0;
                bulkDeleteCancelled = false;
                
                for (const id of toDeleteIds) {
                    if (bulkDeleteCancelled) break;
                    try {
                        const response = await fetch(`/api/delete/${id}`, { method: 'POST' });
                        if (response.ok) {
                            deleted++;
                        } else {
                            const data = await response.json();
                            if (data.retry_after) {
                                await new Promise(r => setTimeout(r, data.retry_after * 1000));
                                await fetch(`/api/delete/${id}`, { method: 'POST' });
                            } else {
                                failed++;
                            }
                        }
                    } catch (e) { failed++; }
                    
                    const progress = ((deleted + failed) / count) * 100;
                    document.getElementById('progress-bar').style.width = progress + '%';
                    document.getElementById('progress-text').textContent = `Syncing deletions... ${deleted + failed} / ${count}`;
                }
                
                document.getElementById('progress-modal').classList.add('hidden');
                
                // Final sync check
                try {
                    // Update main stats
                    const r = await fetch('/api/chats');
                    const d = await r.json();
                    if (!d.error) {
                         // We don't overwrite currentChats here to avoid jarring UI shifts if user is scrolling
                         // Just update stats
                        updateStats(d.stats);
                    }
                } catch(e) {}
                
            }, 10000);
            
            pendingDeletes.set(bulkId, { timeoutId, chatData: storedItems, isBulk: true, items: storedItems });
        }
        
        function ignoreCancel() {
           // Helper to prevent reference errors if old HTML calls it
        }

        function showTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('setup-tab').classList.toggle('hidden', tab !== 'setup');
            document.getElementById('help-tab').classList.toggle('hidden', tab === 'setup');
        }

        async function saveConfig() {
            const apiId = document.getElementById('api-id').value.trim();
            const apiHash = document.getElementById('api-hash').value.trim();

            if (!apiId || !apiHash) {
                showStatus('setup-status', 'Please fill in API ID and Hash', 'error');
                return;
            }

            // Disable button to prevent double submit
            const btn = event.target;
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = 'Saving...';

            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_id: apiId, api_hash: apiHash })
                });

                if (response.ok) {
                    showStatus('setup-status', '✓ Configuration saved!', 'success');
                    setTimeout(() => showConnect(), 1000);
                } else {
                    const data = await response.json();
                    showStatus('setup-status', data.error || 'Error saving configuration', 'error');
                    btn.disabled = false;
                    btn.textContent = originalText;
                }
            } catch (e) {
                showStatus('setup-status', 'Network error. Please try again.', 'error');
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }

        async function connect() {
            const phone = document.getElementById('phone').value.trim();
            if (!phone) {
                showStatus('connect-status', 'Please enter a phone number', 'error');
                return;
            }

            const btn = document.getElementById('connect-btn');
            btn.disabled = true;
            btn.textContent = 'Connecting...';
            showStatus('connect-status', 'Connecting to Telegram...', 'info');
            
            try {
                const response = await fetch('/api/connect', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone: phone })
                });
                const data = await response.json();
                
                if (data.status === 'connected') {
                    showMain();
                    showStatus('connect-status', '', 'info');
                } else if (data.status === 'waiting_code') {
                    document.getElementById('phone-entry').classList.add('hidden');
                    document.getElementById('code-section').classList.remove('hidden');
                    showStatus('connect-status', 'Code sent! Check your Telegram app', 'success');
                }
            } catch (e) {
                showStatus('connect-status', 'Connection failed', 'error');
            } finally {
                btn.disabled = false;
                if (btn.textContent === 'Connecting...') btn.textContent = 'Connect';
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
                } else if (data.status === 'connected') {
                    showMain();
                } else if (data.error) {
                    showStatus('connect-status', '✗ ' + data.error, 'error');
                }
            } catch (e) {
                showStatus('connect-status', '✗ Verification error', 'error');
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
                    showStatus('connect-status', '✗ ' + data.error, 'error');
                }
            } catch (e) {
                showStatus('connect-status', '✗ Verification error', 'error');
            }
        }

        function showMain() {
            document.getElementById('header').classList.remove('full');
            document.getElementById('setup-section').classList.add('hidden');
            document.getElementById('connect-section').classList.add('hidden');
            document.getElementById('main-section').classList.remove('hidden');
            updateUserBadge(); // Fetch and show user info
            loadChats();
        }
        
        async function updateUserBadge() {
            try {
                const response = await fetch('/api/me');
                const data = await response.json();
                
                if (data.phone) {
                    const badge = document.getElementById('user-badge');
                    const phoneSpan = document.getElementById('user-phone');
                    
                    let displayText = data.phone;
                    if (data.first_name) displayText = `${data.first_name} (${data.phone})`;
                    else if (data.username) displayText = `@${data.username}`;
                    
                    phoneSpan.textContent = displayText;
                    badge.classList.remove('hidden');
                }
            } catch (e) {
                console.error("Failed to update user badge", e);
            }
        }

        async function loadChats() {
            const chatsDiv = document.getElementById('chats');
            chatsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><span>Loading chats...</span></div>';
            
            try {
                const response = await fetch('/api/chats');
                const data = await response.json();

                if (data.error) {
                    chatsDiv.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p style="color: var(--danger);">${data.error}</p></div>`;
                    return;
                }

                currentChats = data.chats;
                updateStats(data.stats);
                setFilter('all', document.getElementById('btn-all'));
            } catch (e) {
                chatsDiv.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p style="color: var(--danger);">Network error. Please try again.</p></div>';
            }
        }

        function updateStats(stats) {
            document.getElementById('stat-total').textContent = stats.total;
            document.getElementById('stat-groups').textContent = stats.groups;
            document.getElementById('stat-channels').textContent = stats.channels;
            document.getElementById('stat-users').textContent = stats.users;
        }

        function displayChats(chats) {
            const chatsDiv = document.getElementById('chats');
            document.getElementById('chat-count').textContent = chats.length > 0 ? `(${chats.length})` : '';
            
            if (chats.length === 0) {
                chatsDiv.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>No chats in this category</p></div>';
                return;
            }
            
            // Pagination: only show first displayLimit chats
            const visibleChats = chats.slice(0, displayLimit);
            const hasMore = chats.length > displayLimit;

            let html = visibleChats.map(chat => {
                let badges = '';
                if (chat.is_deleted) badges += '<span class="badge badge-danger">Deleted</span>';
                if (chat.is_bot) badges += '<span class="badge badge-info">Bot</span>';
                if (chat.is_scam) badges += '<span class="badge badge-danger">Scam</span>';
                
                let typeIcon = chat.type === 'channel' ? '📢' : chat.type === 'user' ? '👤' : '👥';
                const isSelected = selectedChats.has(chat.id);
                
                return `
                <div class="chat-item${isSelected ? ' selected' : ''}" data-id="${chat.id}">
                    <input type="checkbox" class="chat-checkbox" ${isSelected ? 'checked' : ''} onchange="toggleChatSelection(${chat.id})">
                    <div class="chat-info">
                        <div class="chat-title">${typeIcon} ${escapeHtml(chat.title)} ${badges}</div>
                        <div class="chat-meta">${chat.type} · ${chat.id}${chat.username ? ' · @' + chat.username : ''}${chat.members ? ' · ' + chat.members.toLocaleString() + ' members' : ''}</div>
                    </div>
                    <button class="danger xs" onclick="deleteChat(${chat.id}, '${escapeHtml(chat.title).replace(/'/g, "\\'")}')">Delete</button>
                </div>
                `;
            }).join('');
            
            // Add "Load More" button if there are more chats
            if (hasMore) {
                html += `
                <div style="text-align: center; padding: 16px;">
                    <button onclick="loadMoreChats()" class="secondary">🕳️ Load More (${chats.length - displayLimit} remaining)</button>
                </div>
                `;
            }
            
            chatsDiv.innerHTML = html;
        }
        
        function loadMoreChats() {
            displayLimit += 50;
            displayChats(getFilteredChats());
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function setFilter(type, btn) {
            currentFilter = type;
            displayLimit = 50;  // Reset pagination on filter change
            
            // Update active state
            document.querySelectorAll('.toolbar-section button').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');
            
            // Filter chats
            if (type === 'all') displayChats(currentChats);
            else if (type === 'groups') displayChats(currentChats.filter(c => c.type === 'group' || c.type === 'supergroup'));
            else if (type === 'channels') displayChats(currentChats.filter(c => c.type === 'channel'));
            else if (type === 'users') displayChats(currentChats.filter(c => c.type === 'user'));
            
            // Update selection bar state if needed
            updateSelectionBar();
        }

        let pendingDeletes = new Map(); // id -> {timeoutId, title, chatData, source}

        // Helper to find chat object across all sources
        function findChatById(id) {
            // Check main list
            let chat = currentChats.find(c => c.id === id);
            if (chat) return { chat, source: 'main' };
            
            // Check analysis data
            if (window.analysisData) {
                for (const cat in window.analysisData) {
                    chat = window.analysisData[cat].find(c => c.id === id);
                    if (chat) return { chat, source: 'analysis', category: cat };
                }
            }
            return null;
        }

        // Helper to refresh all visible lists
        function refreshViews() {
            displayChats(getFilteredChats());
            
            // Refresh analysis view if active
            if (window.currentAnalysisCategoryName && document.getElementById('analysis-results').style.display !== 'none') {
                showAnalysisCategory(window.currentAnalysisCategoryName);
            }
        }

        async function deleteChat(id, title) {
            const found = findChatById(id);
            if (!found) return; // Should not happen if UI is consistent
            
            const { chat, source, category } = found;
            
            // Optimistic deletion - remove from data sources
            if (source === 'main') {
                currentChats = currentChats.filter(c => c.id !== id);
            } else if (source === 'analysis') {
                // Remove from specific analysis category
                window.analysisData[category] = window.analysisData[category].filter(c => c.id !== id);
            }
            
            selectedChats.delete(id);
            refreshViews();
            updateSelectionBar();
            
            // Show undo toast
            showUndoToast(title, id);
            
            // Schedule actual delete
            const timeoutId = setTimeout(async () => {
                try {
                    const response = await fetch(`/api/delete/${id}`, { method: 'POST' });
                    if (!response.ok) {
                        const data = await response.json();
                        if (data.retry_after) {
                             setTimeout(() => deleteChat(id, title), data.retry_after * 1000);
                             return;
                        }
                        // Restore if failed
                        restoreChat(chat, source, category);
                        alert('Error deleting chat: ' + (data.error || 'Unknown error'));
                    } else {
                        // Success - update stats
                        try {
                            const r = await fetch('/api/chats');
                            const d = await r.json();
                            if (!d.error) updateStats(data.stats);
                        } catch(e) {}
                    }
                } catch (e) {
                    // Restore on network error
                    restoreChat(chat, source, category);
                    alert('Network error deleting chat');
                } finally {
                    pendingDeletes.delete(id);
                }
            }, 10000); // 10 seconds delay
            
            pendingDeletes.set(id, { timeoutId, title, chatData: chat, source, category });
        }
        
        function restoreChat(chat, source, category) {
            if (source === 'main') {
                currentChats.push(chat);
            } else if (source === 'analysis') {
                if (!window.analysisData[category]) window.analysisData[category] = [];
                window.analysisData[category].push(chat);
            }
            refreshViews();
            updateSelectionBar();
        }

        function showUndoToast(title, id) {
            // If there's an existing toast/timer running for THIS chat, just ignore (already handled)
            // But we actually support multiple pending deletes now.
            // The toast UI only shows one message at a time, but logic handles many.
            
            const toast = document.getElementById('undo-toast');
            const countdown = document.getElementById('undo-countdown');
            document.getElementById('undo-message').textContent = `"${title}" deleted`;
            
            // Update the toast's "Undo" button to target THIS chat
            const undoBtn = toast.querySelector('button');
            undoBtn.onclick = () => undoDelete(id);
            
            toast.classList.remove('hidden');
            toast.style.display = 'flex'; // Force flex to ensure visibility
            let remaining = 10;
            countdown.textContent = remaining + 's';
            
            // Clear previous toast timer (for UI display only)
            if (undoTimeout) clearInterval(undoTimeout);
            
            undoTimeout = setInterval(() => {
                remaining--;
                countdown.textContent = remaining + 's';
                if (remaining <= 0) {
                    clearInterval(undoTimeout);
                    toast.classList.add('hidden');
                }
            }, 1000);
        }
        
        function undoDelete(id) {
            // Check if we have a pending delete for this ID
            const pending = pendingDeletes.get(id);
            if (!pending) return;
            
            // Cancel the execution
            clearTimeout(pending.timeoutId);
            pendingDeletes.delete(id);
            
            // Restore UI
            if (Array.isArray(pending.chatData)) {
                // Bulk restore - complicated mixed sources.
                // Ideally we track source for each item.
                // For now, simplify: if it was bulk, we kept the source array or logic.
                // In deleteSelected, we'll store smarter data.
                pending.items.forEach(item => restoreChat(item.chat, item.source, item.category));
            } else {
                // Single restore
                restoreChat(pending.chatData, pending.source, pending.category);
            }
            
            // Hide toast if it was for this chat
            const toast = document.getElementById('undo-toast');
            // Loose check for either onclick content or just current ID if simple
            toast.classList.add('hidden');
            if (undoTimeout) clearInterval(undoTimeout);
        }

        async function analyzeSpam() {
            const analysisDiv = document.getElementById('analysis-results');
            const contentDiv = document.getElementById('analysis-content');

            analysisDiv.classList.remove('hidden');
            contentDiv.innerHTML = '<div class="loading"><div class="spinner"></div><span>Analyzing chats for spam...</span></div>';
            
            // Scroll to analysis section so user sees feedback
            analysisDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
            
            try {
                const response = await fetch('/api/analyze');
                const data = await response.json();

                if (data.error) {
                    contentDiv.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p style="color: var(--danger);">${data.error}</p></div>`;
                    return;
                }

                const counts = data.counts;
                contentDiv.innerHTML = `
                    <div class="stats">
                        <div class="stat-card"><h3>🗑️ Deleted Accounts</h3><p style="color: var(--danger);">${counts.deleted}</p></div>
                        <div class="stat-card"><h3>💬 No Messages</h3><p style="color: var(--warning);">${counts.no_messages}</p></div>
                        <div class="stat-card"><h3>🤖 Bots</h3><p style="color: var(--info);">${counts.bots}</p></div>
                        <div class="stat-card"><h3>⚠️ Scam</h3><p style="color: var(--danger);">${counts.scam}</p></div>
                        <div class="stat-card"><h3>🚫 Fake</h3><p style="color: var(--danger);">${counts.fake}</p></div>
                        <div class="stat-card"><h3>✅ Active</h3><p style="color: var(--success);">${counts.active}</p></div>
                    </div>
                    <div style="margin-top: 16px;">
                        <p style="color: var(--text-secondary); font-size: 12px; margin-bottom: 12px;">Click to view category:</p>
                        <div class="actions">
                            <button onclick="showAnalysisCategory('deleted')" class="secondary small">🗑️ Deleted Accounts (${counts.deleted})</button>
                            <button onclick="showAnalysisCategory('no_messages')" class="secondary small">💬 No Messages (${counts.no_messages})</button>
                            <button onclick="showAnalysisCategory('bots')" class="secondary small">🤖 Bots (${counts.bots})</button>
                            <button onclick="showAnalysisCategory('scam')" class="danger small">⚠️ Scam (${counts.scam})</button>
                            <button onclick="showAnalysisCategory('fake')" class="danger small">🚫 Fake (${counts.fake})</button>
                        </div>
                    </div>
                    <div id="analysis-users-list" class="chat-list" style="margin-top: 16px;"></div>
                `;

                window.analysisData = data.users;
            } catch (e) {
                contentDiv.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p style="color: var(--danger);">Network error</p></div>';
            }
        }

        function showAnalysisCategory(category) {
            window.currentAnalysisCategoryName = category; // Store for refresh logic
            const users = window.analysisData[category] || [];
            const listDiv = document.getElementById('analysis-users-list');
            window.currentAnalysisCategory = users;
            
            if (users.length === 0) {
                listDiv.innerHTML = '<div class="empty-state"><div class="icon">✓</div><p>No users in this category</p></div>';
                return;
            }

            const headerHtml = `
                <div class="section-header" style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding: 8px; background: var(--bg-tertiary); border-radius: 8px;">
                    <input type="checkbox" id="select-all-analysis" onchange="toggleSelectAllAnalysis(this.checked)" style="width: 18px; height: 18px;">
                    <label for="select-all-analysis" style="cursor: pointer; font-size: 13px;">Select All (${users.length})</label>
                </div>
            `;

            listDiv.innerHTML = headerHtml + users.map(u => `
                <div class="chat-item" data-id="${u.id}">
                    <input type="checkbox" class="chat-checkbox" ${selectedChats.has(u.id) ? 'checked' : ''} onchange="toggleChatSelection(${u.id})">
                    <div class="chat-info">
                        <div class="chat-title">👤 ${escapeHtml(u.title)}</div>
                        <div class="chat-meta">${u.id}</div>
                    </div>
                    <button class="danger xs" onclick="deleteChat(${u.id}, '${escapeHtml(u.title).replace(/'/g, "\\'")}')">Delete</button>
                </div>
            `).join('');
        }

        function toggleSelectAllAnalysis(checked) {
            const users = window.currentAnalysisCategory || [];
            users.forEach(u => {
                if (checked) {
                    selectedChats.add(u.id);
                } else {
                    selectedChats.delete(u.id);
                }
            });
            updateSelectionBar();
            document.querySelectorAll('#analysis-users-list .chat-checkbox').forEach(cb => { cb.checked = checked; });
            document.querySelectorAll('#analysis-users-list .chat-item').forEach(item => { item.classList.toggle('selected', checked); });
        }

        function exportData(type) {
            const format = document.getElementById('export-format').value;
            window.open(`/api/export/${type}?format=${format}`, '_blank');
        }

        function updateExportButtons() {
            // Optional: visual update if needed
        }

        function showStatus(elementId, message, type) {
            const element = document.getElementById(elementId);
            element.className = `status status-${type}`;
            element.textContent = message;
        }

        async function checkConfig() {
            try {
                // First check if app is configured
                const configRes = await fetch('/api/config');
                const configData = await configRes.json();
                
                if (!configData.configured) {
                    showSetup();
                    return;
                }

                // If configured, check if connected
                try {
                    const response = await fetch('/api/chats');
                    if (response.ok) {
                        const data = await response.json();
                        if (!data.error) {
                            showMain();
                            return;
                        }
                    }
                    // Not connected but configured
                    showConnect();
                } catch (e) {
                    showConnect();
                }
            } catch (e) {
                console.error('Config check failed:', e);
            }
        }

        function showSetup() {
            document.getElementById('header').classList.add('full');
            document.getElementById('setup-section').classList.remove('hidden');
            document.getElementById('connect-section').classList.add('hidden');
            document.getElementById('main-section').classList.add('hidden');
        }

        function showConnect() {
            document.getElementById('header').classList.add('full');
            document.getElementById('setup-section').classList.add('hidden');
            document.getElementById('connect-section').classList.remove('hidden');
            document.getElementById('main-section').classList.add('hidden');
        }



        async function logout() {
            if (!confirm('Are you sure you want to log out?')) return;
            try {
                await fetch('/api/logout', { method: 'POST' });
                location.reload();
            } catch (e) {
                alert('Logout failed');
            }
        }

        async function resetApp() {
            if (!confirm('This will delete your API credentials. Are you sure?')) return;
            try {
                await fetch('/api/reset', { method: 'POST' });
                location.reload();
            } catch (e) {
                alert('Reset failed');
            }
        }
        
        async function shutdownServer() {
            if (!confirm('Are you sure you want to stop the server? You will need to restart the application manually.')) return;
            try {
                await fetch('/api/shutdown', { method: 'POST' });
                document.body.innerHTML = `
                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; background:var(--bg-primary); color:var(--text-primary); font-family:'JetBrains Mono', monospace;">
                        <h1 style="color:var(--danger)">Server Stopped</h1>
                        <p>You can now close this tab.</p>
                    </div>
                `;
            } catch (e) {
                alert('Shutdown failed');
            }
        }

        window.onload = checkConfig;
    </script>
</body>
</html>"""


# Create templates directory
def create_templates():
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    template_path = os.path.join(TEMPLATE_DIR, "index.html")
    # Always overwrite to ensure latest template
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(HTML_TEMPLATE)


create_templates()


# Custom exception classes
class TelegramError(Exception):
    """Custom exception for Telegram-related errors"""
    def __init__(self, message: str, code: str = "TELEGRAM_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class NotConnectedError(Exception):
    """Exception when client is not connected"""
    def __init__(self, message: str = "Not connected to Telegram"):
        self.message = message
        super().__init__(self.message)


# FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info(f"Starting Telegram Chat Manager v{APP_VERSION}")
    # Try auto-connect
    await auto_connect()
    
    yield
    # Cleanup on shutdown
    global client
    if client and client.is_connected():
        await client.disconnect()
        logger.info("Disconnected from Telegram")


app = FastAPI(
    title="Telegram Chat Manager",
    description="Manage your Telegram chats locally",
    version=APP_VERSION,
    lifespan=lifespan
)


# Exception handlers
@app.exception_handler(TelegramError)
async def telegram_error_handler(request: Request, exc: TelegramError):
    logger.error(f"Telegram error: {exc.message}")
    return JSONResponse(
        status_code=400,
        content={"error": exc.message, "code": exc.code}
    )


@app.exception_handler(NotConnectedError)
async def not_connected_handler(request: Request, exc: NotConnectedError):
    logger.warning(f"Not connected: {exc.message}")
    return JSONResponse(
        status_code=400,
        content={"error": exc.message, "code": "NOT_CONNECTED"}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "code": "HTTP_ERROR"}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"}
    )


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration:.2f}s)")
    return response


class ConfigRequest(BaseModel):
    api_id: str
    api_hash: str


class ConnectRequest(BaseModel):
    phone: str


class VerifyRequest(BaseModel):
    code: str = None
    password: str = None


# Helper functions
def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            config = None
    return config


def save_config(api_id, api_hash, phone=None):
    # Load existing to preserve phone if only updating API keys
    current = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                current = json.load(f)
        except:
            pass

    config_data = {
        "api_id": api_id, 
        "api_hash": api_hash,
        "phone": phone or current.get("phone")
    }
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=2)
    logger.info("Configuration saved")
    return config_data


@app.post("/api/shutdown")
async def shutdown_server():
    """Graceful shutdown of the server"""
    logger.info("Shutdown requested via API")
    if client and client.is_connected():
        await client.disconnect()
    
    # Run shutdown in separate thread to allow response to return
    import threading
    import time
    def kill():
        time.sleep(1)
        os._exit(0)
    
    threading.Thread(target=kill).start()
    return {"success": True, "message": "Server shutting down..."}

async def auto_connect():
    """Attempt to auto-connect if config and session exist"""
    global client, config, is_connected, current_session_file
    
    if not config:
        load_config()
        
    if config and config.get("api_id") and config.get("api_hash") and config.get("phone"):
        try:
            phone = config["phone"]
            logger.info(f"Attempting auto-connect for {phone}")
            
            # Ensure directory for session file exists
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            session_path = os.path.join(BASE_DIR, phone.replace("+", ""))
            
            client = TelegramClient(session_path, config["api_id"], config["api_hash"])
            await client.connect()
            
            if await client.is_user_authorized():
                is_connected = True
                current_session_file = session_path + ".session"
                logger.info(f"Auto-connected successfully as {phone}")
            else:
                logger.warning("Auto-connect failed: Session valid but not authorized")
                await client.disconnect()
                client = None
        except Exception as e:
            logger.error(f"Auto-connect error: {e}")
            if client:
                await client.disconnect()
            client = None


# Routes
@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main web interface"""
    create_templates()
    with open(os.path.join(TEMPLATE_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": "TelegramChatManager",
        "version": APP_VERSION,
        "connected": is_connected
    }


@app.get("/api/config")
async def get_config():
    """Get current configuration status"""
    global config
    if not config:
        load_config()
    
    
    # Return basic config status
    return {
        "configured": config is not None,
        "api_id": config["api_id"] if config else None,
        "phone": config.get("phone") if config else None,  # Return saved phone
        "has_hash": bool(config and config.get("api_hash"))
    }


@app.get("/api/me")
async def get_me():
    """Get currently logged in user info"""
    global client
    if not client or not client.is_connected():
        if config and config.get("phone"):
             return {"phone": config["phone"], "connected": False} # Return saved phone even if not connected
        raise NotConnectedError()
        
    try:
        me = await client.get_me()
        return {
            "id": me.id,
            "username": me.username,
            "phone": me.phone,
            "first_name": me.first_name,
            "connected": True
        }
    except Exception as e:
        logger.error(f"Error getting me: {e}")
        return {"error": str(e)}


@app.post("/api/config")
async def save_app_config(data: ConfigRequest):
    """Save Telegram API credentials"""
    global config
    config = save_config(data.api_id, data.api_hash)
    return {"success": True}


@app.post("/api/connect")
async def connect(data: ConnectRequest):
    """Connect to Telegram using provided phone"""
    global client, config, is_connected

    if not config:
        load_config()

    if not config:
        raise TelegramError("App not configured. Save API credentials first.", "NOT_CONFIGURED")

    try:
        api_id = (
            int(config["api_id"])
            if isinstance(config["api_id"], str)
            else config["api_id"]
        )
        
        # Ensure directory for session file exists
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        session_path = os.path.join(BASE_DIR, data.phone.replace("+", ""))
        
        # Store for cleanup
        global current_session_file
        current_session_file = session_path + ".session"

        client = TelegramClient(session_path, api_id, config["api_hash"])
        await client.connect()

        if await client.is_user_authorized():
            is_connected = True
             # Save phone to config for auto-connect
            save_config(config["api_id"], config["api_hash"], data.phone)
            logger.info(f"Already authorized ({data.phone}), connected successfully")
            return {"status": "connected", "needs_code": False}
        else:
            await client.send_code_request(data.phone)
            logger.info(f"Code sent to {data.phone}")
            # Store phone in client object or temp global for verification step
            client._phone = data.phone
            return {"status": "waiting_code", "needs_code": True}
    except Exception as e:
        logger.error(f"Connection error: {e}")
        raise TelegramError(str(e), "CONNECTION_ERROR")


@app.post("/api/logout")
async def logout():
    """Logout current session and delete session file"""
    global client, is_connected, current_session_file, config
    
    if client:
        await client.log_out() # Properly invalidate session on Telegram server side if possible
        if client.is_connected():
            await client.disconnect()
            
    is_connected = False
    client = None
    
    # Remove phone from config (but keep API keys)
    if config:
        config = save_config(config["api_id"], config["api_hash"], None)
    
    # Delete the specific session file for this user
    if current_session_file and os.path.exists(current_session_file):
        try:
            os.remove(current_session_file)
            logger.info(f"Deleted session file: {current_session_file}")
        except Exception as e:
            logger.error(f"Error deleting session file: {e}")
            
    current_session_file = None
    logger.info("Logged out and cleaned up")
    return {"success": True}


@app.post("/api/reset")
async def reset_app():
    """Reset application configuration"""
    global client, config, is_connected
    if client:
        try:
            # Try to terminate session on Telegram servers first
            if await client.is_user_authorized():
                await client.log_out()
                logger.info("Terminated session on Telegram server")
        except Exception as e:
            logger.warning(f"Could not terminate session on server: {e}")
            
        if client.is_connected():
            await client.disconnect()
            
    is_connected = False
    client = None
    config = None
    
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
        logger.info("Config file deleted")
        
    # Delete ALL .session files in BASE_DIR
    try:
        session_files = glob.glob(os.path.join(BASE_DIR, "*.session"))
        for f in session_files:
            try:
                os.remove(f)
                logger.info(f"Deleted orphan session file: {f}")
            except Exception as e:
                logger.error(f"Failed to delete {f}: {e}")
    except Exception as e:
        logger.error(f"Error cleaning up session files: {e}")
        
    return {"success": True}


@app.post("/api/verify")
async def verify(data: VerifyRequest):
    """Verify with code or 2FA password"""
    global client, is_connected

    try:
        if data.password:
            await client.sign_in(password=data.password)
            logger.info("Signed in with 2FA password")
        else:
            await client.sign_in(client._phone, data.code)
            logger.info("Signed in with code")

        is_connected = True
        # Save phone to config for auto-connect
        save_config(config["api_id"], config["api_hash"], client._phone)
        
        return {"status": "connected"}
    except SessionPasswordNeededError:
        logger.info("2FA password required")
        return {"status": "needs_password"}
    except Exception as e:
        logger.error(f"Verification error: {e}")
        raise TelegramError(str(e), "VERIFICATION_ERROR")


@app.get("/api/chats")
async def get_chats():
    """Get all chats with statistics"""
    global all_chats_cache

    if not client or not client.is_connected():
        raise NotConnectedError()

    try:
        chats = []
        stats = {"groups": 0, "channels": 0, "users": 0, "total": 0}

        async for dialog in client.iter_dialogs():
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
            else:
                stats["groups"] += 1
                chat_data["type"] = "group"
                chat_data["title"] = getattr(chat, "title", "Unknown")
                chat_data["members"] = getattr(chat, "participants_count", 0)

            stats["total"] += 1
            chats.append(chat_data)

        all_chats_cache = chats
        logger.info(f"Loaded {stats['total']} chats")
        return {"chats": chats, "stats": stats}
    except Exception as e:
        logger.error(f"Error loading chats: {e}")
        raise TelegramError(str(e), "LOAD_CHATS_ERROR")


@app.get("/api/analyze")
async def analyze():
    """Analyze users for spam and suspicious accounts"""
    if not client or not client.is_connected():
        raise NotConnectedError()

    try:
        analysis = {
            "deleted": [],
            "no_messages": [],
            "bots": [],
            "scam": [],
            "fake": [],
            "active": [],
        }

        users_checked = 0
        async for dialog in client.iter_dialogs():
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
                    if users_checked <= 50:
                        try:
                            messages = await client.get_messages(user, limit=1)
                            if len(messages) == 0:
                                analysis["no_messages"].append(user_data)
                            else:
                                analysis["active"].append(user_data)
                        except:
                            analysis["no_messages"].append(user_data)
                    else:
                        analysis["active"].append(user_data)

        logger.info(f"Analyzed {users_checked} users")
        return {
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
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise TelegramError(str(e), "ANALYSIS_ERROR")


@app.post("/api/delete/{chat_id}")
async def delete_chat(chat_id: int):
    """Delete a specific chat"""
    if not client or not client.is_connected():
        raise NotConnectedError()

    try:
        entity = await client.get_entity(chat_id)
        await client.delete_dialog(entity)
        logger.info(f"Deleted chat {chat_id}")
        return {"success": True}
    except Exception as e:
        # Check for rate limiting (FloodWaitError)
        error_str = str(e)
        if "FloodWaitError" in type(e).__name__ or "flood" in error_str.lower():
            # Extract wait time from error
            import re
            match = re.search(r'(\d+)', error_str)
            wait_time = int(match.group(1)) if match else 30
            logger.warning(f"Rate limited for {wait_time} seconds")
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limited", "retry_after": wait_time}
            )
        logger.error(f"Delete error: {e}")
        raise TelegramError(str(e), "DELETE_ERROR")



@app.get("/api/export/{export_type}")
async def export_data_endpoint(export_type: str, format: str = "json"):
    """Export data as JSON or CSV"""
    global client, all_chats_cache

    if not client or not client.is_connected():
        raise NotConnectedError()

    if not all_chats_cache:
        await load_chats()

    data = []
    filename_prefix = export_type

    try:
        if export_type == "groups":
            data = [
                chat_to_dict(c) 
                for c in all_chats_cache 
                if isinstance(c, (Chat, Channel)) and (getattr(c, "megagroup", False) or isinstance(c, Chat))
            ]
        elif export_type == "channels":
            data = [
                chat_to_dict(c) 
                for c in all_chats_cache 
                if isinstance(c, Channel) and not getattr(c, "megagroup", False)
            ]
        elif export_type == "users":
            data = [
                chat_to_dict(c) 
                for c in all_chats_cache 
                if isinstance(c, User)
            ]
        else:
            raise HTTPException(status_code=400, detail="Invalid export type")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "csv":
            filename = f"{filename_prefix}_{timestamp}.csv"
            output = io.StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            logger.info(f"Exported {len(data)} {export_type} to {filename} as CSV")
            return HTMLResponse(
                content=output.getvalue(),
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Type": "text/csv"
                }
            )
        else: # Default to JSON
            filename = f"{filename_prefix}_{timestamp}.json"
            # Ensure the output directory exists
            output_dir = os.path.join(BASE_DIR, "data", "output")
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            
            logger.info(f"Exported {len(data)} {export_type} to {filename} as JSON")
            # Return file download
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type="application/json"
            )
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise TelegramError(str(e), "EXPORT_ERROR")

