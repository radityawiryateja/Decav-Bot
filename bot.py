import json
import logging
import re
import markdown
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from supabase import create_client

# Token dan Channel
BOT_TOKEN = '8288933289:AAHCp1BzSdiJyy8owiaRiYOXYKw7tH87V3k'
CHANNEL_ID = '@basepf'  # Ganti dengan username channel kamu
GROUP_ID_DISKUSI = -1002457998417  # <- Ganti dengan ID grup diskusi kamu
ADMIN_GROUP_ID = -1003093290169  # Ganti dengan ID grup admin kamu
LOG_GROUP_ID = -1002973369337  # Ganti dengan ID grup log kamu
SUPABASE_URL = 'https://kddjwsnndbliljnxixuv.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtkZGp3c25uZGJsaWxqbnhpeHV2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc1OTI2MzIsImV4cCI6MjA3MzE2ODYzMn0.Byv8o2VbTnoq4nQjAHs_ptkK8BXy1W3kkeNFkwCXYYA'

# Inisialisasi logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Status bot (aktif atau tidak)
bot_active = True

# Inisialisasi Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# callback yang dijalankan setelah Application.initialize()
async def on_startup(application: Application):
    try:
        me = await application.bot.get_me()
        logger.info(f"✅ Bot siap: @{me.username} (id={me.id})")
    except Exception as e:
        logger.error(f"⚠️ Gagal get_me saat startup: {e}")

# callback saat shutdown (opsional)
async def on_shutdown(application: Application):
    logger.info("⏹️ Bot shutting down...")


def load_required_channels():
    response = supabase.table('required_channels').select("channel_username").execute()
    if response.data:
        return [row["channel_username"] for row in response.data]
    return []

def save_required_channels(channels):
    supabase.table('required_channels').delete().neq("channel_username", "").execute()
    for channel in channels:
        supabase.table('required_channels').insert({"channel_username": channel}).execute()

required_channels = load_required_channels()

async def check_subscription(user_id, context: CallbackContext):
    for channel in required_channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logger.error(f"Error checking subscription in {channel}: {e}")
            return False
    return True

async def get_active_hashtags():
    response = supabase.table("triggered_hashtags").select("hashtag").eq("active", True).execute()
    if response.data:
        return [row["hashtag"] for row in response.data]
    return []

