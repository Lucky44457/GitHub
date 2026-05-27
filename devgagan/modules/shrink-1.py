# ---------------------------------------------------
# File Name: shrink.py
# Author: Gagan | Upgraded by Claude v2.1.1
# Changes:
#   - Token verify ke baad 12 hr premium milega (3 hr nahi)
#   - Referral system: /refer → dono ko 1 day premium
#   - Premium expiry reminder: 3 din pehle notify
# ---------------------------------------------------

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import random, requests, string, aiohttp
from devgagan import app
from devgagan.core.func import *
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB, WEBSITE_URL, AD_API, LOG_GROUP
from devgagan.core.mongo import plans_db

# ── MongoDB ──
tclient = AsyncIOMotorClient(MONGO_DB)
tdb = tclient["telegram_bot"]
token = tdb["tokens"]
referral_col = tdb["referrals"]  # referral tracking

async def create_ttl_index():
    await token.create_index("expires_at", expireAfterSeconds=0)

Param = {}

# ── Utilities ──
async def generate_random_param(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def get_shortened_url(deep_link):
    api_url = f"https://{WEBSITE_URL}/api"
    params = {"api": AD_API, "url": deep_link, "format": "json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "success":
                        return data.get("shortenedUrl")
    except Exception:
        pass
    return deep_link

async def is_user_verified(user_id):
    """Token verified hai ya nahi check karo"""
    session = await token.find_one({"user_id": user_id})
    return session is not None

async def give_token_premium(user_id, hours=12):
    """Token verify hone ke baad N hours ka premium do"""
    expiry = datetime.utcnow() + timedelta(hours=hours)
    await plans_db.add_premium(user_id, expiry)

# ── /start handler ──
@app.on_message(filters.command("start"))
async def token_handler(client, message):
    join = await subscribe(client, message)
    if join == 1:
        return

    user_id = message.chat.id

    if len(message.command) <= 1:
        image_url = "https://i.postimg.cc/tCJ0M27D/IMG-20250823-145001-279.jpg"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url="https://t.me/PdfsHubbb")],
            [InlineKeyboardButton("💎 Get Premium", url="https://t.me/DarkEnd7")],
            [InlineKeyboardButton("❓ Help", callback_data="https://t.me/DarkEnd7")]
        ])
        await message.reply_photo(
            image_url,
            caption=(
                f"Hey {message.from_user.first_name}! 👋\n\n"
                "🚀 **What I Can Do:**\n"
                "✨ Save posts from restricted channels & groups\n"
                "✨ Download media from YT, Insta, and more\n"
                "✨ For private channels, use /login\n"
                "✨ Type /help for all commands\n\n"
                "💎 **Premium Features:**\n"
                "🔹 Use /token to get **12 hours free premium**\n"
                "🔹 Upgrade with /upgrade for unlimited access\n"
                "🔹 Faster speed, priority support 🚀\n\n"
                "✅ Send me any post link to start saving!"
            ),
            reply_markup=keyboard
        )
        return

    param = message.command[1]
    freecheck = await chk_user(message, user_id)

    # ── Referral link handle ──
    if param.startswith("ref_"):
        referrer_id = int(param.split("ref_")[1])
        await handle_referral(user_id, referrer_id, message)
        return

    # ── Token verify ──
    if freecheck != 1:
        await message.reply("You are a premium user, no need of token 😉")
        return

    if param and user_id in Param and Param[user_id] == param:
        # ✅ Token verify: 12 hr premium do
        await token.insert_one({
            "user_id": user_id,
            "param": param,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=12),
        })
        await give_token_premium(user_id, hours=12)
        del Param[user_id]
        await message.reply(
            "✅ **Verified! You got 12 hours of premium access.**\n\n"
            "Enjoy /batch and all features!\n"
            "Use /myplan to check your plan."
        )
    else:
        await message.reply("❌ Invalid or expired verification link. Please generate a new /token.")


