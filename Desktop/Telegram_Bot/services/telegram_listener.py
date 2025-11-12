# python
import asyncio
import csv
import os
import json

from pathlib import Path
from dotenv import load_dotenv,find_dotenv
from datetime import datetime

from telethon import TelegramClient, events
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputChannel, Channel, ReactionEmoji, ReactionCustomEmoji, ReactionPaid

from transformers import pipeline

load_dotenv(find_dotenv())

# Please create a .env file. Add the environment variables over there. And never the env file on github or gitlab.
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION")
INVITE_LINK = os.getenv("INVITE_LINK")


DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
JSON_PATH = DATA_DIR / f"messages_{timestamp}.json"

sentiment_analyzer = pipeline("sentiment-analysis")

# These are the headers for the Json file. 
HEADER = ["chat_id", "message_id", "sender_id", "timestamp", "text",
          "has_media", "media_type", "file_name", "file_size_kb",
          "views", "reactions", "sentiment"]

async def list_joined_channels(client):
    channels = []
    async for dialog in client.iter_dialogs():
        ent = dialog.entity
        if isinstance(ent, Channel):
            channels.append(ent)
    return channels


async def process_messages_for_all_channels(client, process_message, limit):
    channels = await list_joined_channels(client)
    print(f"No INVITE_URL provided. Listening to all chats. Found {len(channels)} channels.")

    for ch in channels:
        try:
            # Pull last N messages for this channel
            msgs = [m async for m in client.iter_messages(ch, limit=limit)]
            for m in reversed(msgs):
                await process_message(m)
        except Exception as e:
            print(f"Failed to fetch history for {getattr(ch, 'title', ch.id)}: {e}")

    # Register one global handler for new messages (all chats)
    @client.on(events.NewMessage())
    async def handle_all(event):
        await process_message(event.message)

    @client.on(events.MessageEdited())
    async def handle_edit(event):
        message = event.message
        await process_message(message)  

    return channels  # optional, if you need the list


async def process_messages_for_one_channel(client, process_message, target, limit):

        msgs = [msg async for msg in client.iter_messages(target, limit=limit)]
        for m in reversed(msgs):
            await process_message(m)

        @client.on(events.NewMessage(chats=target))
        async def handle_new(event):
             message = event.message
             await process_message(message)
            
        @client.on(events.MessageEdited(chats=target))
        async def handle_edit(event):
            message = event.message
            await process_message(message)


def write_csv_row(row_dict):
    # Ensure file exists and has header; then append
    CSV_PATH = Path(r"{CSV_FILE_PATH}")
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_dict)


def safe_serialize_reactions(message):
    r = getattr(message, "reactions", None)
    if not r or not getattr(r, "results", None):
        return ""
    parts = []
    for rc in r.results:
        label = render_reaction_label(rc.reaction)
        parts.append(f"{label}:{rc.count}")
    return ";".join(parts)

def write_json_entry_per_post(entry, message_id, sender_id):
    """Create a separate JSON file for each post."""
    try:
        JSON_PATH = DATA_DIR / f"output/post_{message_id}_{sender_id}.json"
        JSON_PATH.parent.mkdir(parents=True, exist_ok=True)  # <-- ADD THIS LINE ✅
        existing_data = []
        if JSON_PATH.exists():
            with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = []

        existing_data.append(entry)
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
        print(f"JSON file saved: {JSON_PATH}")
    except Exception as e:
        print(f"JSON write error: {e}")
        print(f"Error writing JSON for post {message_id}: {e}")

def write_text_file_per_post(message,sender_id):
    """Save only the text of a message to a separate .txt file."""

    try:
        FILE_PATH = DATA_DIR / f"output/post_{message.id}_{sender_id}.txt"
        FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        text_content = message.text or ""
        if not text_content.strip():
            return  # skip empty or non-text messages
        with open(FILE_PATH, "w", encoding="utf-8-sig") as f:
            f.write(text_content.strip())

        print(f"Text file saved: {FILE_PATH}")
    except Exception as e:
        print(f"Error writing text file for post {message.id}: {e}")

