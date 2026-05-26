# devgagan/modules/id.py
# Simple /id command to fetch chat/user/channel id

from pyrogram import filters
from pyrogram.types import Message
from devgagan import app  # your pyrogram Client instance import
import asyncio

@app.on_message(filters.command("id"))
async def id_cmd(client, message: Message):
    """
    Usage:
    - /id             -> returns current chat id (or user id in private)
    - reply + /id     -> returns replied user's id (and forwarded-from chat id if forwarded)
    - /id @username   -> resolves username and returns that chat id
    """
    try:
        args = message.text.split(maxsplit=1)
        # 1) If user provided a username: /id @someusername
        if len(args) > 1 and args[1].strip():
            query = args[1].strip()
            # Try to resolve username or numeric id via get_chat
            try:
                chat = await client.get_chat(query)
                text = f"🔎 Resolved: {getattr(chat, 'title', getattr(chat, 'username', ''))}\n" \
                       f"🆔 Chat ID: `{chat.id}`\n" \
                       f"📌 Type: `{chat.type}`"
            except Exception as e:
                text = f"❗ Could not resolve `{query}`.\nError: `{e}`"
            await message.reply_text(text, quote=True)
            return

        # 2) If replying to a message: show replied user id and any forwarded-from info
        if message.reply_to_message:
            rm = message.reply_to_message
            parts = []
            if rm.from_user:
                parts.append(f"👤 Replied user: `{rm.from_user.id}`")
                if getattr(rm.from_user, "username", None):
                    parts.append(f"🔗 Username: @{rm.from_user.username}")
            # If the message was forwarded from a chat (channel)
            if getattr(rm, "forward_from_chat", None):
                fc = rm.forward_from_chat
                parts.append(f"📢 Forwarded from chat: `{fc.id}`")
                if getattr(fc, "title", None):
                    parts.append(f"🏷️ Title: {fc.title}")
            # If message was forwarded from user
            if getattr(rm, "forward_from", None):
                ff = rm.forward_from
                parts.append(f"↪️ Forwarded from user: `{ff.id}`")
                if getattr(ff, "username", None):
                    parts.append(f"🔗 Username: @{ff.username}")

            # Fallback: include replied message chat id
            parts.append(f"💬 Replied message chat id: `{rm.chat.id}`")

            await message.reply_text("\n".join(parts), quote=True)
            return

        # 3) Default: return current chat id, and the sender (user) id if present
        chat = message.chat
        lines = [f"💬 Chat ID: `{chat.id}`", f"📌 Chat type: `{chat.type}`"]
        if message.from_user:
            lines.append(f"👤 Your user ID: `{message.from_user.id}`")
            if getattr(message.from_user, "username", None):
                lines.append(f"🔗 Your username: @{message.from_user.username}")
        await message.reply_text("\n".join(lines), quote=True)

    except Exception as e:
        await message.reply_text(f"❗ Error while fetching id: `{e}`", quote=True)