# ── /token handler ──
@app.on_message(filters.command("token"))
async def smart_handler(client, message):
    user_id = message.chat.id
    freecheck = await chk_user(message, user_id)

    if freecheck != 1:
        await message.reply("You are a premium user, no need of token 😉")
        return

    if await is_user_verified(user_id):
        data = await plans_db.check_premium(user_id)
        if data and data.get("expire_date"):
            import pytz
            expiry = data["expire_date"].astimezone(pytz.timezone("Asia/Kolkata"))
            expiry_str = expiry.strftime("%d-%m-%Y %I:%M %p IST")
            await message.reply(f"✅ Your 12-hour premium is active!\n\n⌛️ Expires: **{expiry_str}**")
        else:
            await message.reply("✅ Your free session is already active!")
        return

    param = await generate_random_param()
    Param[user_id] = param
    deep_link = f"https://t.me/{client.me.username}?start={param}"
    shortened_url = await get_shortened_url(deep_link)

    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 Verify Token", url=shortened_url)]
    ])
    await message.reply(
        "Click below to verify your free token:\n\n"
        "**What you'll get:**\n"
        "⏰ 12 hours premium access\n"
        "📦 Batch limit: 150 messages\n"
        "⚡ All features unlocked\n\n"
        "> Complete the ad, then you'll be redirected back automatically.",
        reply_markup=button
    )


# ── Referral System ──
async def handle_referral(new_user_id, referrer_id, message):
    """Referral handle karo — dono ko 1 day premium"""
    if new_user_id == referrer_id:
        await message.reply("❌ Apne aap ko refer nahi kar sakte!")
        return

    # Check: kya ye user pehle se referred hai?
    existing = await referral_col.find_one({"referred_user": new_user_id})
    if existing:
        await message.reply("✅ Welcome! You've already used a referral link before.")
        return

    # Dono ko 1 din premium do
    expiry = datetime.utcnow() + timedelta(days=1)
    await plans_db.add_premium(new_user_id, expiry)
    await plans_db.add_premium(referrer_id, expiry)

    # Track karo
    await referral_col.insert_one({
        "referred_user": new_user_id,
        "referrer": referrer_id,
        "date": datetime.utcnow()
    })

    # New user ko notify
    await message.reply(
        "🎉 **Welcome!**\n\n"
        "You used a referral link — **1 day premium** added to your account!\n"
        "Use /myplan to check."
    )

    # Referrer ko notify
    try:
        await app.send_message(
            referrer_id,
            "🎉 **Someone joined using your referral link!**\n\n"
            "**1 day premium** added to your account as reward!\n"
            "Use /myplan to check."
        )
    except Exception:
        pass


@app.on_message(filters.command("refer"))
async def refer_handler(client, message):
    """User ka referral link generate karo"""
    user_id = message.chat.id
    ref_link = f"https://t.me/{client.me.username}?start=ref_{user_id}"

    # Count kitne logo ne refer kiya
    count = await referral_col.count_documents({"referrer": user_id})

    await message.reply(
        f"🔗 **Your Referral Link:**\n`{ref_link}`\n\n"
        f"👥 Total referrals: **{count}**\n\n"
        "**How it works:**\n"
        "• Share your link\n"
        "• When someone joins → both get **1 day premium**\n"
        "• No limit on referrals!"
    )


# ── Premium Expiry Reminder (call this from __main__.py scheduler) ──
async def send_expiry_reminders():
    """3 din pehle expiry reminder bhejo"""
    import pytz
    now = datetime.utcnow()
    reminder_threshold = now + timedelta(days=3)

    async for data in plans_db.db.find():
        user_id = data["_id"]
        expire_date = data.get("expire_date")
        if not expire_date:
            continue

        time_left = expire_date - now
        # 3 din se kam bacha hai aur 2 din se zyada (takhi baar baar na bheje)
        if timedelta(days=2) < time_left <= timedelta(days=3):
            try:
                expire_str = expire_date.astimezone(
                    pytz.timezone("Asia/Kolkata")
                ).strftime("%d-%m-%Y %I:%M %p IST")
                await app.send_message(
                    user_id,
                    f"⚠️ **Premium Expiry Reminder**\n\n"
                    f"Your premium expires on **{expire_str}**\n\n"
                    f"Renew now to keep your access!\n"
                    f"Contact: @DarkEnd7"
                )
            except Exception:
                pass
