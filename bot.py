import logging
import re
from telethon import TelegramClient, events, Button

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

# මේකෙන් Private Group එකට දාන වීඩියෝස් වල විස්තර Bot ගේ මතකයේ තබා ගනී (Memory Storage)
db_videos = []

# ---------------------------------------------------------
# 2. Private Group එකට වීඩියෝ එකක් දානකොටම Bot එය මතකයේ තබා ගැනීම
# ---------------------------------------------------------
@client.on(events.NewMessage(chats=PRIVATE_CHAT_ID, func=lambda e: e.video))
async def store_private_video(event):
    text = event.text or event.caption or ""
    if text:
        # වීඩියෝවේ ID එක සහ Text එක Memory එකට Save කරයි
        db_videos.append({'id': event.id, 'text': text})
        print(f"📥 Saved to memory: {text}")

# ---------------------------------------------------------
# 3. /quality Command එක හැසිරවීම (Reply කළ විට ක්‍රියාත්මක වේ)
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

    # නමෙන් Quality එක ඉවත් කර චිත්‍රපටයේ නම පමණක් ලබා ගැනීම
    match = re.match(r'^(.*?)\s*-\s*\d{3,4}p', original_text, re.IGNORECASE)
    movie_title = match.group(1).strip() if match else original_text.strip()

    buttons = []
    
    # Bot ගේ මතකයෙන් (Memory) අදාළ නම ඇති වීඩියෝ සෙවීම
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
        await event.reply(f"❌ **{movie_title}** සඳහා වෙනත් Qualities කිසිවක් Bot ගේ Database මතකයේ හමු නොවීය.\n*(සටහන: Bot ඔන් කළ පසු Private Group එකට දාන ලද වීඩියෝ පමණක් මෙහි පෙන්වනු ඇත.)*")

# ---------------------------------------------------------
# 4. Button Click කළ විට අදාළ වීඩියෝව Inbox එකට යැවීම
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
print("🤖 Bot is successfully running on your PC... (Press Ctrl+C to stop)")
client.run_until_disconnected()