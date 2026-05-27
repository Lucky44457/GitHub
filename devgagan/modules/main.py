# ---------------------------------------------------
# File Name: main.py
# Author: Gagan | Upgraded by Claude
# Version: 2.1.0
# Changes:
#   - Parallel batch processing (asyncio.gather + Semaphore)
#   - MongoDB task queue (restart resume)
#   - /resume command added
# ---------------------------------------------------

import time
import random
import string
import asyncio
from pyrogram import filters, Client
from devgagan import app, userrbot
from config import API_ID, API_HASH, FREEMIUM_LIMIT, PREMIUM_LIMIT, OWNER_ID, DEFAULT_SESSION
from devgagan.core.get_func import get_msg
from devgagan.core.func import *
from devgagan.core.mongo import db
from devgagan.core.mongo.queue_db import (
    save_task, update_progress, mark_done,
    get_pending_task, delete_task
)
from pyrogram.errors import FloodWait
from datetime import datetime, timedelta
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import subprocess
from devgagan.modules.shrink import is_user_verified

# ── Concurrency: ek saath kitne files process hon ──
# Free user: 2, Premium: 4
FREE_SEMAPHORE_LIMIT = 2
PREMIUM_SEMAPHORE_LIMIT = 4

async def generate_random_name(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))


users_loop = {}
interval_set = {}
batch_mode = {}


async def process_and_upload_link(userbot, user_id, msg_id, link, retry_count, message):
    try:
        await get_msg(userbot, user_id, msg_id, link, retry_count, message)
        try:
            await app.delete_messages(user_id, msg_id)
        except Exception:
            pass
        await asyncio.sleep(15)
    finally:
        pass


async def check_interval(user_id, freecheck):
    if freecheck != 1 or await is_user_verified(user_id):
        return True, None

    now = datetime.now()

    if user_id in interval_set:
        cooldown_end = interval_set[user_id]
        if now < cooldown_end:
            remaining_time = (cooldown_end - now).seconds
            return False, (
                f"Please wait {remaining_time} second(s) before sending another link.\n\n"
                "> Hey 👋 You can use /token to use the bot free for 3 hours without any time limit."
            )
        else:
            del interval_set[user_id]

    return True, None


async def set_interval(user_id, interval_minutes=45):
    now = datetime.now()
    interval_set[user_id] = now + timedelta(seconds=interval_minutes)


@app.on_message(
    filters.regex(r'https?://(?:www\.)?t\.me/[^\s]+|tg://openmessage\?user_id=\w+&message_id=\d+')
    & filters.private
)
async def single_link(_, message):
    user_id = message.chat.id

    if await subscribe(_, message) == 1 or user_id in batch_mode:
        return

    if users_loop.get(user_id, False):
        await message.reply(
            "You already have an ongoing process. Please wait or cancel with /cancel."
        )
        return

    if await chk_user(message, user_id) == 1 and FREEMIUM_LIMIT == 0 and user_id not in OWNER_ID and not await is_user_verified(user_id):
        await message.reply("Freemium service is currently not available. Upgrade to premium for access.")
        return

    can_proceed, response_message = await check_interval(user_id, await chk_user(message, user_id))
    if not can_proceed:
        await message.reply(response_message)
        return

    users_loop[user_id] = True

    link = message.text if "tg://openmessage" in message.text else get_link(message.text)
    msg = await message.reply("Processing...")
    userbot = await initialize_userbot(user_id)
    try:
        if await is_normal_tg_link(link):
            await process_and_upload_link(userbot, user_id, msg.id, link, 0, message)
            await set_interval(user_id, interval_minutes=45)
        else:
            await process_special_links(userbot, user_id, msg, link)

    except FloodWait as fw:
        await msg.edit_text(f'Try again after {fw.x} seconds due to floodwait from Telegram.')
    except Exception as e:
        await msg.edit_text(f"Link: `{link}`\n\n**Error:** {str(e)}")
    finally:
        users_loop[user_id] = False
        try:
            await msg.delete()
        except Exception:
            pass


async def initialize_userbot(user_id):
    data = await db.get_data(user_id)
    if data and data.get("session"):
        try:
            userbot = Client(
                "userbot",
                api_id=API_ID,
                api_hash=API_HASH,
                device_model='iPhone 16 Pro',
                session_string=data.get("session")
            )
            await userbot.start()
            return userbot
        except Exception:
            await app.send_message(user_id, "Login Expired, please /login again.")
            return None
    else:
        if DEFAULT_SESSION:
            return userrbot
        else:
            return None


