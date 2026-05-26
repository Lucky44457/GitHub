# ---------------------------------------------------
# File Name: __init__.py
# Author: Gagan | Fixed by Claude
# Version: 2.1.1
# Fixes:
#   - pyromod import (app.ask fix)
#   - Peer ID cache on startup (channel/log_group fix)
# ---------------------------------------------------

import asyncio
import logging
import time
import pyromod  # ✅ FIX 1: app.ask() ke liye — pyromod patch karta hai Client ko
from pyromod import Client  # pyromod wala Client use karo
from pyrogram.enums import ParseMode
from config import API_ID, API_HASH, BOT_TOKEN, STRING, MONGO_DB, DEFAULT_SESSION, LOG_GROUP, CHANNEL_ID
from telethon.sync import TelegramClient
from motor.motor_asyncio import AsyncIOMotorClient

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)

botStartTime = time.time()

app = Client(
    "pyrobot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=50,
    parse_mode=ParseMode.MARKDOWN
)

sex = TelegramClient('sexrepo', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

if STRING:
    from pyrogram import Client as PyroClient
    pro = PyroClient("ggbot", api_id=API_ID, api_hash=API_HASH, session_string=STRING)
else:
    pro = None

if DEFAULT_SESSION:
    from pyrogram import Client as PyroClient
    userrbot = PyroClient("userrbot", api_id=API_ID, api_hash=API_HASH, session_string=DEFAULT_SESSION)
else:
    userrbot = None

telethon_client = TelegramClient('telethon_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# MongoDB setup
tclient = AsyncIOMotorClient(MONGO_DB)
tdb = tclient["telegram_bot"]
token = tdb["tokens"]

async def create_ttl_index():
    await token.create_index("expires_at", expireAfterSeconds=0)

async def setup_database():
    await create_ttl_index()
    print("MongoDB TTL index created.")

async def cache_important_peers():
    """
    ✅ FIX 2: Restart ke baad Peer ID error fix
    Pyrogram restart pe channel/group peers bhool jaata hai.
    Startup pe resolve karke cache me daal do.
    """
    peers_to_cache = []
    
    try:
        log_group_id = int(LOG_GROUP)
        peers_to_cache.append(log_group_id)
    except (ValueError, TypeError):
        pass
    
    try:
        peers_to_cache.append(int(CHANNEL_ID))
    except (ValueError, TypeError):
        pass

    for peer_id in peers_to_cache:
        try:
            await app.get_chat(peer_id)
            print(f"Peer cached: {peer_id}")
        except Exception as e:
            print(f"Could not cache peer {peer_id}: {e}")
            print("Tip: Bot ko us channel/group me admin banao aur ek baar message bhejo.")

async def restrict_bot():
    global BOT_ID, BOT_NAME, BOT_USERNAME
    await setup_database()
    await app.start()
    getme = await app.get_me()
    BOT_ID = getme.id
    BOT_USERNAME = getme.username
    BOT_NAME = f"{getme.first_name} {getme.last_name}" if getme.last_name else getme.first_name

    # ✅ FIX 2: Startup pe peers cache karo
    await cache_important_peers()

    if pro:
        await pro.start()
    if userrbot:
        await userrbot.start()

loop.run_until_complete(restrict_bot())
