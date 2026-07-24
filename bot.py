import logging
import re
from telethon import TelegramClient, events, Button

# ---------------------------------------------------------
# 1. Credentials
# ---------------------------------------------------------
API_ID = 38027451
API_HASH = "205920d66f76fe9c1d18ba068011f803"
BOT_TOKEN = "7978238021:AAHeZiX2t3ewpse9hWQC49ffE6VIbH3qeWc"

PUBLIC_CHAT_ID = "@sn_and_wormgpt"
PRIVATE_CHAT_ID = "@moviesprivatelk" # ඔයාගේ Database Channel / Group එක

client = TelegramClient('my_local_bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# ---------------------------------------------------------
# 2. /quality Command එක (Bot Restrictions රහිතව)
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

    # Movie Name එක වෙන් කර ගැනීම (උදා: "Ben 10: Alien Force Season 01")
    match = re.match(r'^(.*?)\s*-\s*\d{3,4}p', original_text, re.IGNORECASE)
    movie_title = match.group(1).strip() if match else original_text.strip()

    status_msg = await event.reply(f"🔎 **{movie_title}** සඳහා පවතින Qualities සොයමින් පවතී...")

    buttons = []
    seen_qualities = set()

    try:
        # SearchRequest වෙනුවට අන්තිම Messages 300 කෙලින්ම Fetch කර Python හරහා Search කිරීම
        async for message in client.iter_messages(PRIVATE_CHAT_ID, limit=300):
            msg_text = message.text or message.caption or ""
            
            # Text එකේ Movie Title එක තියෙනවා නම් සහ Video එකක් තියෙනවා නම් පමණක් බලයි
            if msg_text and movie_title.lower() in msg_text.lower():
                if message.video or message.document:
                    q_match = re.search(r'(\d{3,4}p)', msg_text, re.IGNORECASE)
                    if q_match:
                        quality = q_match.group(1).lower()
                        
                        if quality not in seen_qualities:
                            seen_qualities.add(quality)
                            button_data = f"fwd_{message.id}".encode('utf-8')
                            btn_label = f"⬇️ {quality.upper()} Download"
                            buttons.append(Button.inline(btn_label, data=button_data))

        # Buttons සෑදීම
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
# 3. Button Click කළ විට Inbox එකට Forward කිරීම
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