async def is_normal_tg_link(link: str) -> bool:
    special_identifiers = ['t.me/+', 't.me/c/', 't.me/b/', 'tg://openmessage']
    return 't.me/' in link and not any(x in link for x in special_identifiers)


async def process_special_links(userbot, user_id, msg, link):
    if userbot is None:
        return await msg.edit_text("Try logging in to the bot and try again.")
    if 't.me/+' in link:
        result = await userbot_join(userbot, link)
        await msg.edit_text(result)
        return
    special_patterns = ['t.me/c/', 't.me/b/', '/s/', 'tg://openmessage']
    if any(sub in link for sub in special_patterns):
        await process_and_upload_link(userbot, user_id, msg.id, link, 0, msg)
        await set_interval(user_id, interval_minutes=45)
        return
    await msg.edit_text("Invalid link...")


# ═══════════════════════════════════════════════
# ✅ UPGRADED BATCH — Parallel Processing
# ═══════════════════════════════════════════════

async def process_batch_item(semaphore, userbot, user_id, url, index, total,
                              pin_msg, keyboard, users_loop, message):
    """Single batch item — semaphore ke saath parallel chalega"""
    async with semaphore:
        if not users_loop.get(user_id, False):
            return

        link = get_link(url)
        if not link:
            return

        try:
            msg = await app.send_message(user_id, f"Processing {index}/{total}...")
            await process_and_upload_link(userbot, user_id, msg.id, link, 0, message)  # ✅ FIX: message pass karo
        except FloodWait as fw:
            await asyncio.sleep(fw.x + 2)
        except Exception as e:
            print(f"Batch item error [{url}]: {e}")

        try:
            await pin_msg.edit_text(
                f"Batch process started ⚡\nProcessing: {index}/{total}\n\n**__Powered by Blue Power__**",
                reply_markup=keyboard
            )
        except Exception:
            pass

        # MongoDB me progress update karo
        try:
            await update_progress(user_id, index)
        except Exception:
            pass

        # Telegram rate limit avoid karne ke liye thoda wait
        await asyncio.sleep(5)


@app.on_message(filters.command("batch") & filters.private)
async def batch_link(_, message):
    join = await subscribe(_, message)
    if join == 1:
        return
    user_id = message.chat.id

    if users_loop.get(user_id, False):
        await app.send_message(
            message.chat.id,
            "You already have a batch process running. Please wait for it to complete."
        )
        return

    freecheck = await chk_user(message, user_id)
    if freecheck == 1 and FREEMIUM_LIMIT == 0 and user_id not in OWNER_ID and not await is_user_verified(user_id):
        await message.reply("Freemium service is currently not available. Upgrade to premium for access.")
        return

    max_batch_size = FREEMIUM_LIMIT if freecheck == 1 else PREMIUM_LIMIT

    # Start link input
    for attempt in range(3):
        start = await app.ask(message.chat.id, "Please send the start link.\n\n> Maximum tries 3")
        start_id = start.text.strip()
        s = start_id.split("/")[-1]
        if s.isdigit():
            cs = int(s)
            break
        await app.send_message(message.chat.id, "Invalid link. Please send again ...")
    else:
        await app.send_message(message.chat.id, "Maximum attempts exceeded. Try later.")
        return

    # Number of messages input
    for attempt in range(3):
        num_messages = await app.ask(message.chat.id, f"How many messages do you want to process?\n> Max limit {max_batch_size}")
        try:
            cl = int(num_messages.text.strip())
            if 1 <= cl <= max_batch_size:
                break
            raise ValueError()
        except ValueError:
            await app.send_message(
                message.chat.id,
                f"Invalid number. Please enter a number between 1 and {max_batch_size}."
            )
    else:
        await app.send_message(message.chat.id, "Maximum attempts exceeded. Try later.")
        return

    can_proceed, response_message = await check_interval(user_id, freecheck)
    if not can_proceed:
        await message.reply(response_message)
        return

    # ✅ MongoDB me task save karo (restart resume ke liye)
    await save_task(user_id, start_id, cs, cl, processed=0)

    join_button = InlineKeyboardButton("Join Channel", url="https://t.me/+DhhAmyvXj0ExZjk1")
    keyboard = InlineKeyboardMarkup([[join_button]])
    pin_msg = await app.send_message(
        user_id,
        f"Batch process started ⚡\nProcessing: 0/{cl}\n\n**Powered by Blue Power**",
        reply_markup=keyboard
    )
    await pin_msg.pin(both_sides=True)

    users_loop[user_id] = True

    try:
        userbot = await initialize_userbot(user_id)

        # ✅ SPEED FIX: Parallel processing with semaphore
        sem_limit = FREE_SEMAPHORE_LIMIT if freecheck == 1 else PREMIUM_SEMAPHORE_LIMIT
        semaphore = asyncio.Semaphore(sem_limit)

        # Saare tasks ek saath ready karo
        tasks = []
        for i, msg_num in enumerate(range(cs, cs + cl), start=1):
            url = f"{'/'.join(start_id.split('/')[:-1])}/{msg_num}"
            tasks.append(
                process_batch_item(
                    semaphore, userbot, user_id, url, i, cl,
                    pin_msg, keyboard, users_loop, message  # ✅ FIX
                )
            )

        # ✅ Parallel execute karo (sem_limit ek saath)
        await asyncio.gather(*tasks)

        # ✅ Done — task mark karo
        await mark_done(user_id)
        await delete_task(user_id)
        await set_interval(user_id, interval_minutes=300)

        await pin_msg.edit_text(
            f"Batch completed successfully for {cl} messages 🎉\n\n**__Powered by Blue Power__**",
            reply_markup=keyboard
        )
        await app.send_message(message.chat.id, "Batch completed successfully! 🎉")

    except Exception as e:
        await app.send_message(message.chat.id, f"Error: {e}")
    finally:
        users_loop.pop(user_id, None)


