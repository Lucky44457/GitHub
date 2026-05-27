# ---------------------------------------------------
# File Name: config.py
# Author: Gagan | Upgraded by Claude
# Version: 2.1.0 (Security + Env Fix)
# ---------------------------------------------------

from os import getenv

# ✅ SECURITY FIX: Cookies ab .env se aayenge, hardcoded nahi honge
# Apni .env file me ye variables add karo:
# INSTA_COOKIES=datr=xxx; sessionid=xxx...
# YT_COOKIES=VISITOR_INFO1_LIVE=xxx...

API_ID = int(getenv("API_ID", ""))
API_HASH = getenv("API_HASH", "")
BOT_TOKEN = getenv("BOT_TOKEN", "")
OWNER_ID = list(map(int, getenv("OWNER_ID", "6197171929 5728458734 1838614580 7528647779 8444536859 7346097787 8788088299 8115457075").split()))
MONGO_DB = getenv("MONGO_DB", "")
LOG_GROUP = getenv("LOG_GROUP", "-1003268678671")
CHANNEL_ID = int(getenv("CHANNEL_ID", "-1002439642259"))
FREEMIUM_LIMIT = int(getenv("FREEMIUM_LIMIT", "50"))
PREMIUM_LIMIT = int(getenv("PREMIUM_LIMIT", "150"))
WEBSITE_URL = getenv("WEBSITE_URL", "shrinkforearn.in")
AD_API = getenv("AD_API", "f673ecd2aa19a3013eadbd35bb85cdc61d6e6ed3")
STRING = getenv("STRING", "")
DEFAULT_SESSION = getenv("DEFAUL_SESSION", None)

# ✅ Cookies env se lo — .env file me rakho, config.py me mat
YT_COOKIES = getenv("YT_COOKIES", "")
INSTA_COOKIES = getenv("INSTA_COOKIES", "")
