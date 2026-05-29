# ---------------------------------------------------
# Dockerfile
# Author: Gagan | Fixed by Claude v2.2.0
# Fixes for Heroku/Koyeb compatibility:
#   - CMD: flask run se app.py pe switch kiya
#     (app.py me os.environ.get("PORT") hai — dynamic port pakadta hai)
#   - flask run hardcoded -p 8000 tha — Heroku/Koyeb ka PORT ignore hota tha
#   - WORKDIR pehle set kiya — COPY correctly /app me jaati hai
#   - VPS pe same Dockerfile kaam karega
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

# ✅ FIX: app.py use karo — ye os.environ.get("PORT", 8000) padta hai
#         Heroku/Koyeb dynamically PORT env set karta hai
#         flask run -p 8000 hardcoded tha isliye PORT ignore hota tha
CMD python3 app.py & python3 -m devgagan