# ✅ NEW: /resume command — restart ke baad pending batch continue kare
@app.on_message(filters.command("resume") & filters.private)
async def resume_batch(_, message):
    user_id = message.chat.id

    if users_loop.get(user_id, False):
        await message.reply("Ek batch pehle se chal raha hai. /cancel karke try karo.")
        return

    task = await get_pending_task(user_id)
    if not task:
        await message.reply("Koi pending batch task nahi mila.")
        return

    start_id = task["start_link"]
    cs = task["start_id"]
    total = task["total"]
    done = task["processed"]
    remaining = total - done

    if remaining <= 0:
        await mark_done(user_id)
        await delete_task(user_id)
        await message.reply("Tera batch pehle se complete ho chuka hai.")
        return

    resume_from = cs + done
    await message.reply(
        f"▶️ Resuming batch from **{done + 1}/{total}**\n"
        f"Remaining: **{remaining}** messages\n\n"
        f"Send /cancel to stop."
    )

    freecheck = await chk_user(message, user_id)
    join_button = InlineKeyboardButton("Join Channel", url="https://t.me/+DhhAmyvXj0ExZjk1")
    keyboard = InlineKeyboardMarkup([[join_button]])
    pin_msg = await app.send_message(
        user_id,
        f"Resuming batch ⚡\nProcessing: {done}/{total}\n\n**Powered by Blue Power**",
        reply_markup=keyboard
    )

    users_loop[user_id] = True

    try:
        userbot = await initialize_userbot(user_id)
        sem_limit = FREE_SEMAPHORE_LIMIT if freecheck == 1 else PREMIUM_SEMAPHORE_LIMIT
        semaphore = asyncio.Semaphore(sem_limit)

        tasks = []
        for i, msg_num in enumerate(range(resume_from, resume_from + remaining), start=done + 1):
            url = f"{'/'.join(start_id.split('/')[:-1])}/{msg_num}"
            tasks.append(
                process_batch_item(
                    semaphore, userbot, user_id, url, i, total,
                    pin_msg, keyboard, users_loop, message  # ✅ FIX
                )
            )

        await asyncio.gather(*tasks)

        await mark_done(user_id)
        await delete_task(user_id)

        await pin_msg.edit_text(
            f"Resume completed! All {total} messages done 🎉\n\n**__Powered by Blue Power__**",
            reply_markup=keyboard
        )
        await app.send_message(message.chat.id, "Resume completed successfully! 🎉")

    except Exception as e:
        await app.send_message(message.chat.id, f"Resume error: {e}")
    finally:
        users_loop.pop(user_id, None)


@app.on_message(filters.command("cancel"))
async def stop_batch(_, message):
    user_id = message.chat.id

    if user_id in users_loop and users_loop[user_id]:
        users_loop[user_id] = False
        # ✅ Pending task bhi clear karo
        await delete_task(user_id)
        await app.send_message(
            message.chat.id,
            "Batch processing has been stopped successfully. You can start a new batch now."
        )
    elif user_id in users_loop and not users_loop[user_id]:
        await app.send_message(
            message.chat.id,
            "The batch process was already stopped. No active batch to cancel."
        )
    else:
        await app.send_message(
            message.chat.id,
            "No active batch processing is running to cancel."
    )
