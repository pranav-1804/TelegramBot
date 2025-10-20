# python
import asyncio
import csv
import os
from telethon import TelegramClient, events
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputChannel
from telethon.tl.types import ReactionEmoji, ReactionCustomEmoji, ReactionPaid
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=r"Path of your venv file") 

# Please create a .venv file. Add the environment variables over there.
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("session_name")
INVITE_LINK = os.getenv("INVITE_LINK")

# These are the headers for the csv file. 
HEADER = ["chat_id", "message_id", "sender_id", "timestamp", "text",
          "has_media", "media_type", "file_name", "file_size_kb",
          "views", "reactions"]



async def ensure_joined(client, invite_url: str):
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

def serialize_reactions(message):
    if not getattr(message, "reactions", None):
        return ""
    parts = []
    for rc in message.reactions.results:
        label = render_reaction_label(rc.reaction)
        parts.append(f"{label}:{rc.count}")
    return ";".join(parts)

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

def write_csv_row(row_dict):
    # Ensure file exists and has header; then append
    CSV_PATH = Path("Path to csv file")
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_dict)

async def process_message_for_csv(message):
    row = {
        "chat_id": message.chat_id,
        "message_id": message.id,
        "sender_id": getattr(message, "sender_id", None),
        "timestamp": (message.date.isoformat() if getattr(message, "date", None) else None),
        "text": (message.text[:3000] if message.text else ""),
        "has_media": bool(message.media),
        "media_type": type(message.media).__name__ if message.media else "",
        "file_name": getattr(message.file, "name", "") if getattr(message, "file", None) else "",
        "file_size_kb": round(getattr(message.file, "size", 0) / 1024, 2) if getattr(message, "file", None) else "",
        "views": getattr(message, "views", None),
        "reactions": serialize_reactions(message)
    }
    write_csv_row(row)

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    # Resolve and ensure we are re in the channel/group
    target = await ensure_joined(client, INVITE_LINK)

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
        await process_message_for_csv(message)

    if target:
        msgs = []
        async for msg in client.iter_messages(target, limit=4):
            msgs.append(msg)

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
    else:
        print("No INVITE_URL provided. Listening to all chats.")
        @client.on(events.NewMessage())
        async def handle_all(event):
            await process_message(event)

    print("Listening for messages...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
