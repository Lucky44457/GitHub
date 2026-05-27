# ---------------------------------------------------
# File Name: __main__.py
# Author: Gagan | Upgraded by Claude
# Version: 2.1.0 — Resume on restart added
# ---------------------------------------------------

import asyncio
import importlib
import gc
from pyrogram import idle
from devgagan.modules import ALL_MODULES
from devgagan.core.mongo.plans_db import check_and_remove_expired_users
from devgagan.core.mongo.queue_db import get_all_pending, mark_done
from devgagan.modules.shrink import send_expiry_reminders
from aiojobs import create_scheduler
from devgagan.modules import ban
from devgagan.modules import id
from devgagan import app

# ----------------------------Bot-Start---------------------------- #

loop = asyncio.get_event_loop()


async def schedule_reminder_check():
    while True:
        await send_expiry_reminders()
        await asyncio.sleep(3600)  # har 1 ghante me check karo

async def schedule_expiry_check():
    scheduler = await create_scheduler()
    while True:
        await scheduler.spawn(check_and_remove_expired_users())
        await asyncio.sleep(60)
        gc.collect()


async def resume_pending_tasks():
    """
    Bot restart ke baad saare pending batch tasks users ko notify karo.
    Actual resume devgagan/modules/main.py ke andar hoga jab user dobara /batch karega,
    ya user /resume command use karega.
    """
    try:
        pending = await get_all_pending()
        if not pending:
            print("No pending tasks to resume.")
            return

        for task in pending:
            user_id = task.get("user_id")
            processed = task.get("processed", 0)
            total = task.get("total", 0)

            if processed >= total:
                await mark_done(user_id)
                continue

            try:
                await app.send_message(
                    user_id,
                    f"🔄 **Bot restarted!**\n\n"
                    f"Your last batch was at **{processed}/{total}**.\n\n"
                    f"Send /resume to continue from where it stopped.\n"
                    f"Or send /cancel to clear the pending task."
                )
                print(f"Notified user {user_id} about pending task ({processed}/{total})")
            except Exception as e:
                print(f"Could not notify user {user_id}: {e}")

    except Exception as e:
        print(f"resume_pending_tasks error: {e}")


async def devggn_boot():
    for all_module in ALL_MODULES:
        importlib.import_module("devgagan.modules." + all_module)

    print("""
---------------------------------------------------
📂 Bot Deployed successfully ...
📝 Description: A Pyrogram bot for downloading files from Telegram channels or groups 
                and uploading them back to Telegram.
👨‍💻 Author: Gagan
🌐 GitHub: https://github.com/devgaganin/
📬 Telegram: https://t.me/PdfsHubbb
▶️ YouTube: https://youtube.com/@dev_gagan
🗓️ Created: 2025-01-11
🔄 Last Modified: 2025-05-27
🛠️ Version: 2.1.0
📜 License: MIT License
---------------------------------------------------
""")

    asyncio.create_task(schedule_expiry_check())
    asyncio.create_task(schedule_reminder_check())
    print("Auto removal started ...")

    # ✅ NEW: Pending batch tasks users ko notify karo
    await resume_pending_tasks()
    print("Pending task check done ...")

    await idle()
    print("Bot stopped...")


if __name__ == "__main__":
    loop.run_until_complete(devggn_boot())

# ------------------------------------------------------------------ #
