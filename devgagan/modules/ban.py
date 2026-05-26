# devgagan/modules/ban.py
# Ban system for Pyrogram bot
# - stores banned user IDs in a JSON file (banned_users.json)
# - provides /ban, /unban, /bannedlist commands (admins only)
# - a global pre-check handler that blocks banned users from using the bot

import os
import json
import threading
from typing import List

from pyrogram import filters
from pyrogram.types import Message
from devgagan import app
import config

BANNED_FILE = os.path.join(os.path.dirname(__file__), "..", "banned_users.json")
_LOCK = threading.Lock()


def _load_banned() -> List[int]:
    try:
        with _LOCK:
            if not os.path.exists(BANNED_FILE):
                return []
            with open(BANNED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [int(x) for x in data]
    except Exception:
        return []


def _save_banned(lst: List[int]):
    with _LOCK:
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            json.dump([int(x) for x in lst], f)


def is_banned(user_id: int) -> bool:
    return int(user_id) in _load_banned()


def ban_user(user_id: int):
    lst = _load_banned()
    if int(user_id) not in lst:
        lst.append(int(user_id))
        _save_banned(lst)


def unban_user(user_id: int):
    lst = _load_banned()
    if int(user_id) in lst:
        lst.remove(int(user_id))
        _save_banned(lst)


def get_banned_list() -> List[int]:
    return _load_banned()


# helper: check admin (uses config.OWNER_ID list)
def _is_admin(user_id: int) -> bool:
    try:
        return int(user_id) in list(map(int, config.OWNER_ID))
    except Exception:
        return False


# Global handler that blocks banned users early.
@app.on_message(filters.create(lambda _, __, msg: msg.from_user and is_banned(msg.from_user.id)))
async def _blocked_banned_users(_, message: Message):
    try:
        await message.reply_text(
            "🚫 You are banned from using this bot.\n"
            "If you think this is a mistake, contact the bot owner.",
            quote=True
        )
    except Exception:
        pass
    # Do not re-raise so other handlers won't run for this message.


# Admin command: /ban <user_id or reply>
@app.on_message(filters.command("ban") & filters.user(config.OWNER_ID))
async def _ban_cmd(_, message: Message):
    target_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split(maxsplit=1)
        if len(args) > 1 and args[1].strip().isdigit():
            target_id = int(args[1].strip())

    if not target_id:
        await message.reply_text("Usage: /ban <user_id> or reply to a user's message.", quote=True)
        return

    if _is_admin(target_id):
        await message.reply_text("❗ Can't ban an owner/admin.", quote=True)
        return

    ban_user(target_id)
    await message.reply_text(f"✅ Banned user `{target_id}`.", quote=True)


# Admin command: /unban <user_id or reply>
@app.on_message(filters.command("unban") & filters.user(config.OWNER_ID))
async def _unban_cmd(_, message: Message):
    target_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split(maxsplit=1)
        if len(args) > 1 and args[1].strip().isdigit():
            target_id = int(args[1].strip())

    if not target_id:
        await message.reply_text("Usage: /unban <user_id> or reply to a user's message.", quote=True)
        return

    unban_user(target_id)
    await message.reply_text(f"✅ Unbanned user `{target_id}`.", quote=True)


# Admin command: /bannedlist - shows list (first 200 users)
@app.on_message(filters.command("bannedlist") & filters.user(config.OWNER_ID))
async def _banned_list_cmd(_, message: Message):
    lst = get_banned_list()
    if not lst:
        await message.reply_text("No banned users.", quote=True)
        return

    lines = [f"- `{uid}`" for uid in lst[:200]]
    text = "🚫 Banned users:\n\n" + "\n".join(lines)
    await message.reply_text(text, quote=True)