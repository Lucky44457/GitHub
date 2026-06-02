# ---------------------------------------------------
# Dockerfile
# Author: Gagan | Fixed by Claude v2.3.0
# Fixes:
#   - CMD: Flask aur bot dono properly start hote hain
#   - PORT env variable correctly handle hota hai
#   - uvloop added for performance
# ---------------------------------------------------

FROM python:3.10.4-slim

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        git curl wget bash ffmpeg \
        python3-pip software-properties-common \
        neofetch && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --upgrade pip wheel && \
    pip3 install --no-cache-dir -U -r requirements.txt

COPY . .

EXPOSE 8000

# ✅ FIX: gunicorn use karo Flask ke liye (production-ready)
#         bot alag process me chalta hai
#         Agar gunicorn nahi chahiye toh: python3 app.py & python3 -m devgagan
CMD sh -c "gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers 1 & python3 -m devgagan"
