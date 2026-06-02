# ---------------------------------------------------
# File Name: __main__.py
# Author: Gagan | Fixed by Claude v2.2.0
# Fixes for Heroku/Koyeb compatibility:
#   - restrict_bot() ab devggn_boot() ke andar call hota hai
#     (pehle __init__.py me loop.run_until_complete tha — crash fix)
#   - uvloop optional hai — crash nahi karta agar missing ho
#   - VPS compatibility INTACT — koi breaking change nahi
# ---------------------------------------------------

import asyncio
import importlib
import gc

# ✅ uvloop — optional performance boost (VPS pe install karo)
# Heroku/Koyeb pe nahi hoga toh gracefully skip
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("✅ uvloop enabled")
except ImportError:
    print("⚠️ uvloop not found, using default asyncio loop")

from pyrogram import idle
from devgagan.modules import ALL_MODULES
from devgagan.core.mongo.plans_db import check_and_remove_expired_users
from devgagan.core.mongo.queue_db import get_all_pending, mark_done
from devgagan.modules.shrink import send_expiry_reminders, setup_daily_ttl_index
from devgagan.modules import ban
from devgagan.modules import id
from devgagan import app, restrict_bot
from config import LOG_GROUP, CHANNEL_ID


async def schedule_reminder_check():
    while True:
        await send_expiry_reminders()
        await asyncio.sleep(3600)


async def schedule_expiry_check():
    # ✅ FIX: aiojobs scheduler hata diya — wo tasks stack karta tha CPU 100% tak
    # Ab direct await karo — ek task complete hone ke baad hi agla chalega
    while True:
        try:
            await check_and_remove_expired_users()
        except Exception as e:
            print(f"Expiry check error: {e}")
        gc.collect()
        await asyncio.sleep(3600)  # har 1 ghante mein — 60s CPU waste tha


async def warm_up_peers():
    """
    ✅ REAL FIX for 'Peer id invalid' after restart.

    Pyrogram SQLite cache restart pe peer info bhool jaata hai.
    Sahi fix: startup pe LOG_GROUP aur CHANNEL_ID me ek
    silent message bhejo aur turant delete karo.
    Ye Telegram ko force karta hai peer ko session me register karne ke liye.
    """
    peers = []

    try:
        peers.append(int(LOG_GROUP))
    except (ValueError, TypeError):
        pass

    try:
        peers.append(int(CHANNEL_ID))
    except (ValueError, TypeError):
        pass

    for peer_id in peers:
        try:
            await app.get_chat(peer_id)
            print(f"✅ Peer already cached: {peer_id}")
        except Exception:
            try:
                msg = await app.send_message(peer_id, ".")
                await msg.delete()
                print(f"✅ Peer warmed up via message: {peer_id}")
            except Exception as e:
                print(f"⚠️ Peer warm-up failed for {peer_id}: {e}")
                print(f"   Fix: Bot ko {peer_id} me admin banao")


async def resume_pending_tasks():
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
                    f"Send /resume to continue.\n"
                    f"Or send /cancel to clear the task."
                )
                print(f"Notified user {user_id} ({processed}/{total})")
            except Exception as e:
                print(f"Could not notify {user_id}: {e}")
    except Exception as e:
        print(f"resume_pending_tasks error: {e}")


async def devggn_boot():
    # ✅ Step 1: Bot clients start karo (restrict_bot ab yahan se call hoga)
    # Pehle __init__.py me loop.run_until_complete(restrict_bot()) tha
    # wo Heroku/Koyeb pe crash karta tha — ab properly async hai
    await restrict_bot()
    print("✅ Bot clients started")

    # ✅ Step 2: Modules load karo
    for all_module in ALL_MODULES:
        importlib.import_module("devgagan.modules." + all_module)

    print("""
---------------------------------------------------
📂 Bot Deployed successfully ...
👨‍💻 Author: Gagan
🛠️ Version: 2.2.0
---------------------------------------------------
""")

    # ✅ Step 3: Daily TTL index setup
    await setup_daily_ttl_index()

    # ✅ Step 4: Peer warm-up PEHLE — baaki sab baad me
    await warm_up_peers()
    print("Peer warm-up done ...")

    # ✅ Step 5: Background tasks
    asyncio.create_task(schedule_expiry_check())
    asyncio.create_task(schedule_reminder_check())
    print("Auto removal started ...")

    # ✅ Step 6: Pending task resume
    await resume_pending_tasks()
    print("Pending task check done ...")

    # ✅ Step 7: Bot idle — events listen karo
    await idle()
    print("Bot stopped...")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(devggn_boot())
