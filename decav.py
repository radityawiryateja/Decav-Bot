import os
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
import json
import logging
import re
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from supabase import create_client
from dotenv import load_dotenv
from telegram.ext import ContextTypes


# Token dan Channel
load_dotenv()  # Load file .env

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Inisialisasi logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Status bot (aktif atau tidak)
bot_active = True

# Inisialisasi Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    # Simpan ke Supabase
    response = supabase.table("users").upsert([data]).execute()
    print("User saved:", response)

async def start(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Simpan user ke database
    await save_user(user_id, username)
    if await check_subscription(user_id, context):
        await update.message.reply_text("Halo! Kamu sudah subscribe channel kami. Silakan kirim pesan!")
    else:
        keyboard = [[InlineKeyboardButton("Join Channels", url=f"https://t.me/{channel[1:]}")] for channel in required_channels]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Kamu harus bergabung dengan channel berikut terlebih dahulu:", reply_markup=reply_markup)


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
        await update.message.reply_text("Kamu belum subscribe channel kami. Silakan subscribe di sini.", reply_markup=reply_markup)
        return

    # Cek apakah pesan mengandung #hunt atau 🐿 di teks atau caption media
    text_content = (update.message.text or update.message.caption or "").strip().lower()
    is_direct_forward = "#pf" in text_content or "🐿" in text_content

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
        await update.message.reply_text("Pesan kamu telah dikirim ke channel kami. Kamu dapat melihatnya melalui tombol berikut.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Pesan kamu telah dikirim, mohon tunggu beberapa saat.")

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
    
    logger.info(f"Original message: {original_message.text or original_message.caption}")
    logger.info(f"Extracted user ID: {user_id}")

    caption = f"📬 Balasan dari admin:\n\n{reply_text}" if reply_text else "📬 Balasan dari admin."

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

        await update.message.reply_text("Balasan telah dikirim.")
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        await update.message.reply_text("Gagal mengirim balasan. Pastikan pengguna masih dapat menerima pesan.")

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

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('open', open_bot))
    application.add_handler(CommandHandler('close', close_bot))
    application.add_handler(CommandHandler('grupid', get_group_id))
    application.add_handler(CommandHandler('setrequired', set_required_channels))
    application.add_handler(CommandHandler('broadcastfw', broadcast_forward))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_pesan))
    application.add_handler(MessageHandler(filters.ALL & filters.Chat(ADMIN_GROUP_ID), handle_admin_reply))


    application.run_polling()

if __name__ == '__main__':
    main()
