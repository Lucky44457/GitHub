# ---------------------------------------------------
# File Name: __init__.py
# Author: Gagan | Fixed by Claude v2.1.1
# Fixes:
#   - asyncio.new_event_loop() hata diya (loop conflict fix)
#   - pyromod import added (app.ask fix)
#   - Startup peer caching (Peer ID error fix)
# ---------------------------------------------------

import asyncio
import logging
import time

# ✅ FIX 1: pyromod import — app.ask() ke liye
import pyromod
from pyromod import Client

from pyrogram.enums import ParseMode
from config import API_ID, API_HASH, BOT_TOKEN, STRING, MONGO_DB, DEFAULT_SESSION, LOG_GROUP, CHANNEL_ID
from telethon.sync import TelegramClient
from motor.motor_asyncio import AsyncIOMotorClient

# ✅ FIX 2: asyncio.new_event_loop() HATA DIYA
# Pehle tha: loop = asyncio.new_event_loop() → pyromod ke saath conflict karta tha
# Ab: default loop use hoga, koi conflict nahi
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)

botStartTime = time.time()

# ✅ pyromod ka Client use karo (app.ask support ke liye)
app = Client(
    "pyrobot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=50,
    parse_mode=ParseMode.MARKDOWN
)

# ✅ FIX: Sirf ek Telethon client — same session reuse karenge
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

# ✅ FIX: Duplicate Telethon client hata diya — sex (sexrepo) hi use hoga
telethon_client = sex

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
    ✅ FIX 3: Restart ke baad Peer ID invalid error fix.
    Bot startup pe LOG_GROUP aur CHANNEL_ID ko resolve karke
    Pyrogram session cache me daal do.
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
            print(f"✅ Peer cached: {peer_id}")
        except Exception as e:
            print(f"⚠️ Peer cache failed for {peer_id}: {e}")
            print("   → Bot ko us channel/group me admin banao aur ek message bhejo, phir restart karo.")


async def restrict_bot():
    global BOT_ID, BOT_NAME, BOT_USERNAME
    await setup_database()
    await app.start()
    getme = await app.get_me()
    BOT_ID = getme.id
    BOT_USERNAME = getme.username
    BOT_NAME = f"{getme.first_name} {getme.last_name}" if getme.last_name else getme.first_name

    # ✅ Startup pe peers resolve karo
    await cache_important_peers()

    if pro:
        await pro.start()
    if userrbot:
        await userrbot.start()


loop.run_until_complete(restrict_bot())
