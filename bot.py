import logging
import re
import json
import os
from telethon import TelegramClient, events, Button
from telethon.tl.types import ChannelParticipantsAdmins, ChannelParticipantCreator

# ---------------------------------------------------------
# 1. Credentials (ඔයාගේ විස්තර)
# ---------------------------------------------------------
API_ID = 38027451
API_HASH = "205920d66f76fe9c1d18ba068011f803"
BOT_TOKEN = "7978238021:AAHeZiX2t3ewpse9hWQC49ffE6VIbH3qeWc"

PUBLIC_CHAT_ID = "@sn_and_wormgpt"
PRIVATE_CHAT_ID = -1004369259801 # 👈 ඔයාගේ Private Group එකේ ID එක මෙතනට දාන්න (-100 සමඟ)

client = TelegramClient('my_local_bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# ---------------------------------------------------------
# Database Management (ෆයිල් එකක දත්ත රඳවා තබා ගැනීම)
# ---------------------------------------------------------
DB_FILE = "videos_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db_videos = load_db()

# ---------------------------------------------------------
# 2. /request Command එක හැසිරවීම (Owner ට මැසේජ් යැවීම)
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/request\s+(.+)'))
async def handle_request(event):
    if not event.is_group:
        await event.reply("⚠️ මේ Command එක පාවිච්චි කරන්න පුළුවන් Group එකක් ඇතුළේ විතරයි!")
        return

    movie_name = event.pattern_match.group(1)
    sender = await event.get_sender()
    chat = await event.get_chat()
    
    searching_msg = await event.reply("⏳ ඔයාගේ Request එක Group Owner ට යවමින් පවතී...")

    try:
        owner_id = None
        async for user in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
            if isinstance(user.participant, ChannelParticipantCreator):
                owner_id = user.id
                break
        
        await searching_msg.delete()
        if owner_id:
            msg = (
                f"🎬 **New Movie Request** 🎬\n\n"
                f"👤 **ඉල්ලුම්කරු:** {sender.first_name} (@{sender.username if sender.username else 'None'})\n"
                f"🎥 **චිත්‍රපටය:** {movie_name}\n"
                f"📍 **Group එක:** {chat.title}"
            )
            await client.send_message(owner_id, msg)
            await event.reply("✅ ඔයාගේ චිත්‍රපට ඉල්ලීම සාර්ථකව Group Owner වෙත යවන ලදී!")
        else:
            await event.reply("❌ Group Owner ව සොයාගැනීමට නොහැකි විය.")
            
    except Exception as e:
        print(f"Error finding owner: {e}")
        await searching_msg.delete()
        await event.reply("❌ Error: Owner වෙත පණිවිඩය යැවීමට Bot හට Admin Permissions නොමැත.")

# ---------------------------------------------------------
# 3. Private Group එකට වීඩියෝ එකක් දානකොට Database එකට Save කිරීම
# ---------------------------------------------------------
@client.on(events.NewMessage(chats=PRIVATE_CHAT_ID, func=lambda e: e.video))
async def store_private_video(event):
    text = event.text or event.caption or ""
    if text:
        db_videos.append({'id': event.id, 'text': text})
        save_db(db_videos)
        print(f"📥 Saved to Database: {text}")

# ---------------------------------------------------------
# 4. /quality Command එක හැසිරවීම (Reply කළ විට ක්‍රියාත්මක වේ)
# ---------------------------------------------------------
@client.on(events.NewMessage(chats=PUBLIC_CHAT_ID, pattern=r'(?i)^/quality'))
async def handle_quality_command(event):
    if not event.is_reply:
        await event.reply("⚠️ කරුණාකර වෙනත් චිත්‍රපට වීඩියෝවකට **Reply කරමින්** `/quality` ලෙස Type කරන්න.")
        return

    reply_msg = await event.get_reply_message()
    original_text = reply_msg.text or reply_msg.caption or ""

    if not original_text:
        await event.reply("⚠️ මෙම Reply කළ පණිවිඩයේ නමක් (Caption එකක්) සොයාගත නොහැකි විය.")
        return

    match = re.match(r'^(.*?)\s*-\s*\d{3,4}p', original_text, re.IGNORECASE)
    movie_title = match.group(1).strip() if match else original_text.strip()

    buttons = []
    
    # Database එකෙන් අදාළ නම ඇති වීඩියෝ සෙවීම
    for item in db_videos:
        msg_text = item['text']
        if movie_title.lower() in msg_text.lower():
            q_match = re.search(r'(\d{3,4}p)', msg_text, re.IGNORECASE)
            if q_match:
                quality = q_match.group(1)
                button_data = f"fwd_{item['id']}".encode('utf-8')
                
                btn_label = f"⬇️ {quality} Download"
                if not any(b.text == btn_label for b in buttons):
                    buttons.append(Button.inline(btn_label, data=button_data))

    if buttons:
        formatted_buttons = [[b] for b in buttons]
        await event.reply(f"🍿 **{movie_title}**\nඅදාළ Qualities පහතින් ලබාගන්න (Inbox වෙත පැමිණේ):", buttons=formatted_buttons)
    else:
        await event.reply(f"❌ **{movie_title}** සඳහා වෙනත් Qualities කිසිවක් Database එකෙහි හමු නොවීය.")

# ---------------------------------------------------------
# 5. Button Click කළ විට අදාළ වීඩියෝව Inbox එකට යැවීම
# ---------------------------------------------------------
@client.on(events.CallbackQuery(pattern=b"^fwd_(\d+)"))
async def handle_quality_download(event):
    msg_id = int(event.pattern_match.group(1).decode('utf-8'))
    sender = await event.get_sender()
    
    try:
        await client.forward_messages(sender.id, msg_id, PRIVATE_CHAT_ID)
        await event.answer("✅ වීඩියෝව ඔබගේ Inbox එකට යවන ලදී!", alert=False)
        
    except Exception as e:
        await event.answer("⚠️ කරුණාකර පළමුව Bot ගේ Inbox එකට ගොස් 'Start' ලබා දෙන්න. ඉන්පසු නැවත Click කරන්න!", alert=True)

# ---------------------------------------------------------
# Bot Run කරන්න
# ---------------------------------------------------------
print("🤖 Bot is successfully running on your PC/Railway... (Press Ctrl+C to stop)")
client.run_until_disconnected()
