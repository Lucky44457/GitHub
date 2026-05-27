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
from config import MONGO_DB, WEBSITE_URL, AD_API, LOG_GROUP, ADMIN_USERNAME, UPI_ID
from devgagan.core.mongo import plans_db

# ── MongoDB ──
tclient = AsyncIOMotorClient(MONGO_DB)
tdb = tclient["telegram_bot"]
token = tdb["tokens"]
referral_col = tdb["referrals"]   # referral tracking
daily_col    = tdb["daily_usage"]  # daily token limit tracking

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


async def has_used_token_today(user_id: int) -> bool:
    """Check: kya user ne aaj token already use kiya?"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rec = await daily_col.find_one({"user_id": user_id, "date": today})
    return rec is not None


async def mark_token_used_today(user_id: int):
    """Aaj ka token use mark karo (1 per day limit)"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    tomorrow = datetime.utcnow().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    await daily_col.update_one(
        {"user_id": user_id, "date": today},
        {"$set": {
            "user_id": user_id,
            "date": today,
            "expires_at": tomorrow   # midnight pe auto-delete (TTL index)
        }},
        upsert=True
    )


async def setup_daily_ttl_index():
    """Daily collection ke liye TTL index — midnight pe auto clean"""
    await daily_col.create_index("expires_at", expireAfterSeconds=0)

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
            [InlineKeyboardButton("💎 Get Premium", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("❓ Help", url=f"https://t.me/{ADMIN_USERNAME}")]
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
        # ✅ Daily limit check: ek din me sirf ek baar
        if await has_used_token_today(user_id):
            del Param[user_id]
            # Kitna time bacha hai midnight tak
            now = datetime.utcnow()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            hrs_left = int((midnight - now).seconds / 3600)
            mins_left = int(((midnight - now).seconds % 3600) / 60)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Upgrade Premium", callback_data="upgrade")],
                [InlineKeyboardButton("📬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
            ])
            await message.reply(
                f"⏳ **Daily limit reached!**\n\n"
                f"You already used your free token today.\n"
                f"⏰ Next token in **{hrs_left}h {mins_left}m**\n\n"
                f"💎 Upgrade to premium for unlimited access!",
                reply_markup=btn
            )
            return
        # ✅ Token verify: 12 hr premium do
        await token.insert_one({
            "user_id": user_id,
            "param": param,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=12),
        })
        await give_token_premium(user_id, hours=12)
        await mark_token_used_today(user_id)   # daily limit mark karo
        del Param[user_id]
        btn_ok = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Upgrade for More", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await message.reply(
            "✅ **Verified! You got 12 hours of premium access.**\n\n"
            "🎯 Enjoy /batch and all features!\n"
            "📋 Use /myplan to check your plan.\n\n"
            "💡 Need more? Upgrade to premium!",
            reply_markup=btn_ok
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

    # ✅ Daily limit check in /token command bhi
    if await has_used_token_today(user_id):
        now = datetime.utcnow()
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        hrs_left = int((midnight - now).seconds / 3600)
        mins_left = int(((midnight - now).seconds % 3600) / 60)
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Upgrade Premium", callback_data="upgrade")],
            [InlineKeyboardButton("📬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await message.reply(
            f"⏳ **Daily limit reached!**\n\n"
            f"You already used your free token today.\n"
            f"⏰ Next token in **{hrs_left}h {mins_left}m**\n\n"
            f"💎 Upgrade for unlimited access!",
            reply_markup=btn
        )
        return

    param = await generate_random_param()
    Param[user_id] = param
    deep_link = f"https://t.me/{client.me.username}?start={param}"
    shortened_url = await get_shortened_url(deep_link)

    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 Verify Token", url=shortened_url)]
    ])
    await message.reply(
        "🔓 **Verify your free token below:**\n\n"
        "**What you'll get:**\n"
        "⏰  12 hours premium access\n"
        "📦  150 files/batch\n"
        "⚡  All features unlocked\n\n"
        "⚠️  1 token per day — use it wisely!\n\n"
        "Complete the ad, then you will be redirected back automatically.",
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




# ── /upgrade command ──
@app.on_message(filters.command("upgrade"))
async def upgrade_handler(client, message):
    await show_upgrade_plans(message)


@app.on_callback_query(filters.regex("upgrade"))
async def upgrade_callback(client, callback_query):
    await callback_query.answer()
    await show_upgrade_plans(callback_query.message)


async def show_upgrade_plans(message):
    from config import UPI_ID, ADMIN_USERNAME
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton("🏠 Back to Start", callback_data="start")]
    ])
    await message.reply(
        f"💎 **Upgrade to Premium** 💎\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"🆓 **Free Plan**\n"
        f"• Token verify karke 12 hrs premium\n"
        f"• 150 files/batch\n"
        f"• 1 token per day\n\n"

        f"🥉 **Starter — 7 Days**\n"
        f"💵 **₹49** \n"
        f"• 150 files/batch\n"
        f"• No token needed\n"
        f"• Priority support\n\n"

        f"🥈 **Standard — 30 Days** ⭐ Popular\n"
        f"💵 **₹149** (₹5/day)\n"
        f"• 150 files/batch\n"
        f"• No token needed\n"
        f"• Priority support\n\n"

        f"🥇 **Pro — 90 Days**\n"
        f"💵 **₹399** (₹4.4/day)\n"
        f"• 150 files/batch\n"
        f"• No token needed\n"
        f"• VIP support\n\n"

        f"👑 **Lifetime**\n"
        f"💵 **₹999** (Ek baar, hamesha ke liye)\n"
        f"• Sab kuch unlimited\n"
        f"• VIP support\n\n"

        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 **UPI:** `{UPI_ID}`\n\n"
        f"📌 **Payment ke baad:**\n"
        f"1️⃣ Screenshot bhejo admin ko\n"
        f"2️⃣ Admin 5 min me activate karega\n\n"
        f"❤️ Thank you for supporting!",
        reply_markup=btn
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
                    f"Contact: @DARKEND_X"
                )
            except Exception:
                pass
