# ---------------------------------------------------
# File Name: queue_db.py
# Description: Batch task queue — restart ke baad resume support
# Author: Upgraded by Claude
# Version: 2.1.0
# ---------------------------------------------------

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB
import datetime

mongo = AsyncIOMotorClient(MONGO_DB)
_db = mongo["bot_queue"]
queue_col = _db["tasks"]


async def save_task(user_id: int, start_link: str, start_id: int, total: int, processed: int = 0):
    """Batch task MongoDB me save karo"""
    await queue_col.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "start_link": start_link,
            "start_id": start_id,
            "total": total,
            "processed": processed,
            "status": "pending",
            "updated_at": datetime.datetime.utcnow()
        }},
        upsert=True
    )


async def update_progress(user_id: int, processed: int):
    """Processed count update karo"""
    await queue_col.update_one(
        {"user_id": user_id},
        {"$set": {"processed": processed, "updated_at": datetime.datetime.utcnow()}}
    )


async def mark_done(user_id: int):
    """Task complete mark karo"""
    await queue_col.update_one(
        {"user_id": user_id},
        {"$set": {"status": "done", "updated_at": datetime.datetime.utcnow()}}
    )


async def get_pending_task(user_id: int):
    """User ka pending task lo"""
    return await queue_col.find_one({"user_id": user_id, "status": "pending"})


async def get_all_pending():
    """Restart ke baad saare pending tasks lo"""
    return await queue_col.find({"status": "pending"}).to_list(length=200)


async def delete_task(user_id: int):
    """Task delete karo"""
    await queue_col.delete_one({"user_id": user_id})
