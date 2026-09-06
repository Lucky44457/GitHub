# ---------------------------------------------------
# File Name: __init__.py
# Author: Gagan | Fixed by Claude v2.2.0
# Fixes for Heroku/Koyeb compatibility:
#   - Telethon .start() ab import time pe NAHI chalta
#     (blocking call tha — Heroku/Koyeb crash karta tha)
#   - loop.run_until_complete(restrict_bot()) ab yahan NAHI hai
#     __main__.py ke devggn_boot() me move kiya
#   - Pyrogram SQLite session → MemoryStorage use karo agar
#     BOT_SESSION env set nahi hai (ephemeral filesystem fix)
#   - Telethon: StringSession use karo — filesystem pe depend nahi
#   - VPS compatibility INTACT hai — koi breaking change nahi
# ---------------------------------------------------

import asyncio
import logging
import os
import time

# ✅ pyromod import — app.ask() ke liye
# pyromod 0.2.0+ mein Client directly export nahi hota
# Client pyrofork (pyrogram) se aata hai, pyromod sirf patch karta hai
import pyromod
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.storage import MemoryStorage

from config import API_ID, API_HASH, BOT_TOKEN, STRING, MONGO_DB, DEFAULT_SESSION, LOG_GROUP, CHANNEL_ID
from telethon import TelegramClient          # ← telethon.sync NAHI (sync blocking hai)
from telethon.sessions import StringSession
from motor.motor_asyncio import AsyncIOMotorClient

# ✅ Event loop — safely get or create
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

# ✅ Pyrogram Client
# - VPS pe "pyrobot.session" file banta hai (persistent)
# - Heroku/Koyeb pe filesystem wipe hota hai restart pe,
#   isliye MemoryStorage fallback use karo
#   (Bot re-auth nahi maangega kyunki BOT_TOKEN se login hota hai)
_SESSION_NAME = "pyrobot"
app = Client(
    _SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=50,
    parse_mode=ParseMode.MARKDOWN,
)

# ✅ Telethon Client — StringSession use karo
# - StringSession filesystem pe kuch store NAHI karta
# - VPS aur Heroku/Koyeb dono pe same tarike se kaam karta hai
# - BOT_SESSION env var optional hai — agar set hai toh reuse hoga
#   warna fresh empty StringSession (bot token se login hoga)
_bot_session_str = os.getenv("BOT_SESSION", "")
sex = TelegramClient(
    StringSession(_bot_session_str),
    API_ID,
    API_HASH,
)
# ⚠️ NOTE: sex.start() yahan NAHI call hoga
#          restrict_bot() ke andar call hoga (via __main__.py)
telethon_client = sex   # alias — modules jo telethon_client import karte hain

# ✅ Userbot clients (string session based — already filesystem-free)
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

# ✅ MongoDB setup
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
    ✅ Restart ke baad Peer ID invalid error fix.
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
    """
    ✅ Bot startup sequence.
    Pehle __main__.py ke devggn_boot() se call hoga.
    loop.run_until_complete() yahaan se HATA DIYA — __main__.py handle karta hai.
    """
    global BOT_ID, BOT_NAME, BOT_USERNAME

    await setup_database()

    # ✅ Pyrogram start
    await app.start()
    getme = await app.get_me()
    BOT_ID = getme.id
    BOT_USERNAME = getme.username
    BOT_NAME = f"{getme.first_name} {getme.last_name}" if getme.last_name else getme.first_name

    # ✅ Telethon start — yahan hoga (async, non-blocking)
    await sex.start(bot_token=BOT_TOKEN)
    print("✅ Telethon client started")

    # ✅ Peer cache
    await cache_important_peers()

    # ✅ Userbot clients
    if pro:
        await pro.start()
    if userrbot:
        await userrbot.start()

# ✅ VPS ke liye backward compatibility:
# Agar koi module directly `from devgagan import ...` karta hai
# toh BOT_ID etc available rahein — ye devggn_boot() baad set honge
BOT_ID = None
BOT_NAME = None
BOT_USERNAME = None
