# ---------------------------------------------------
# File Name: __main__.py
# Author: Gagan | Upgraded by Claude v2.1.2
# Fix: Peer ID error on restart — startup me channels
#      me message bhej ke forcefully cache karo
# ---------------------------------------------------

import asyncio
import importlib
import gc

# ✅ uvloop — async event loop 30-40% faster
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("✅ uvloop enabled")
except ImportError:
    print("⚠️ uvloop not found, using default loop")
from pyrogram import idle
from devgagan.modules import ALL_MODULES
from devgagan.core.mongo.plans_db import check_and_remove_expired_users
from devgagan.core.mongo.queue_db import get_all_pending, mark_done
from devgagan.modules.shrink import send_expiry_reminders, setup_daily_ttl_index
from aiojobs import create_scheduler
from devgagan.modules import ban
from devgagan.modules import id
from devgagan import app
from config import LOG_GROUP, CHANNEL_ID

loop = asyncio.get_event_loop()


async def schedule_reminder_check():
    while True:
        await send_expiry_reminders()
        await asyncio.sleep(3600)


async def schedule_expiry_check():
    scheduler = await create_scheduler()
    while True:
        await scheduler.spawn(check_and_remove_expired_users())
        await asyncio.sleep(60)
        gc.collect()


async def warm_up_peers():
    """
    ✅ REAL FIX for 'Peer id invalid' after restart.

    Pyrogram SQLite cache restart pe peer info bhool jaata hai.
    get_chat() numeric ID se tab kaam karta hai jab peer cache me ho.

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
            # Step 1: Pehle get_chat try karo (agar pehle se cache me ho)
            await app.get_chat(peer_id)
            print(f"✅ Peer already cached: {peer_id}")
        except Exception:
            # Step 2: Cache miss — ek message bhejo aur delete karo
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
    for all_module in ALL_MODULES:
        importlib.import_module("devgagan.modules." + all_module)

    print("""
---------------------------------------------------
📂 Bot Deployed successfully ...
👨‍💻 Author: Gagan
🛠️ Version: 2.1.2
---------------------------------------------------
""")

    # ✅ Daily TTL index setup
    await setup_daily_ttl_index()
    # ✅ Peer warm-up PEHLE — baaki sab baad me
    await warm_up_peers()
    print("Peer warm-up done ...")

    asyncio.create_task(schedule_expiry_check())
    asyncio.create_task(schedule_reminder_check())
    print("Auto removal started ...")

    await resume_pending_tasks()
    print("Pending task check done ...")

    await idle()
    print("Bot stopped...")


if __name__ == "__main__":
    loop.run_until_complete(devggn_boot())
