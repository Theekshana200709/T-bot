import logging
import re
import json
import os
from telethon import TelegramClient, events, Button
from telethon.tl.types import ChannelParticipantsAdmins, ChannelParticipantCreator

# ---------------------------------------------------------
# 1. Credentials
# ---------------------------------------------------------
API_ID = 38027451
API_HASH = "205920d66f76fe9c1d18ba068011f803"
BOT_TOKEN = "7978238021:AAHeZiX2t3ewpse9hWQC49ffE6VIbH3qeWc"

PUBLIC_CHAT_ID = "@moviesdotlk"
PRIVATE_CHAT_ID = "@moviesprivatelk" # ඔයාගේ Database Channel / Group එක

client = TelegramClient('my_local_bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
logging.basicConfig(format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# ---------------------------------------------------------
# Database Management (ෆයිල් එකක දත්ත රඳවා තබා ගැනීම - API Error මඟහරවා ගැනීමට)
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
# 2. Private Channel එකට වීඩියෝවක් දානකොටම Database එකට Save කිරීම
# ---------------------------------------------------------
@client.on(events.NewMessage(chats=PRIVATE_CHAT_ID, func=lambda e: e.video or e.document))
async def store_private_video(event):
    text = event.text or event.caption or ""
    if text:
        # එකම වීඩියෝව දෙපාරක් Save වීම වැළැක්වීම
        if not any(item['id'] == event.id for item in db_videos):
            db_videos.append({'id': event.id, 'text': text})
            save_db(db_videos)
            print(f"📥 Saved to Database: {text}")


# ---------------------------------------------------------
# 3. /start, /help, hi, hello සඳහා Welcome Message එක
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^(/start|/help|hi|hello)$'))
async def handle_start_help(event):
    sender = await event.get_sender()
    first_name = sender.first_name if sender else "යාළුවා"
    
    welcome_text = (
        f"👋 ආයුබෝවන් **{first_name}**!\n\n"
        f"🤖 මම තමයි Movies Bot. මට පුළුවන් ඔයාට අවශ්‍ය Movies වල විවිධ Qualities (480p, 720p, 1080p) හොයලා ඔයාගේ Inbox එකටම එවන්න.\n\n"
        f"🛠️ **මාව භාවිතා කරන ආකාරය:**\n"
        f"1️⃣ Group එකේ තියෙන චිත්‍රපටයක වීඩියෝවකට / පෝස්ට් එකකට **Reply** කරමින් `/quality` ලෙස Type කර යවන්න.\n"
        f"2️⃣ එවිට මම අදාළ චිත්‍රපටයේ ඇති Qualities පෙන්වමින් Buttons ලබා දෙන්නම්.\n"
        f"3️⃣ ඔබට අවශ්‍ය Quality එක මත Click කළ විට එය ඔබේ Inbox එකට එවනු ලැබේ.\n\n"
        f"🎬 **Movie එකක් ඉල්ලීමට:** `/request [චිත්‍රපටයේ නම]` ලෙස Group එකේ Type කරන්න.\n\n"
        f"⚠️ **වැදගත්:** වීඩියෝ ලබා ගැනීමට ප්‍රථම පහත බොත්තම Click කර මාගේ Inbox වෙත ගොස් 'Start' ලබා දෙන්න!"
    )
    
    me = await client.get_me()
    bot_username = me.username
    
    buttons = [
        [Button.url("🚀 Start Bot in Inbox", f"https://t.me/{bot_username}?start=1")]
    ]
    
    await event.reply(welcome_text, buttons=buttons)


# ---------------------------------------------------------
# 4. අලුතින් Group එකට Join වෙන සාමාජිකයන්ව පිළිගැනීම
# ---------------------------------------------------------
@client.on(events.ChatAction(chats=PUBLIC_CHAT_ID))
async def handle_new_member(event):
    if event.user_joined or event.user_added:
        users = await event.get_users()
        for user in users:
            welcome_msg = (
                f"🎉 ආයුබෝවන් [{user.first_name}](tg://user?id={user.id})!\n\n"
                f"🎬 අපගේ Group එකට සාදරයෙන් පිළිගනිමු. ඔබට අවශ්‍ය චිත්‍රපට පහසුවෙන් ලබා ගැනීමට ඕනෑම චිත්‍රපටයකට Reply කරමින් `/quality` ලෙස Type කරන්න."
            )
            await event.reply(welcome_msg)


# ---------------------------------------------------------
# 5. Bot ගේ තත්ත්වය පරීක්ෂා කිරීම (/ping)
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/ping$'))
async def ping_command(event):
    await event.reply("🏓 **Pong!**\n✅ Bot ඉතා හොඳින් ක්‍රියාකාරීව පවතී.")


# ---------------------------------------------------------
# 6. /request Command එක (චිත්‍රපට ඉල්ලීම් Owner වෙත යැවීම)
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
# 7. /quality Command එක (Database එක හරහා API Error රහිතව ක්‍රියාත්මක වේ)
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

    status_msg = await event.reply(f"🔎 **{movie_title}** සඳහා පවතින Qualities සොයමින් පවතී...")

    buttons = []
    seen_qualities = set()

    try:
        # History ස්කෑන් කිරීම වෙනුවට local Database (JSON) එකෙන් සෙවීම
        for item in db_videos:
            msg_text = item['text']
            if movie_title.lower() in msg_text.lower():
                q_match = re.search(r'(\d{3,4}p)', msg_text, re.IGNORECASE)
                if q_match:
                    quality = q_match.group(1).lower()
                    
                    if quality not in seen_qualities:
                        seen_qualities.add(quality)
                        button_data = f"fwd_{item['id']}".encode('utf-8')
                        btn_label = f"⬇️ {quality.upper()} Download"
                        buttons.append(Button.inline(btn_label, data=button_data))

        if buttons:
            formatted_buttons = [[b] for b in buttons]
            await status_msg.edit(
                f"🍿 **{movie_title}**\nඅදාළ Qualities පහතින් ලබාගන්න (Inbox වෙත පැමිණේ):", 
                buttons=formatted_buttons
            )
        else:
            await status_msg.edit(f"❌ **{movie_title}** සඳහා වෙනත් Qualities කිසිවක් Database එකේ හමු නොවීය.")

    except Exception as e:
        await status_msg.edit(f"❌ දෝෂයක් ආවා: {e}")


# ---------------------------------------------------------
# 8. Button Click කළ විට Inbox එකට Forward කිරීම
# ---------------------------------------------------------
@client.on(events.CallbackQuery(pattern=b"^fwd_(\d+)"))
async def handle_quality_download(event):
    msg_id = int(event.pattern_match.group(1).decode('utf-8'))
    sender = await event.get_sender()
    
    try:
        await client.forward_messages(sender.id, msg_id, PRIVATE_CHAT_ID)
        await event.answer("✅ වීඩියෝව ඔබගේ Inbox එකට යවන ලදී!", alert=False)
    except Exception as e:
        await event.answer("⚠️ කරුණාකර පළමුව Bot ගේ Inbox (PM) එකට ගොස් 'Start' ලබා දෙන්න!", alert=True)

# Run Bot
print("🤖 Bot is successfully running...")
client.run_until_disconnected()
