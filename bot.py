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
# [NEW] 2. /start, /help, hi, hello සඳහා Welcome Message එක
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
        f"⚠️ **වැදගත්:** වීඩියෝ ලබා ගැනීමට ප්‍රථම පහත බොත්තම Click කර මාගේ Inbox වෙත ගොස් 'Start' ලබා දෙන්න!"
    )
    
    # Bot ගේ Username එක ලබාගෙන Start Button එකක් සෑදීම
    me = await client.get_me()
    bot_username = me.username
    
    buttons = [
        [Button.url("🚀 Start Bot in Inbox", f"https://t.me/{bot_username}?start=1")]
    ]
    
    await event.reply(welcome_text, buttons=buttons)


# ---------------------------------------------------------
# [NEW] 3. අලුතින් Group එකට Join වෙන සාමාජිකයන්ව පිළිගැනීම
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
# [NEW] 4. Bot ගේ තත්ත්වය පරීක්ෂා කිරීම (/ping)
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/ping$'))
async def ping_command(event):
    await event.reply("🏓 **Pong!**\n✅ Bot ඉතා හොඳින් ක්‍රියාකාරීව පවතී.")


# ---------------------------------------------------------
# 5. /quality Command එක (Bot Restrictions රහිතව)
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
        async for message in client.iter_messages(PRIVATE_CHAT_ID, limit=300):
            msg_text = message.text or message.caption or ""
            
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
# 6. Button Click කළ විට Inbox එකට Forward කිරීම
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