async def process_message_for_json(message):
    sentiment = await asyncio.to_thread(sentiment_analyzer, message.text or "")
    sender_id = getattr(message, "sender_id", None)
    row = {
        "chat_id": message.chat_id,
        "message_id": message.id,
        "sender_id": sender_id,
        "timestamp": message.date.isoformat() if getattr(message, "date", None) else None,
        "text": (message.text[:3000] if message.text else ""),
        "has_media": bool(message.media),
        "media_type": type(message.media).__name__ if message.media else "",
        "file_name": getattr(message.file, "name", "") if getattr(message, "file", None) else "",
        "file_size_kb": round(getattr(message.file, "size", 0) / 1024, 2) if getattr(message, "file", None) else "",
        "views": getattr(message, "views", None),
        "reactions": safe_serialize_reactions(message),
        "sentiment": sentiment[0]["label"] if sentiment else ""
    }
    try:
        #write_csv_row(row)
        write_json_entry_per_post(row, message.id, sender_id)
        write_text_file_per_post(message,sender_id)
    except Exception as e:
        print(f"CSV write error: {e}")

def render_reaction_label(r):
        if isinstance(r, ReactionEmoji):
            return r.emoticon  # e.g., "👍"
        if isinstance(r, ReactionCustomEmoji):
            # We can later resolve document_id to a sticker/emoji file if needed
            return f"custom_emoji:{r.document_id}"
        if isinstance(r, ReactionPaid):
            # Paid reactions don’t have an emoji string
            return "paid_reaction"
        # Fallback for future types
        return str(r)

def _is_empty(s: str) -> bool:
    return s is None or not str(s).strip()

async def ensure_joined(client, invite_url: str):

    if _is_empty(invite_url):
        return None
     
    # Handles both invite hash links and public @ links
    if "/+" in invite_url:
        # Private invite hash style: https://t.me/+<hash>
        invite_hash = invite_url.rsplit("/", 1)[-1].replace("+", "")
        try:
            res = await client(ImportChatInviteRequest(invite_hash))
            entity = res.chats[0] if res.chats else res.updates[0].chat
        except UserAlreadyParticipantError:
            entity = await client.get_entity(invite_url)
    else:
        # Public link or t.me/username
        entity = await client.get_entity(invite_url)
        # If it's a channel and we’re not a participant, try joining
        try:
            await client(JoinChannelRequest(entity))
        except Exception:
            pass
    return entity

async def process_message(message):
        
        # 1. Basic Info
        print("--- New Message ---")
        print(f"Message ID: {message.id}")
        print(f"Timestamp: {message.date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 2. Text Content
        if message.text:
            print(f"Text: {message.text[:100]}...") # Trimmed to first 100 chars
            
        # 3. Media/File Info
        if message.media:
            print("Media detected.")
            if message.file:
                print(f"  - File Name: {message.file.name}")
                print(f"  - File Size: {round(message.file.size / 1024, 2)} KB")

            # Example: Download media (uncomment if needed)
            # await client.download_media(message.media, file="downloads/")

        # 4. Reaction Info
        if message.reactions:
            print("Reactions:")
            for reaction_count in message.reactions.results:
                label = render_reaction_label(reaction_count.reaction)
                print(f"    - {label}: {reaction_count.count}")

        print("------\n")
        await process_message_for_json(message)
        
async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    # Resolve and ensure we are re in the channel/group
    target = await ensure_joined(client, INVITE_LINK)

    if target:
        print("Listening to single channel ")
        await process_messages_for_one_channel(client, process_message, target, limit= 5)
        
    else:
        print("No INVITE_URL provided. Listening to all chats.")
        await process_messages_for_all_channels(client, process_message, limit=5)

    print("Listening for messages...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
