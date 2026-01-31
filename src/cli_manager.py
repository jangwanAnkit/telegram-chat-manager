from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest, GetHistoryRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import InputPeerEmpty, Channel, Chat, User
from telethon.errors import (
    UserNotParticipantError,
    ChatAdminRequiredError,
    SessionPasswordNeededError,
)
from datetime import datetime
import json
import os
import sys
import getpass

CONFIG_FILE = "telegram_config.json"


# Load or create config
def load_config():
    """Load configuration from file or prompt user"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    print("\n" + "=" * 80)
    print("FIRST TIME SETUP")
    print("=" * 80)
    print("\nYou'll need API credentials from https://my.telegram.org/apps")
    print("1. Login with your phone number")
    print("2. Go to 'API development tools'")
    print("3. Create a new app (any name works)")
    print("4. Copy the api_id and api_hash\n")

    config = {
        "api_id": input("Enter API ID: ").strip(),
        "api_hash": input("Enter API Hash: ").strip(),
        "phone": input(
            "Enter phone number (with country code, e.g., +1234567890): "
        ).strip(),
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n[OK] Config saved to {CONFIG_FILE}")
    return config


# Load configuration
config = load_config()
api_id = config["api_id"]
api_hash = config["api_hash"]
phone = config["phone"]

client = TelegramClient(phone, api_id, api_hash)


async def fetch_all_chats():
    """Fetch ALL chats using pagination with detailed categorization"""
    all_chats = []

    print("Fetching all chats (this may take a moment)...")

    async for dialog in client.iter_dialogs():
        all_chats.append(dialog.entity)
        if len(all_chats) % 50 == 0:
            print(f"  Fetched {len(all_chats)} chats so far...")

    print(f"[OK] Fetched total {len(all_chats)} chats")
    return all_chats


def categorize_chats(all_chats):
    """Categorize chats into groups, channels, users, and unknown"""
    groups = []
    broadcast_channels = []
    supergroups = []
    users = []
    basic_groups = []
    unknown = []

    for chat in all_chats:
        try:
            if isinstance(chat, User):
                users.append(chat)
            elif isinstance(chat, Chat):
                basic_groups.append(chat)
            elif isinstance(chat, Channel):
                if getattr(chat, "broadcast", False):
                    broadcast_channels.append(chat)
                elif getattr(chat, "megagroup", False):
                    supergroups.append(chat)
                else:
                    supergroups.append(chat)
            else:
                unknown.append(chat)
        except Exception as e:
            print(f"  Error categorizing chat: {e}")
            unknown.append(chat)

    all_groups = basic_groups + supergroups

    return {
        "groups": all_groups,
        "supergroups": supergroups,
        "basic_groups": basic_groups,
        "channels": broadcast_channels,
        "users": users,
        "unknown": unknown,
    }


def print_chat_statistics(categorized):
    """Print detailed statistics about chats"""
    print("\n" + "=" * 80)
    print("CHAT STATISTICS")
    print("=" * 80)
    print(f"Total Groups: {len(categorized['groups'])}")
    print(f"  ├─ Supergroups (large groups): {len(categorized['supergroups'])}")
    print(f"  └─ Basic Groups (small groups): {len(categorized['basic_groups'])}")
    print(f"Broadcast Channels: {len(categorized['channels'])}")
    print(f"Private Chats (Users): {len(categorized['users'])}")
    if categorized["unknown"]:
        print(f"Unknown/Other: {len(categorized['unknown'])}")
    print(f"\nTotal Chats: {sum([len(v) for v in categorized.values()])}")
    print("=" * 80)


async def analyze_user_chats(users, progress_callback=None):
    """Analyze user chats to identify spam/unused contacts"""
    print("\nAnalyzing user chats (this will take a while for many users)...")

    deleted_users = []
    no_messages = []
    only_incoming = []
    bots = []
    scam_users = []
    fake_users = []
    active_chats = []

    for i, user in enumerate(users, 1):
        if i % 50 == 0:
            print(f"  Analyzed {i}/{len(users)} users...")
            if progress_callback:
                progress_callback(i, len(users))

        try:
            # Check if user is deleted
            if user.deleted:
                deleted_users.append(user)
                continue

            # Check if user is bot
            if getattr(user, "bot", False):
                bots.append(user)
                continue

            # Check if marked as scam/fake
            if getattr(user, "scam", False):
                scam_users.append(user)
                continue

            if getattr(user, "fake", False):
                fake_users.append(user)
                continue

            # Get message history to check interaction
            messages = await client.get_messages(user, limit=10)

            if len(messages) == 0:
                no_messages.append(user)
            else:
                # Check if you ever sent a message
                has_outgoing = any(msg.out for msg in messages)

                if not has_outgoing:
                    only_incoming.append(user)
                else:
                    active_chats.append(user)

        except Exception as e:
            # If we can't fetch messages, consider it suspicious
            no_messages.append(user)

    return {
        "deleted": deleted_users,
        "no_messages": no_messages,
        "only_incoming": only_incoming,
        "bots": bots,
        "scam": scam_users,
        "fake": fake_users,
        "active": active_chats,
    }


def print_user_analysis(analysis):
    """Print user chat analysis results"""
    print("\n" + "=" * 80)
    print("USER CHAT ANALYSIS")
    print("=" * 80)
    print(f"[FAIL] Deleted Users (accounts deleted): {len(analysis['deleted'])}")
    print(f"[FAIL] No Messages (empty chats): {len(analysis['no_messages'])}")
    print(f"[WARN]  Only Incoming (never replied): {len(analysis['only_incoming'])}")
    print(f"[BOT] Bots: {len(analysis['bots'])}")
    print(f"[BLOCK] Scam Users (flagged by Telegram): {len(analysis['scam'])}")
    print(f"[BLOCK] Fake Users (flagged by Telegram): {len(analysis['fake'])}")
    print(f"[OK] Active Chats (you interacted): {len(analysis['active'])}")
    print(
        f"\nTotal Spam/Unused: {len(analysis['deleted']) + len(analysis['no_messages']) + len(analysis['scam']) + len(analysis['fake'])}"
    )
    print("=" * 80)


async def export_users_to_json(users):
    """Export all users to JSON file"""
    users_list = []

    print(f"\nExporting {len(users)} users to JSON...")

    for i, user in enumerate(users, 1):
        user_data = {
            "id": user.id,
            "first_name": getattr(user, "first_name", "Unknown"),
            "last_name": getattr(user, "last_name", ""),
            "username": getattr(user, "username", None),
            "phone": getattr(user, "phone", None),
            "is_bot": getattr(user, "bot", False),
            "is_deleted": getattr(user, "deleted", False),
            "is_scam": getattr(user, "scam", False),
            "is_fake": getattr(user, "fake", False),
            "is_verified": getattr(user, "verified", False),
            "type": "user",
        }

        # Create full name for title field
        full_name = user_data["first_name"]
        if user_data["last_name"]:
            full_name += f" {user_data['last_name']}"
        user_data["title"] = full_name

        users_list.append(user_data)

        if i % 50 == 0:
            print(f"  Processed {i}/{len(users)} users...")

    filename = f"users_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(users_list, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Exported {len(users)} users to {filename}")
    print(
        f"\n[INFO] To delete users, edit this file and keep only the users you want to DELETE,"
    )
    print(f"   then use option 11 to delete them.")

    return filename


async def get_user_details(user):
    """Get details about a user"""
    details = {
        "id": user.id,
        "first_name": getattr(user, "first_name", "Unknown"),
        "last_name": getattr(user, "last_name", ""),
        "username": getattr(user, "username", None),
        "phone": getattr(user, "phone", None),
        "is_bot": getattr(user, "bot", False),
        "is_deleted": getattr(user, "deleted", False),
        "is_scam": getattr(user, "scam", False),
        "is_fake": getattr(user, "fake", False),
        "is_verified": getattr(user, "verified", False),
        "type": "user",
    }

    full_name = details["first_name"]
    if details["last_name"]:
        full_name += f" {details['last_name']}"
    details["title"] = full_name

    return details


async def get_group_details(group):
    """Fetch detailed information about a group"""
    details = {
        "title": getattr(group, "title", "Unknown"),
        "id": group.id,
        "username": getattr(group, "username", None),
        "participants_count": getattr(group, "participants_count", "Unknown"),
        "created_date": getattr(group, "date", None),
        "is_megagroup": getattr(group, "megagroup", False),
        "is_broadcast": getattr(group, "broadcast", False),
        "is_verified": getattr(group, "verified", False),
        "is_scam": getattr(group, "scam", False),
        "is_fake": getattr(group, "fake", False),
        "restriction_reason": getattr(group, "restriction_reason", None),
        "type": "Unknown",
    }

    if isinstance(group, User):
        return await get_user_details(group)
    elif isinstance(group, Chat):
        details["type"] = "Basic Group"
    elif isinstance(group, Channel):
        if details["is_broadcast"]:
            details["type"] = "Broadcast Channel"
        elif details["is_megagroup"]:
            details["type"] = "Supergroup"
        else:
            details["type"] = "Channel"

    try:
        if isinstance(group, Channel):
            full_channel = await client(GetFullChannelRequest(group))
            details["description"] = full_channel.full_chat.about or "No description"
            details["admins_count"] = getattr(
                full_channel.full_chat, "admins_count", "Unknown"
            )
            details["unread_count"] = getattr(full_channel.full_chat, "unread_count", 0)
        else:
            details["description"] = "No description"
            details["admins_count"] = "Unknown"
            details["unread_count"] = 0
    except:
        details["description"] = "Unable to fetch"
        details["admins_count"] = "Unknown"
        details["unread_count"] = 0

    return details


async def export_simple_list(items, item_type="items"):
    """Export simple item list (id + name) to JSON"""
    simple_list = []

    print(f"\nExporting simple {item_type} list...")
    for i, item in enumerate(items, 1):
        if isinstance(item, User):
            details = await get_user_details(item)
            simple_list.append(details)
        else:
            simple_list.append(
                {
                    "id": item.id,
                    "title": getattr(item, "title", f"User_{item.id}"),
                    "username": getattr(item, "username", None),
                    "members": getattr(item, "participants_count", "Unknown"),
                    "type": "broadcast_channel"
                    if getattr(item, "broadcast", False)
                    else "supergroup"
                    if getattr(item, "megagroup", False)
                    else "basic_group"
                    if isinstance(item, Chat)
                    else "unknown",
                }
            )

        if i % 50 == 0:
            print(f"  Processed {i}/{len(items)} {item_type}...")

    filename = f"{item_type}_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(simple_list, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Exported {len(items)} {item_type} to {filename}")
    print(
        f"\n[INFO] To delete items, edit this file and keep only the items you want to DELETE,"
    )
    print(f"   then use the delete option.")

    return filename


async def delete_from_json_file(all_items):
    """Delete items specified in a JSON file"""
    print("\n--- Delete Items from JSON File ---")

    json_files = [
        f
        for f in os.listdir(".")
        if f.endswith(".json")
        and ("groups_" in f or "channels_" in f or "users_" in f or "spam_" in f)
    ]

    if not json_files:
        print("[FAIL] No JSON files found in current directory")
        return

    print("\nAvailable JSON files:")
    for i, filename in enumerate(json_files, 1):
        print(f"{i}. {filename}")

    print(f"{len(json_files) + 1}. Enter custom filename")

    choice = input("\nSelect file: ").strip()

    try:
        choice_num = int(choice)
        if 1 <= choice_num <= len(json_files):
            filename = json_files[choice_num - 1]
        elif choice_num == len(json_files) + 1:
            filename = input("Enter JSON filename: ").strip()
        else:
            print("Invalid choice")
            return
    except:
        filename = choice

    if not os.path.exists(filename):
        print(f"[FAIL] File '{filename}' not found")
        return

    try:
        with open(filename, "r", encoding="utf-8") as f:
            items_to_delete = json.load(f)
    except Exception as e:
        print(f"[FAIL] Error reading JSON file: {e}")
        return

    if not items_to_delete or not isinstance(items_to_delete, list):
        print("[FAIL] Invalid JSON format. Expected a list.")
        return

    print(f"\n[OK] Loaded {len(items_to_delete)} items from {filename}")

    item_map = {item.id: item for item in all_items}

    print("\n--- Items to be deleted ---")
    found_items = []
    not_found = []

    for item in items_to_delete:
        item_id = item.get("id")
        if item_id in item_map:
            found_items.append(item_map[item_id])
            item_type = item.get("type", "unknown")
            print(f"[OK] [{item_type}] {item.get('title', 'Unknown')} (ID: {item_id})")
        else:
            not_found.append(item)
            print(f"[FAIL] {item.get('title', 'Unknown')} (ID: {item_id}) - Not found")

    if not_found:
        print(f"\n[WARN]  Warning: {len(not_found)} items not found")

    if not found_items:
        print("\n[FAIL] No matching items found to delete")
        return

    print(f"\n[WARN]  YOU ARE ABOUT TO DELETE {len(found_items)} CHATS!")
    confirm = input("Type 'DELETE' to confirm: ").strip()

    if confirm != "DELETE":
        print("[ERROR] Cancelled.")
        return

    left_count = 0
    errors = []

    print("\nDeleting chats...")
    for i, item in enumerate(found_items, 1):
        try:
            await client.delete_dialog(item)
            item_title = getattr(
                item, "title", getattr(item, "first_name", f"User_{item.id}")
            )
            print(f"[{i}/{len(found_items)}] [OK] Deleted '{item_title}'")
            left_count += 1
        except Exception as e:
            item_title = getattr(
                item, "title", getattr(item, "first_name", f"User_{item.id}")
            )
            error_msg = f"'{item_title}': {str(e)}"
            errors.append(error_msg)
            print(f"[{i}/{len(found_items)}] [FAIL] Error: {e}")

    print(f"\n{'=' * 80}")
    print(f"DELETION SUMMARY")
    print(f"{'=' * 80}")
    print(f"[OK] Successfully deleted: {left_count}/{len(found_items)} chats")

    if errors:
        print(f"\n[FAIL] Errors ({len(errors)}):")
        for error in errors[:10]:
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    log_filename = f"deletion_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "source_file": filename,
        "total_requested": len(items_to_delete),
        "found": len(found_items),
        "successfully_deleted": left_count,
        "errors": errors,
    }

    with open(log_filename, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Deletion log saved to {log_filename}")


async def list_items(items):
    """Display items in a formatted list"""
    print("\n" + "=" * 80)
    print(f"LISTING {len(items)} ITEMS")
    print("=" * 80)

    for i, item in enumerate(items, 1):
        details = await get_group_details(item)
        print(f"\n[{i}] {details['title']} [{details['type']}]")
        print(f"    ID: {details['id']}")

        if isinstance(item, User):
            print(
                f"    Username: @{details['username']}"
                if details["username"]
                else "    Username: None"
            )
            print(
                f"    Phone: {details['phone']}"
                if details["phone"]
                else "    Phone: None"
            )
            if details["is_deleted"]:
                print(f"    [WARN]  DELETED USER")
            if details["is_scam"]:
                print(f"    [BLOCK] SCAM USER")
            if details["is_fake"]:
                print(f"    [BLOCK] FAKE USER")
            if details["is_bot"]:
                print(f"    [BOT] BOT")
        else:
            print(f"    Members: {details.get('participants_count', 'Unknown')}")
            print(
                f"    Username: @{details['username']}"
                if details["username"]
                else "    Username: None"
            )

    print("\n" + "=" * 80)


async def interactive_delete_users(users):
    """Delete user chats one by one with confirmation"""
    deleted_count = 0
    skipped = []

    for i, user in enumerate(users, 1):
        # Get user details
        first_name = getattr(user, "first_name", "Unknown")
        last_name = getattr(user, "last_name", "")
        full_name = f"{first_name} {last_name}".strip()
        username = getattr(user, "username", None)
        user_id = user.id
        phone = getattr(user, "phone", None)

        # Check flags
        is_deleted = getattr(user, "deleted", False)
        is_bot = getattr(user, "bot", False)
        is_scam = getattr(user, "scam", False)
        is_fake = getattr(user, "fake", False)
        is_verified = getattr(user, "verified", False)

        # Display user info
        print(f"\n{'=' * 80}")
        print(f"[{i}/{len(users)}] {full_name}")
        print(f"{'=' * 80}")
        print(f"ID: {user_id}")
        print(f"Username: @{username}" if username else "Username: None")
        print(f"Phone: +{phone}" if phone else "Phone: None")

        # Show warnings/flags
        if is_deleted:
            print("[WARN]  DELETED USER (account no longer exists)")
        if is_bot:
            print("[BOT] BOT")
        if is_scam:
            print("[BLOCK] SCAM USER (flagged by Telegram)")
        if is_fake:
            print("[BLOCK] FAKE USER (flagged by Telegram)")
        if is_verified:
            print("[OK] VERIFIED USER")

        # Try to get last few messages for context
        try:
            messages = await client.get_messages(user, limit=3)
            if messages:
                print(f"\nLast {len(messages)} message(s):")
                for msg in messages:
                    direction = "->  You" if msg.out else "<-  Them"
                    msg_text = (
                        msg.message[:100] if msg.message else "[Media/Sticker/File]"
                    )
                    msg_date = (
                        msg.date.strftime("%Y-%m-%d %H:%M")
                        if msg.date
                        else "Unknown date"
                    )
                    print(f"  {direction} ({msg_date}): {msg_text}")
            else:
                print("\n[EMPTY] No messages in this chat")
        except Exception as e:
            print(f"\n[WARN]  Could not fetch messages: {e}")

        # Ask for action
        choice = input("\nAction? (y=delete, n=skip, q=quit): ").lower().strip()

        if choice == "q":
            print("\nStopping...")
            break
        elif choice == "y":
            try:
                await client.delete_dialog(user)
                print(f"[OK] Deleted chat with '{full_name}'")
                deleted_count += 1
            except Exception as e:
                print(f"[FAIL] Error deleting: {e}")
        else:
            print(f"- Skipped '{full_name}'")
            skipped.append(full_name)

    return deleted_count, skipped


async def main():
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = input("Enter the code sent to Telegram: ")
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = getpass.getpass(
                "Two-factor authentication enabled. Enter your password: "
            )
            await client.sign_in(password=password)

    all_chats = await fetch_all_chats()
    categorized = categorize_chats(all_chats)
    print_chat_statistics(categorized)

    all_groups = categorized["groups"]
    all_channels = categorized["channels"]
    all_users = categorized["users"]
    user_analysis = None

    while True:
        print("\n" + "=" * 80)
        print("TELEGRAM CHAT MANAGER")
        print("=" * 80)
        print(
            f"Groups: {len(all_groups)} | Channels: {len(all_channels)} | Users: {len(all_users)}"
        )
        print("=" * 80)
        print("1. Show statistics")
        print("2. Analyze user chats (find spam/unused)")
        print("3. List all groups")
        print("4. List all channels")
        print("5. List deleted users")
        print("6. List users with no interaction")
        print("7. List scam/fake users")
        print("8. Export groups to JSON")
        print("9. Export channels to JSON")
        print("10. Export spam users to JSON")
        print("11. Export all users to JSON")
        print("12. Delete from JSON file")
        print("13. Interactive delete users (one by one)")
        print("14. Refresh")
        print("15. Exit")

        menu_choice = input("\nSelect option: ").strip()

        if menu_choice == "1":
            print_chat_statistics(categorized)

        elif menu_choice == "2":
            user_analysis = await analyze_user_chats(all_users)
            print_user_analysis(user_analysis)

        elif menu_choice == "3":
            await list_items(all_groups)

        elif menu_choice == "4":
            await list_items(all_channels)

        elif menu_choice == "5":
            if not user_analysis:
                user_analysis = await analyze_user_chats(all_users)
            await list_items(user_analysis["deleted"])

        elif menu_choice == "6":
            if not user_analysis:
                user_analysis = await analyze_user_chats(all_users)
            combined = user_analysis["no_messages"] + user_analysis["only_incoming"]
            await list_items(combined)

        elif menu_choice == "7":
            if not user_analysis:
                user_analysis = await analyze_user_chats(all_users)
            combined = user_analysis["scam"] + user_analysis["fake"]
            await list_items(combined)

        elif menu_choice == "8":
            await export_simple_list(all_groups, "groups")

        elif menu_choice == "9":
            await export_simple_list(all_channels, "channels")

        elif menu_choice == "10":
            if not user_analysis:
                user_analysis = await analyze_user_chats(all_users)
            spam_users = (
                user_analysis["deleted"]
                + user_analysis["no_messages"]
                + user_analysis["scam"]
                + user_analysis["fake"]
            )
            await export_simple_list(spam_users, "spam_users")

        elif menu_choice == "11":
            await export_users_to_json(all_users)

        elif menu_choice == "12":
            await delete_from_json_file(all_chats)

        elif menu_choice == "13":
            print("\n1. All users")
            print("2. Deleted users only")
            print("3. Spam/No interaction users only")
            print("4. Scam/Fake users only")
            sub_choice = input("Select: ").strip()
            if sub_choice == "1":
                deleted, skipped = await interactive_delete_users(all_users)
            elif sub_choice == "2":
                if not user_analysis:
                    user_analysis = await analyze_user_chats(all_users)
                deleted, skipped = await interactive_delete_users(
                    user_analysis["deleted"]
                )
            elif sub_choice == "3":
                if not user_analysis:
                    user_analysis = await analyze_user_chats(all_users)
                spam_users = (
                    user_analysis["no_messages"] + user_analysis["only_incoming"]
                )
                deleted, skipped = await interactive_delete_users(spam_users)
            elif sub_choice == "4":
                if not user_analysis:
                    user_analysis = await analyze_user_chats(all_users)
                scam_users = user_analysis["scam"] + user_analysis["fake"]
                deleted, skipped = await interactive_delete_users(scam_users)
            print(f"\n[OK] Deleted: {deleted}, Skipped: {len(skipped)}")

        elif menu_choice == "14":
            print("\nRefreshing...")
            all_chats = await fetch_all_chats()
            categorized = categorize_chats(all_chats)
            print_chat_statistics(categorized)
            all_groups = categorized["groups"]
            all_channels = categorized["channels"]
            all_users = categorized["users"]
            user_analysis = None

        elif menu_choice == "15":
            print("\nExiting...")
            break

        else:
            print("Invalid option.")


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
