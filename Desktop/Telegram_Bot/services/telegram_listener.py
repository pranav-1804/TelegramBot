import asyncio
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

from telethon import TelegramClient, events
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Channel, ReactionEmoji, ReactionCustomEmoji, ReactionPaid

from transformers import pipeline

# ======================================================
# ENV SETUP
# ======================================================

load_dotenv(find_dotenv())

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION")
INVITE_LINK = os.getenv("INVITE_LINK")
LIMIT = os.getenv("LIMIT");

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
OUTPUT_DIR = DATA_DIR / "output/telegram"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

META_DIR = OUTPUT_DIR / ".meta"
META_DIR.mkdir(parents=True, exist_ok=True)

sentiment_analyzer = pipeline("sentiment-analysis")

# ======================================================
# RUNTIME STATE (PER CHANNEL)
# ======================================================

CHANNEL_FILE_CONTEXT = {}  # chat_id -> {txt, json}

# ======================================================
# UTILITIES
# ======================================================

def is_empty(val):
    return val is None or not str(val).strip()

def safe_channel_name(chat):
    return (chat.username or chat.title or "telegram").replace(" ", "_")

def get_channel_file_paths(chat):
    """
    Create deterministic filenames ONCE per channel:
    <name>_<id>_<timestamp>.txt
    <name>_<id>_<timestamp>.txt.json
    """
    if chat.id in CHANNEL_FILE_CONTEXT:
        return CHANNEL_FILE_CONTEXT[chat.id]
    base_name = f"{safe_channel_name(chat)}_{chat.id}"

    txt_path = OUTPUT_DIR / f"{base_name}.txt"
    json_path = META_DIR / f"{base_name}.txt.json"

    CHANNEL_FILE_CONTEXT[chat.id] = {
        "txt": txt_path,
        "json": json_path
    }

    return CHANNEL_FILE_CONTEXT[chat.id]

def render_reaction_label(r):
    if isinstance(r, ReactionEmoji):
        return r.emoticon
    if isinstance(r, ReactionCustomEmoji):
        return f"custom_emoji:{r.document_id}"
    if isinstance(r, ReactionPaid):
        return "paid_reaction"
    return str(r)

def safe_serialize_reactions(message):
    r = getattr(message, "reactions", None)
    if not r or not getattr(r, "results", None):
        return ""
    return ";".join(
        f"{render_reaction_label(rc.reaction)}:{rc.count}"
        for rc in r.results
    )

# ======================================================
# FILE WRITERS
# ======================================================

def append_text_to_channel(message, chat):
    if not message.text or not message.text.strip():
        return

    paths = get_channel_file_paths(chat)
    txt_path = paths["txt"]

    with open(txt_path, "a", encoding="utf-8") as f:
        f.write(
            "\n----------------------------------------\n"
            f"Message ID : {message.id}\n"
            f"Timestamp  : {message.date.isoformat() if message.date else ''}\n"
            f"Sender ID  : {message.sender_id}\n\n"
            f"{message.text.strip()}\n"
        )

def append_json_to_channel(message_entry, chat):
    paths = get_channel_file_paths(chat)
    json_path = paths["json"]

    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {
            "title": f"Telegram {chat.title}",
            "backlink": str(paths["txt"]),
            "language": "en",
            "classification": [chat.username or chat.title],
            "properties": {
                "chat_id": chat.id,
                "messages": []
            }
        }

    data["properties"]["messages"].append(message_entry)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ======================================================
# MESSAGE PROCESSING
# ======================================================

async def process_message_for_storage(message):
    chat = await message.get_chat()

    sentiment = await asyncio.to_thread(
        sentiment_analyzer,
        message.text or ""
    )

    message_entry = {
        "message_id": message.id,
        "sender_id": message.sender_id,
        "timestamp": message.date.isoformat() if message.date else None,
        "has_media": bool(message.media),
        "media_type": type(message.media).__name__ if message.media else "",
        "file_name": message.file.name if getattr(message, "file", None) else None,
        "file_size_kb": (
            round(message.file.size / 1024, 2)
            if getattr(message, "file", None)
            else None
        ),
        "views": getattr(message, "views", None),
        "reactions": safe_serialize_reactions(message),
        "sentiment": sentiment[0]["label"] if sentiment else None
    }

    append_text_to_channel(message, chat)
    append_json_to_channel(message_entry, chat)

# ======================================================
# CHANNEL HANDLING
# ======================================================

async def list_joined_channels(client):
    channels = []
    async for dialog in client.iter_dialogs():
        if isinstance(dialog.entity, Channel):
            channels.append(dialog.entity)
    return channels

async def ensure_joined(client, invite_url):
    if is_empty(invite_url):
        return None

    if "/+" in invite_url:
        invite_hash = invite_url.rsplit("/", 1)[-1].replace("+", "")
        try:
            res = await client(ImportChatInviteRequest(invite_hash))
            return res.chats[0]
        except UserAlreadyParticipantError:
            return await client.get_entity(invite_url)
    else:
        entity = await client.get_entity(invite_url)
        try:
            await client(JoinChannelRequest(entity))
        except Exception:
            pass
        return entity

# ======================================================
# MESSAGE STREAMS
# ======================================================

async def process_single_channel(client, target, limit):

    print("Processing Historical Messages")
    history = [m async for m in client.iter_messages(target, limit=limit)]
    for m in reversed(history):
        await process_message_for_storage(m)

    print("Messages fetched and stored in file!!")

    print("Listening for real time messages")
    @client.on(events.NewMessage(chats=target))
    async def on_new(event):
        await process_message_for_storage(event.message)

    @client.on(events.MessageEdited(chats=target))
    async def on_edit(event):
        await process_message_for_storage(event.message)

async def process_all_channels(client, limit):
    print("Fetching all the channels the bot has joined to ")
    channels = await list_joined_channels(client)

    for ch in channels:
        try:
            print("Processing Historical Messages")
            history = [m async for m in client.iter_messages(ch, limit=limit)]
            for m in reversed(history):
                await process_message_for_storage(m)
        except Exception as e:
            print(f"History fetch failed for {ch.title}: {e}")
    
    print("Messages fetched and stored in file!!")

    print("Listening for real time messages")

    @client.on(events.NewMessage())
    async def on_new(event):
        await process_message_for_storage(event.message)

    @client.on(events.MessageEdited())
    async def on_edit(event):
        await process_message_for_storage(event.message)

# ======================================================
# MAIN
# ======================================================

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    print("Initialized Telegram Client")
    print("------------------------------------------")

    print("Trying to join the specified channel if mentioned any!!")
    target = await ensure_joined(client, INVITE_LINK)

    if target:
        print(f"Listening to channel: {target.title}")
        await process_single_channel(client, target, LIMIT)
    else:
        print("Listening to all joined channels")
        await process_all_channels(client, LIMIT)

    print("Listening for messages...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
