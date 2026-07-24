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
PRIVATE_CHAT_ID = "@moviesprivatelk"  # ඔයාගේ Database Channel / Group එක

client = TelegramClient('my_local_bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
logging.basicConfig(format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# ---------------------------------------------------------
# Generic JSON-file "database" helpers (API එකක් නැතුව local storage)
# ---------------------------------------------------------
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


VIDEOS_DB_FILE = "videos_db.json"
REQUESTS_DB_FILE = "requests_db.json"
USERS_DB_FILE = "users_db.json"
OWNER_MAP_FILE = "owner_map.json"      # owner_dm_msg_id (str) -> request info, for reply-relay
OWNER_ID_FILE = "owner_id.json"        # cached {"owner_id": <int>} per group

db_videos = load_json(VIDEOS_DB_FILE, [])
db_requests = load_json(REQUESTS_DB_FILE, [])   # list of dicts
db_users = load_json(USERS_DB_FILE, [])         # list of user ids (for /broadcast)
owner_map = load_json(OWNER_MAP_FILE, {})       # str(msg_id) -> {...}
owner_cache = load_json(OWNER_ID_FILE, {})      # str(chat_id) -> owner_id


def track_user(event_or_id):
    """Remember every user who has talked to the bot, so /broadcast can reach them."""
    uid = event_or_id if isinstance(event_or_id, int) else event_or_id.sender_id
    if uid and uid not in db_users:
        db_users.append(uid)
        save_json(USERS_DB_FILE, db_users)


def extract_title(text):
    """'Movie Name - 720p' -> 'Movie Name'. Falls back to full text."""
    match = re.match(r'^(.*?)\s*-\s*\d{3,4}p', text, re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


async def get_owner_id(event):
    """Find & cache the creator/owner of the group this event came from."""
    chat_id = event.chat_id
    key = str(chat_id)
    if key in owner_cache:
        return owner_cache[key]
    owner_id = None
    async for user in client.iter_participants(chat_id, filter=ChannelParticipantsAdmins):
        if isinstance(user.participant, ChannelParticipantCreator):
            owner_id = user.id
            break
    if owner_id:
        owner_cache[key] = owner_id
        save_json(OWNER_ID_FILE, owner_cache)
    return owner_id


def next_request_id():
    return (max([r['req_id'] for r in db_requests], default=0)) + 1


# ---------------------------------------------------------
# 2. Private Channel එකට වීඩියෝවක් දානකොටම Database එකට Save කිරීම
#    + ඒ movie එක කලින් කවුරු හරි Request කරලද කියලා check කරලා
#      Auto-notify කිරීම (Feature #1: Request Subscription & Auto Notify)
# ---------------------------------------------------------
@client.on(events.NewMessage(chats=PRIVATE_CHAT_ID, func=lambda e: e.video or e.document))
async def store_private_video(event):
    text = event.text or event.caption or ""
    if not text:
        return

    if not any(item['id'] == event.id for item in db_videos):
        db_videos.append({'id': event.id, 'text': text})
        save_json(VIDEOS_DB_FILE, db_videos)
        print(f"📥 Saved to Database: {text}")

    uploaded_title = extract_title(text).lower()

    changed = False
    for req in db_requests:
        if req['status'] != 'pending':
            continue
        req_title = req['movie'].lower()
        if req_title in uploaded_title or uploaded_title in req_title:
            req['status'] = 'fulfilled'
            changed = True

            # DM the user who requested it
            try:
                await client.send_message(
                    req['user_id'],
                    f"🎉 ඔයා ඉල්ලපු **{req['movie']}** දැන් Group එකේ තියෙනවා!\n\n"
                    f"👉 Group එකට ගිහින් අදාළ Post එකට Reply කරමින් `/quality` ලෙස Type කරලා Download කරගන්න."
                )
            except Exception as e:
                print(f"⚠️ Couldn't DM user {req['user_id']}: {e}")

            # Reply publicly in the group under the original request message
            try:
                await client.send_message(
                    req['chat_id'],
                    f"📢 [{req['first_name']}](tg://user?id={req['user_id']}) ඉල්ලපු "
                    f"**{req['movie']}** දැන් Group එකේ Available!",
                    reply_to=req['msg_id']
                )
            except Exception as e:
                print(f"⚠️ Couldn't post group notification: {e}")

    if changed:
        save_json(REQUESTS_DB_FILE, db_requests)


# ---------------------------------------------------------
# 3. /start, /help, hi, hello සඳහා Welcome Message එක
#    (Feature-complete command menu එකක් සමඟ - Fixed)
# ---------------------------------------------------------
HELP_TEXT = (
    "🛠️ **මට තියෙන Commands ටික:**\n\n"
    "1️⃣ Movie වීඩියෝවකට/පෝස්ට් එකකට **Reply** කර `/quality` - ඒ movie එකේ tිබෙන qualities බලන්න\n"
    "2️⃣ `/search [නම]` - Reply නොකර, movie නමින්ම qualities හොයන්න\n"
    "3️⃣ `/request [නම]` - නැති Movie එකක් Owner ගෙන් ඉල්ලන්න\n"
    "4️⃣ `/myrequests` - ඔයා කරපු requests බලන්න\n"
    "5️⃣ `/cancelrequest [number]` - Pending request එකක් cancel කරන්න\n"
    "6️⃣ `/latest [count]` - අලුතෙන්ම add වුණු movies බලන්න (default 5)\n"
    "7️⃣ `/stats` - Database එකේ movies/requests ගණන බලන්න\n"
    "8️⃣ `/rules` - Group Rules බලන්න\n"
    "9️⃣ `/ping` - Bot Online ද කියලා check කරන්න\n"
    "🔟 `/broadcast [msg]` - (Owner only) සියලුම Users ලට Message යවන්න\n\n"
    "⚠️ **වැදගත්:** වීඩියෝ ලබා ගැනීමට ප්‍රථම, පහත බොත්තම Click කර මාගේ Inbox වෙත ගොස් 'Start' ලබා දෙන්න!"
)


@client.on(events.NewMessage(pattern=r'(?i)^(/start|/help|hi|hello)$'))
async def handle_start_help(event):
    track_user(event)
    sender = await event.get_sender()
    first_name = sender.first_name if sender else "යාළුවා"

    welcome_text = (
        f"👋 ආයුබෝවන් **{first_name}**!\n\n"
        f"🤖 මම තමයි Movies Bot. මට පුළුවන් ඔයාට අවශ්‍ය Movies වල විවිධ Qualities (480p, 720p, 1080p) "
        f"හොයලා ඔයාගේ Inbox එකටම එවන්න.\n\n"
        f"{HELP_TEXT}"
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
                f"🎬 අපගේ Group එකට සාදරයෙන් පිළිගනිමු. ඔබට අවශ්‍ය චිත්‍රපට පහසුවෙන් ලබා ගැනීමට "
                f"ඕනෑම චිත්‍රපටයකට Reply කරමින් `/quality` ලෙස Type කරන්න, නැත්නම් `/help` ලෙස Type "
                f"කර මගේ සියලුම Features බලාගන්න."
            )
            await event.reply(welcome_msg)


# ---------------------------------------------------------
# 5. Bot ගේ තත්ත්වය පරීක්ෂා කිරීම (/ping)
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/ping$'))
async def ping_command(event):
    track_user(event)
    await event.reply("🏓 **Pong!**\n✅ Bot ඉතා හොඳින් ක්‍රියාකාරීව පවතී.")


# ---------------------------------------------------------
# 6. /request Command එක (චිත්‍රපට ඉල්ලීම් Owner වෙත යැවීම)
#    + Request එක Database එකේ save කර, Owner reply-relay සඳහා
#      owner_map එකේ record කිරීම
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/request\s+(.+)'))
async def handle_request(event):
    track_user(event)
    if not event.is_group:
        await event.reply("⚠️ මේ Command එක පාවිච්චි කරන්න පුළුවන් Group එකක් ඇතුළේ විතරයි!")
        return

    movie_name = event.pattern_match.group(1).strip()
    sender = await event.get_sender()
    chat = await event.get_chat()

    searching_msg = await event.reply("⏳ ඔයාගේ Request එක Group Owner ට යවමින් පවතී...")

    try:
        owner_id = await get_owner_id(event)

        await searching_msg.delete()
        if owner_id:
            msg = (
                f"🎬 **New Movie Request** 🎬\n\n"
                f"👤 **ඉල්ලුම්කරු:** {sender.first_name} (@{sender.username if sender.username else 'None'})\n"
                f"🎥 **චිත්‍රපටය:** {movie_name}\n"
                f"📍 **Group එක:** {chat.title}\n\n"
                f"↩️ මේ පණිවිඩයට **Reply** කලොත්, ඔයා ලියන දේ කෙලින්ම Group එකේ, ඉල්ලුම් කළ කෙනාට "
                f"Reply එකක් විදියට පේනවා."
            )
            sent_owner_msg = await client.send_message(owner_id, msg)

            # Save request for tracking / auto-notify later
            req_id = next_request_id()
            db_requests.append({
                'req_id': req_id,
                'movie': movie_name,
                'user_id': sender.id,
                'first_name': sender.first_name or "User",
                'username': sender.username,
                'chat_id': event.chat_id,
                'msg_id': event.id,
                'status': 'pending'
            })
            save_json(REQUESTS_DB_FILE, db_requests)

            # Map the owner's DM message id -> request info, so we can relay owner's reply
            owner_map[str(sent_owner_msg.id)] = {
                'owner_id': owner_id,
                'chat_id': event.chat_id,
                'msg_id': event.id,
                'user_id': sender.id,
                'first_name': sender.first_name or "User",
                'movie': movie_name,
                'req_id': req_id
            }
            save_json(OWNER_MAP_FILE, owner_map)

            await event.reply(
                f"✅ ඔයාගේ චිත්‍රපට ඉල්ලීම සාර්ථකව Group Owner වෙත යවන ලදී! "
                f"(Request #{req_id} - `/myrequests` කර බලන්න)"
            )
        else:
            await event.reply("❌ Group Owner ව සොයාගැනීමට නොහැකි විය.")

    except Exception as e:
        print(f"Error finding owner: {e}")
        await searching_msg.delete()
        await event.reply("❌ Error: Owner වෙත පණිවිඩය යැවීමට Bot හට Admin Permissions නොමැත.")


# ---------------------------------------------------------
# 6b. Owner private chat එකේදී, Bot එවපු Request message එකට
#     Reply කලොත්, ඒ පිළිතුර Group එකේ ඉල්ලූ කෙනාට Reply එකක්
#     විදියට Public group එකේ පෙන්වීම (Feature #2: Owner Reply Relay)
# ---------------------------------------------------------
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.is_reply))
async def relay_owner_reply(event):
    reply_to_id = event.reply_to_msg_id
    key = str(reply_to_id)
    if key not in owner_map:
        return  # not a reply to one of our request messages

    info = owner_map[key]
    # Make sure it's actually the owner replying, not someone else
    if event.sender_id != info['owner_id']:
        return

    owner_reply_text = event.text or event.raw_text or ""
    if not owner_reply_text:
        return

    try:
        await client.send_message(
            info['chat_id'],
            f"💬 [{info['first_name']}](tg://user?id={info['user_id']}), ඔයාගේ "
            f"**{info['movie']}** Request එකට Group Owner මෙහෙම කිවුවා:\n\n"
            f"📩 _{owner_reply_text}_",
            reply_to=info['msg_id']
        )
        await event.reply("✅ ඔයාගේ පිළිතුර Group එකේ ඉල්ලූ කෙනාට යවන ලදී!")
    except Exception as e:
        print(f"⚠️ Couldn't relay owner reply: {e}")
        await event.reply(f"❌ පිළිතුර යැවීමට නොහැකි විය: {e}")


# ---------------------------------------------------------
# 7. /quality Command එක (Reply-based search)
# ---------------------------------------------------------
def search_qualities(movie_title):
    """Returns list of Button.inline objects for all qualities found for a title."""
    buttons = []
    seen_qualities = set()
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
    return buttons


@client.on(events.NewMessage(chats=PUBLIC_CHAT_ID, pattern=r'(?i)^/quality'))
async def handle_quality_command(event):
    track_user(event)
    if not event.is_reply:
        await event.reply("⚠️ කරුණාකර වෙනත් චිත්‍රපට වීඩියෝවකට **Reply කරමින්** `/quality` ලෙස Type කරන්න.")
        return

    reply_msg = await event.get_reply_message()
    original_text = reply_msg.text or reply_msg.caption or ""

    if not original_text:
        await event.reply("⚠️ මෙම Reply කළ පණිවිඩයේ නමක් (Caption එකක්) සොයාගත නොහැකි විය.")
        return

    movie_title = extract_title(original_text)
    status_msg = await event.reply(f"🔎 **{movie_title}** සඳහා පවතින Qualities සොයමින් පවතී...")

    try:
        buttons = search_qualities(movie_title)
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
# 7b. /search [name] - Feature #3: Reply නොකර, movie නමින්ම search කිරීම
# ---------------------------------------------------------
@client.on(events.NewMessage(chats=PUBLIC_CHAT_ID, pattern=r'(?i)^/search\s+(.+)'))
async def handle_search_command(event):
    track_user(event)
    movie_title = event.pattern_match.group(1).strip()
    status_msg = await event.reply(f"🔎 **{movie_title}** සඳහා පවතින Qualities සොයමින් පවතී...")

    try:
        buttons = search_qualities(movie_title)
        if buttons:
            formatted_buttons = [[b] for b in buttons]
            await status_msg.edit(
                f"🍿 **{movie_title}**\nඅදාළ Qualities පහතින් ලබාගන්න (Inbox වෙත පැමිණේ):",
                buttons=formatted_buttons
            )
        else:
            await status_msg.edit(
                f"❌ **{movie_title}** සඳහා Database එකේ කිසිවක් හමු නොවීය.\n"
                f"💡 `/request {movie_title}` ලෙස Type කර Owner ගෙන් ඉල්ලන්න."
            )
    except Exception as e:
        await status_msg.edit(f"❌ දෝෂයක් ආවා: {e}")


# ---------------------------------------------------------
# 7c. /latest [count] - Feature #4: අලුතෙන්ම Add වුණු Movies
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/latest(\s+(\d+))?$'))
async def handle_latest_command(event):
    track_user(event)
    count = 5
    if event.pattern_match.group(2):
        count = min(int(event.pattern_match.group(2)), 20)

    if not db_videos:
        await event.reply("📭 Database එකේ තවම Movies කිසිවක් නැත.")
        return

    latest_items = db_videos[-count:][::-1]
    lines = ["🆕 **අලුතෙන්ම Add වුණු Movies:**\n"]
    for item in latest_items:
        title = extract_title(item['text'])
        lines.append(f"🎬 {title}")

    await event.reply("\n".join(lines))


# ---------------------------------------------------------
# 7d. /stats - Feature #5: Database Statistics
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/stats$'))
async def handle_stats_command(event):
    track_user(event)
    total_videos = len(db_videos)
    pending_requests = len([r for r in db_requests if r['status'] == 'pending'])
    fulfilled_requests = len([r for r in db_requests if r['status'] == 'fulfilled'])
    total_users = len(db_users)

    await event.reply(
        f"📊 **Bot Statistics**\n\n"
        f"🎞️ Total Videos in Database: **{total_videos}**\n"
        f"⏳ Pending Requests: **{pending_requests}**\n"
        f"✅ Fulfilled Requests: **{fulfilled_requests}**\n"
        f"👥 Total Users Interacted: **{total_users}**"
    )


# ---------------------------------------------------------
# 7e. /myrequests - Feature #6: User ගේ Pending Requests බැලීම
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/myrequests$'))
async def handle_myrequests_command(event):
    track_user(event)
    sender_id = event.sender_id
    my_reqs = [r for r in db_requests if r['user_id'] == sender_id]

    if not my_reqs:
        await event.reply("📭 ඔයා තවම කිසිම Movie Request එකක් කරලා නැහැ. `/request [නම]` කරලා try කරන්න.")
        return

    lines = ["📋 **ඔයාගේ Requests:**\n"]
    for r in my_reqs:
        status_icon = "✅" if r['status'] == 'fulfilled' else "⏳"
        lines.append(f"{status_icon} #{r['req_id']} - {r['movie']} ({r['status']})")

    await event.reply("\n".join(lines))


# ---------------------------------------------------------
# 7f. /cancelrequest [number] - Feature #7: Request Cancel කිරීම
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/cancelrequest\s+(\d+)$'))
async def handle_cancel_request(event):
    track_user(event)
    req_id = int(event.pattern_match.group(1))
    sender_id = event.sender_id

    target = next((r for r in db_requests if r['req_id'] == req_id and r['user_id'] == sender_id), None)
    if not target:
        await event.reply("❌ එවැනි Request එකක් ඔයාගේ නමින් හමු නොවීය.")
        return

    if target['status'] != 'pending':
        await event.reply(f"⚠️ Request #{req_id} දැනටමත් **{target['status']}** තත්ත්වයේ පවතී, Cancel කළ නොහැක.")
        return

    target['status'] = 'cancelled'
    save_json(REQUESTS_DB_FILE, db_requests)
    await event.reply(f"🗑️ Request #{req_id} ({target['movie']}) Cancel කරන ලදී.")


# ---------------------------------------------------------
# 7g. /rules - Feature #8: Group Rules
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/rules$'))
async def handle_rules_command(event):
    track_user(event)
    await event.reply(
        "📜 **Group Rules:**\n\n"
        "1️⃣ අනවශ්‍ය Spam Messages, Links දාන්න එපා.\n"
        "2️⃣ Movie/Series Request `/request [නම]` විදියට විතරක් යවන්න.\n"
        "3️⃣ අනුන්ට ගරු කරමින් හැසිරෙන්න.\n"
        "4️⃣ Admin/Owner ලාගේ තීරණවලට එකඟ වන්න.\n\n"
        "මේ රීති කඩ කරන අයට Group එකෙන් Remove කරන්නත් පුළුවන්."
    )


# ---------------------------------------------------------
# 7h. /broadcast [message] - Feature #9: Owner-only Broadcast
#     (කිසිම Payment/External API අවශ්‍ය නොවේ - stored user ids හරහා)
# ---------------------------------------------------------
@client.on(events.NewMessage(pattern=r'(?i)^/broadcast\s+(.+)', func=lambda e: e.is_private))
async def handle_broadcast_command(event):
    sender_id = event.sender_id
    # Only allow if this sender is a known owner of at least one cached group
    if sender_id not in owner_cache.values():
        await event.reply("⛔ මේ Command එක පාවිච්චි කරන්න පුළුවන් Group Owner ට විතරයි.")
        return

    message_text = event.pattern_match.group(1)
    sent, failed = 0, 0
    status = await event.reply("📤 Broadcast යවමින් පවතී...")

    for uid in db_users:
        try:
            await client.send_message(uid, f"📢 **Announcement:**\n\n{message_text}")
            sent += 1
        except Exception:
            failed += 1

    await status.edit(f"✅ Broadcast සම්පූර්ණයි!\n📨 Sent: {sent} | ❌ Failed: {failed}")


# ---------------------------------------------------------
# Feature #10: Auto-cleanup - remove cancelled/fulfilled requests
#              older than a fixed count so json files don't grow forever.
#              (simple housekeeping, runs whenever a new request is added)
# ---------------------------------------------------------
def housekeeping():
    global db_requests
    active = [r for r in db_requests if r['status'] == 'pending']
    done = [r for r in db_requests if r['status'] != 'pending']
    # keep only the last 200 completed/cancelled requests
    db_requests = active + done[-200:]
    save_json(REQUESTS_DB_FILE, db_requests)


# ---------------------------------------------------------
# 8. Button Click කළ විට Inbox එකට Forward කිරීම
# ---------------------------------------------------------
@client.on(events.CallbackQuery(pattern=b"^fwd_(\\d+)"))
async def handle_quality_download(event):
    msg_id = int(event.pattern_match.group(1).decode('utf-8'))
    sender = await event.get_sender()
    track_user(sender.id)

    try:
        await client.forward_messages(sender.id, msg_id, PRIVATE_CHAT_ID)
        await event.answer("✅ වීඩියෝව ඔබගේ Inbox එකට යවන ලදී!", alert=False)
    except Exception:
        await event.answer("⚠️ කරුණාකර පළමුව Bot ගේ Inbox (PM) එකට ගොස් 'Start' ලබා දෙන්න!", alert=True)


# Run Bot
print("🤖 Bot is successfully running...")
housekeeping()
client.run_until_disconnected()