async def add_hashtag(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Gunakan format: /addhashtag <hashtag>")
        return

    hashtag = context.args[0].strip()
    supabase.table("triggered_hashtags").upsert({"hashtag": hashtag}).execute()
    await update.message.reply_text(f"✅ Hashtag `{hashtag}` berhasil ditambahkan!", parse_mode="Markdown")

async def remove_hashtag(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Gunakan format: /removehashtag <hashtag>")
        return

    hashtag = context.args[0].strip()
    supabase.table("triggered_hashtags").delete().eq("hashtag", hashtag).execute()
    await update.message.reply_text(f"❌ Hashtag `{hashtag}` berhasil dihapus!", parse_mode="Markdown")

async def enable_hashtag(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if not context.args:
        await update.message.reply_text("Gunakan format: /enablehashtag <hashtag>")
        return
    hashtag = context.args[0].strip()
    supabase.table("triggered_hashtags").update({"active": True}).eq("hashtag", hashtag).execute()
    await update.message.reply_text(f"✅ Hashtag `{hashtag}` diaktifkan!", parse_mode="Markdown")

async def disable_hashtag(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if not context.args:
        await update.message.reply_text("Gunakan format: /disablehashtag <hashtag>")
        return
    hashtag = context.args[0].strip()
    supabase.table("triggered_hashtags").update({"active": False}).eq("hashtag", hashtag).execute()
    await update.message.reply_text(f"⚠️ Hashtag `{hashtag}` dinonaktifkan!", parse_mode="Markdown")


async def set_required_channels(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Gunakan format: /setrequired @channel1 @channel2")
        return

    global required_channels
    required_channels = context.args
    save_required_channels(required_channels)
    await update.message.reply_text(f"Daftar channel wajib diikuti telah diperbarui: {', '.join(required_channels)}")

async def save_user(user_id, username):
    data = {
        "user_id": user_id,
        "username": username
    }
    # Supaya kalau sudah ada tidak error, tapi update kolom username
    response = supabase.table("users").upsert(
        data,
        on_conflict=["user_id"]
    ).execute()
    print("User saved:", response)


async def start(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Simpan user ke database
    await save_user(user_id, username)
    if await check_subscription(user_id, context):
        await update.message.reply_text(
            "Halo, selamat datang di *BasePF*! ☕️\n\n"
            "𔐼 *Base PF:* [@basepf](https://t.me/basepf)\n"
            "𔐼 *LPM PF:* [@lapakproofneeds](https://t.me/lapakproofneeds)\n"
            "𔐼 *Rules:* [@rulespf](https://t.me/rulespf)\n\n"
            "Ketuk /menu untuk menampilkan navigasi 🐿",
            parse_mode="Markdown"
        )
    else:
        keyboard = [[InlineKeyboardButton("Join Channels", url=f"https://t.me/{channel[1:]}")] for channel in required_channels]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Sebelum lanjut, silakan join channel berikut dulu ya!", reply_markup=reply_markup)


async def handle_pesan(update: Update, context: CallbackContext):
    global bot_active
    if update.effective_chat.type != "private":
        return
    
    if not bot_active:
        await update.message.reply_text("Bot sedang dipause oleh admin.")
        return

    user_id = update.effective_user.id

    username = update.effective_user.username
    first_name = update.effective_user.first_name
    display_name = f"@{username}" if username else first_name

    # Cek apakah user sudah subscribe channel
    if not await check_subscription(user_id, context):
        keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{channel[1:]}")] for channel in required_channels]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Sebelum lanjut, silakan join channel berikut dulu ya!", reply_markup=reply_markup)
        return

    # Ambil semua hashtag aktif dari database
    active_hashtags = await get_active_hashtags()  # Fungsi yang sudah kita buat sebelumnya

    # Ambil teks pesan atau caption
    text_content = (update.message.text or update.message.caption or "").strip().lower()

    # Cek apakah pesan mengandung salah satu hashtag aktif
    is_direct_forward = any(ht.lower() in text_content for ht in active_hashtags)

    # Tambahkan pengecekan pesan kosong
    # Misal user cuma ketik hashtag tapi tidak ada teks tambahan atau media
    text_without_hashtag = text_content
    for ht in active_hashtags:
        text_without_hashtag = re.sub(re.escape(ht), "", text_without_hashtag, flags=re.IGNORECASE)
    text_without_hashtag = text_without_hashtag.strip()

    if is_direct_forward and not text_without_hashtag and not (update.message.photo or update.message.video or update.message.document or update.message.audio or update.message.voice or update.message.sticker):
        await update.message.reply_text("⚠️ Harap isi pesan terlebih dahulu sebelum mengirim hashtag!")
        return

    # Tentukan target kiriman
    target_chat_id = CHANNEL_ID if is_direct_forward else ADMIN_GROUP_ID
    caption = update.message.caption or ""

    # Tambahkan info pengirim jika pesan dikirim ke grup admin
    if not is_direct_forward:
        caption = (
            f"📩 Pesan dari: {first_name}\n"
            f"👤 Username: {display_name}\n"
            f"🆔 ID: {user_id}\n\n"
            f"💬 Pesan:\n"
            f"{caption if caption else ''}"
        )

    message_sent = None

    # Kirim pesan berdasarkan jenis media
    if update.message.text:

        text_message = (
            update.message.text if is_direct_forward else 
            f"📩 Pesan dari: {first_name}\n"
            f"👤 Username: {display_name}\n"
            f"🆔 ID: {user_id}\n\n"
            f"💬 Pesan:\n{update.message.text or ''}"
        )

        message_sent = await context.bot.send_message(chat_id=target_chat_id, text=text_message)
    elif update.message.photo:
        message_sent = await context.bot.send_photo(chat_id=target_chat_id, photo=update.message.photo[-1].file_id, caption=caption)
    elif update.message.video:
        message_sent = await context.bot.send_video(chat_id=target_chat_id, video=update.message.video.file_id, caption=caption)
    elif update.message.document:
        message_sent = await context.bot.send_document(chat_id=target_chat_id, document=update.message.document.file_id, caption=caption)
    elif update.message.sticker:
        message_sent = await context.bot.send_sticker(chat_id=target_chat_id, sticker=update.message.sticker.file_id)
    elif update.message.audio:
        message_sent = await context.bot.send_audio(chat_id=target_chat_id, audio=update.message.audio.file_id, caption=caption)
    elif update.message.voice:
        message_sent = await context.bot.send_voice(chat_id=target_chat_id, voice=update.message.voice.file_id, caption=caption)
    else:
        await update.message.reply_text("Tipe pesan tidak didukung.")
        return

    # Jika pesan dikirim ke channel, tambahkan tombol untuk melihat pesan
    if is_direct_forward and message_sent:
        keyboard = [[InlineKeyboardButton("Lihat Pesan Kamu", url=f"https://t.me/{CHANNEL_ID[1:]}/{message_sent.message_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Pesan kamu telah dikirim ke channel! 🪶\n\n"
            "𔐼 *Base PF:* [@basepf](https://t.me/basepf)\n"
            "𔐼 *LPM PF:* [@lapakproofneeds](https://t.me/lapakproofneeds)\n"
            "𔐼 *Rules:* [@rulespf](https://t.me/rulespf)\n\n"
            "Jangan lupa kepoin channel diatas ya proofies!",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Pesan kamu telah dikirim, mohon tunggu beberapa saat.")

    if is_direct_forward and message_sent:
        supabase.table("menfess_map").insert({
            "post_id": message_sent.message_id,   # id pesan di channel
            "sender_user_id": user_id             # langsung ambil dari update.effective_user.id
        }).execute()

    # Log masuk ke grup
    if is_direct_forward and message_sent:
        message_link = f"https://t.me/{CHANNEL_ID[1:]}/{message_sent.message_id}"
        log_message = (
            f"📌 Log Menfess:\n"
            f"🕰️ Waktu: {update.message.date}\n"
            f"👤 Pengirim: {display_name}\n"
            f"🆔 ID: {user_id}\n"
            f"💬 Pesan: {update.message.text or 'Media'}"
        )

        log_keyboard = [[InlineKeyboardButton("🔍 Lihat Pesan", url=message_link)]]
        log_markup = InlineKeyboardMarkup(log_keyboard)

        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_message, reply_markup=log_markup)


async def handle_admin_reply(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID or not update.message.reply_to_message:
        return
    
    original_message = update.message.reply_to_message
    match = re.search(r"ID(?:\s*Pengguna)?:?\s*(\d+)", original_message.text or original_message.caption or "")

    if not match:
        return
    
    user_id = int(match.group(1))
    reply_text = update.message.text or update.message.caption

    # ✅ Kalau balasan admin itu command
    if reply_text and reply_text.startswith("/"):
        command_name = reply_text.split()[0]

        response = supabase.table("commands").select("content").eq("name", command_name).execute()
        if response.data:
            content = response.data[0]["content"]
            try:
                await context.bot.send_message(chat_id=user_id, text=content, parse_mode="Markdown")
                # kasih notif singkat di grup (opsional)
                notif = await update.message.reply_text(f"✅ Command `{command_name}` dikirim ke user {user_id}", parse_mode="Markdown")
                # auto hapus notif biar grup gak kotor
                import asyncio
                await asyncio.sleep(5)
                try:
                    await notif.delete()
                except:
                    pass
            except Exception as e:
                logger.error(f"Gagal kirim command ke user: {e}")
                await update.message.reply_text("❌ Gagal mengirim command ke user.")
        return  # ⛔ stop di sini, jangan lanjut ke flow balasan biasa!

    # ✅ Kalau bukan command → lanjut balasan biasa
    caption = f"{reply_text}" if reply_text else "📬 Balasan dari admin."

    try:
        if update.message.text:
            await context.bot.send_message(chat_id=user_id, text=caption)
        elif update.message.photo:
            await context.bot.send_photo(chat_id=user_id, photo=update.message.photo[-1].file_id, caption=caption)
        elif update.message.video:
            await context.bot.send_video(chat_id=user_id, video=update.message.video.file_id, caption=caption)
        elif update.message.document:
            await context.bot.send_document(chat_id=user_id, document=update.message.document.file_id, caption=caption)
        elif update.message.sticker:
            await context.bot.send_sticker(chat_id=user_id, sticker=update.message.sticker.file_id)
        elif update.message.audio:
            await context.bot.send_audio(chat_id=user_id, audio=update.message.audio.file_id, caption=caption)
        elif update.message.voice:
            await context.bot.send_voice(chat_id=user_id, voice=update.message.voice.file_id, caption=caption)
        else:
            await update.message.reply_text("Jenis balasan tidak didukung.")
            return

        notif = await update.message.reply_text("✅ Balasan telah dikirim ke user.")
        import asyncio
        await asyncio.sleep(5)
        try:
            await notif.delete()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        await update.message.reply_text("❌ Gagal mengirim balasan. Pastikan pengguna masih dapat menerima pesan.")

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if not msg:
        return

    post_id = msg.message_id
    logging.info(f"📩 Channel post masuk: post_id={post_id}")

    # Simpan sementara ke cache kalau perlu
    # (opsional, karena mapping fix-nya diambil dari auto-forward di grup)
    context.bot_data.setdefault("channel_posts", set()).add(post_id)


async def handle_discussion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # ✅ Kasus 1: auto-forward dari channel ke grup diskusi
    if msg.is_automatic_forward and msg.forward_origin and msg.forward_origin.type == "channel":
        origin_chat = msg.forward_origin.chat
        if origin_chat.username and ("@" + origin_chat.username.lower() == CHANNEL_ID.lower()):
            post_id = msg.forward_origin.message_id
            discussion_message_id = msg.message_id

            supabase.table("menfess_map").update({
                "discussion_message_id": discussion_message_id
            }).eq("post_id", post_id).execute()

            logging.info(f"✅ Mapping disimpan: post_id={post_id}, discussion_message_id={discussion_message_id}")
        else:
            logging.warning(f"⚠️ Forward dari channel lain: {origin_chat.username or origin_chat.id}")
            
            return  # stop di sini biar ga lanjut ke reply handler

    # ✅ Kasus 2: user reply di grup diskusi
    if msg.reply_to_message:
        replied_msg_id = msg.reply_to_message.message_id
        logging.info(f"🧵 Balasan diskusi terdeteksi: {replied_msg_id}")

        # Ambil sender_user_id dan post_id
        response = supabase.table("menfess_map").select("sender_user_id, post_id").eq("discussion_message_id", replied_msg_id).execute()
        if not response.data:
            logging.info("❌ Tidak ada mapping untuk discussion_message_id ini.")
            return

        sender_user_id = response.data[0]["sender_user_id"]
        post_id = response.data[0]["post_id"]
        logging.info(f"📩 Kirim balasan ke user_id: {sender_user_id}")

        # Link komentar ke channel post
        channel_username = CHANNEL_ID.lstrip("@")
        comment_link = f"https://t.me/{channel_username}/{post_id}?comment={msg.message_id}"

        keyboard = [[InlineKeyboardButton("💬 Lihat Balasan", url=comment_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Ambil display name pengirim balasan
        user = msg.from_user
        commenter = f"{user.first_name} (@{user.username})" if user.username else user.first_name

        # Teks notifikasi
        text_notification = f"📬 {commenter} berkomentar untuk menfess kamu!"

        try:
            await context.bot.send_message(
                chat_id=sender_user_id,
                text=text_notification,
                reply_markup=reply_markup
            )
            logging.info("✅ Balasan berhasil dikirim ke user.")
        except Exception as e:
            logger.error(f"❌ Gagal kirim balasan ke user: {e}")



async def open_bot(update: Update, context: CallbackContext):
    global bot_active
    if update.effective_chat.id == ADMIN_GROUP_ID:
        bot_active = True
        await update.message.reply_text("✅ Bot telah diaktifkan kembali.")

async def close_bot(update: Update, context: CallbackContext):
    global bot_active
    if update.effective_chat.id == ADMIN_GROUP_ID:
        bot_active = False
        await update.message.reply_text("⏸️ Bot telah dipause. Kirim /open untuk mengaktifkan kembali.")

async def get_group_id(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title if update.effective_chat.title else "Private Chat"

    response_text = f"🆔 ID Grup/Channel: `{chat_id}`\n🏷️ Nama: {chat_title}"
    await update.message.reply_text(response_text, parse_mode="Markdown")

async def get_all_user_ids():
    """Mengambil semua user_id yang terdaftar di database Supabase."""
    response = supabase.table("users").select("user_id").execute()
    
    # Pastikan response memiliki data
    if hasattr(response, "data") and response.data:
        return [row["user_id"] for row in response.data]
    
    return []

async def remove_failed_user(user_id):
    """Menghapus user_id dari database jika gagal menerima pesan."""
    try:
        supabase.table("users").delete().eq("user_id", user_id).execute()
        logger.info(f"User {user_id} dihapus dari database.")
    except Exception as e:
        logger.error(f"Gagal menghapus user {user_id}: {e}")

async def menu(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private":
        return

    menu_text = (
        "📋 *Daftar Hashtag BasePF*\n\n"
        "🐿 `#wta` – Untuk bertanya\n"
        "🐿 `#wtb` – Untuk mencari barang/jasa\n"
        "🐿 `#hiring` – Untuk informasi hiring admin\n"
        "🐿 `#mutual` – Untuk ajakan mutualan BA \n"
        "🐿 `#ptpt` – Untuk mencari partner ptpt\n"
        "🐿 `#cl` – Untuk info event costless\n"
        "🐿 `#oot` – Bebas (hanya saat sesi oot)\n\n"
        "⚠️ *Peringatan:*\n"
        "Gunakan hashtag dengan benar dan bijak. Hindari spam atau keluar dari ranah profneeds/editing."
    )

    # Inline keyboard menuju rules
    keyboard = [
        [InlineKeyboardButton("📜 Baca Rules Lengkap", url="https://t.me/rulespf/8")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(menu_text, parse_mode="Markdown", reply_markup=reply_markup)


async def broadcast_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengirim forward pesan dari channel publik ke semua user bot."""
    if update.effective_chat.id != ADMIN_GROUP_ID or not context.args:
        return await update.message.reply_text("Gunakan format: /broadcastfw <link>")

    link = context.args[0]

    # Validasi link harus dari channel publik (t.me/username/message_id)
    match = re.match(r"https://t\.me/([a-zA-Z0-9_]+)/(\d+)", link)
    if not match:
        return await update.message.reply_text("❌ Link tidak valid atau bukan dari channel publik!")

    channel_username, message_id = match.groups()

    user_list = await get_all_user_ids()
    success_count = 0
    failed_count = 0

    for user_id in user_list:
        try:
            await context.bot.forward_message(
                chat_id=user_id,
                from_chat_id=f"@{channel_username}",
                message_id=int(message_id)
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Gagal forward ke {user_id}: {e}")
            failed_count += 1
            await remove_failed_user(user_id)  # ✅ Hapus user dari database

    report = f"✅ Forward selesai!\n- Berhasil: {success_count} user\n- Gagal: {failed_count} user"

    await update.message.reply_text(report)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengirim pesan broadcast ke semua user."""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Gunakan format: /broadcast <teks>")
        return

    message_text = " ".join(context.args)
    user_list = await get_all_user_ids()

    success_count = 0
    failed_count = 0

    for user_id in user_list:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception as e:
            logger.error(f"Gagal kirim ke {user_id}: {e}")
            failed_count += 1
            await remove_failed_user(user_id)  # ✅ Hapus user dari database

    report = f"✅ Broadcast selesai!\n- Berhasil: {success_count} user\n- Gagal: {failed_count} user"

    await update.message.reply_text(report)

    # Fungsi untuk menambahkan command
async def add_command(update: Update, context: CallbackContext) -> None:
    if update.message.reply_to_message:
        command_name = context.args[0] if context.args else None
        command_content = update.message.reply_to_message.text
    else:
        if len(context.args) < 2:
            await update.message.reply_text("Gunakan format: /addcommand <nama> <isi>")
            return
        command_name, command_content = context.args[0], " ".join(context.args[1:])

    command_name = command_name
    if not command_name.startswith("/"):
        command_name = "/" + command_name  # Pastikan selalu pakai "/"

    logging.info(f"Menyimpan command: {command_name}")

    response = supabase.table("commands").upsert({"name": command_name, "content": command_content}).execute()
    if response.data:
        await update.message.reply_text(f"Command `{command_name}` berhasil disimpan!", parse_mode='Markdown')
    else:
        await update.message.reply_text("Gagal menyimpan command.")


# Fungsi untuk menghapus command
async def delete_command(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Gunakan format: /deletecommand <nama>")
        return
    
    command_name = context.args[0]

    # ✅ Pastikan selalu ada "/"
    if not command_name.startswith("/"):
        command_name = "/" + command_name

    response = supabase.table("commands").delete().eq("name", command_name).execute()
    
    if response.data:
        await update.message.reply_text(f"Command `{command_name}` berhasil dihapus!", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"Command `{command_name}` tidak ditemukan atau gagal dihapus.", parse_mode='Markdown')

async def settings(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return  # cuma admin group yang bisa akses

    # --- Ambil required channels ---
    channels = load_required_channels()
    channels_text = "\n".join([f"𔐼 {c}" for c in channels]) if channels else "– Belum ada –"

    # --- Ambil hashtags aktif ---
    response = supabase.table("triggered_hashtags").select("hashtag, active").execute()
    hashtags = response.data if response.data else []
    hashtags_text = "\n".join(
        [f"𔐼 `{h['hashtag']}` ({'✅ aktif' if h['active'] else '❌ nonaktif'})" for h in hashtags]
    ) if hashtags else "– Belum ada –"

    # --- Ambil commands ---
    response = supabase.table("commands").select("name, content").execute()
    commands = response.data if response.data else []
    commands_text = "\n\n".join(
        [f"*{c['name']}*\n{c['content']}" for c in commands]
    ) if commands else "– Belum ada –"

    # --- Gabungin jadi satu teks ---
    settings_text = (
        "⚙️ *Pengaturan Bot*\n\n"
        f"📌 *Required Channels:*\n{channels_text}\n\n"
        f"🏷️ *Hashtags:*\n{hashtags_text}\n\n"
        f"💻 *Commands:*\n{commands_text}"
    )

    await update.message.reply_text(settings_text, parse_mode="Markdown")

def main():
    # build application dan pasang post_init agar dijalankan setelah initialize
    application = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    # --- Command built-in ---
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('menu', menu))
    application.add_handler(CommandHandler('open', open_bot))
    application.add_handler(CommandHandler('close', close_bot))
    application.add_handler(CommandHandler('grupid', get_group_id))
    application.add_handler(CommandHandler('setrequired', set_required_channels))
    application.add_handler(CommandHandler("addhashtag", add_hashtag))
    application.add_handler(CommandHandler("removehashtag", remove_hashtag))
    application.add_handler(CommandHandler("enablehashtag", enable_hashtag))
    application.add_handler(CommandHandler("disablehashtag", disable_hashtag))
    application.add_handler(CommandHandler('broadcastfw', broadcast_forward))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CommandHandler("addcommand", add_command))
    application.add_handler(CommandHandler("deletecommand", delete_command))
    application.add_handler(CommandHandler("settings", settings))

    # --- Handlers khusus (lebih spesifik dulu) ---
    application.add_handler(MessageHandler(filters.ALL & filters.Chat(ADMIN_GROUP_ID), handle_admin_reply))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    # gunakan Chat(GROUP_ID_DISKUSI) agar pasti target grup diskusi yang benar
    application.add_handler(MessageHandler(filters.Chat(GROUP_ID_DISKUSI), handle_discussion))

    # --- Handler umum terakhir ---
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_pesan))

    logger.info("✅ Membangun bot selesai. Menjalankan polling...")

    # run polling normal — post_init(on_startup) memastikan initialize sudah dilakukan
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

if __name__ == '__main__':
    main()