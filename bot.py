import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from supabase import create_client, Client
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── ENV VARS (Render me set karna) ───────────────────────────────────────────
BOT_TOKEN    = os.environ["BOT_TOKEN"]
ADMIN_ID     = int(os.environ["ADMIN_ID"])
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# ─── CHANNELS (apne channels se replace karo) ─────────────────────────────────
CHANNELS = [
    {"id": "@BLACK_DEVIL_z_x", "name": "Channel 1", "url": "https://t.me/BLACK_DEVIL_z_x"},
    {"id": "@SNYPER_DEVIL", "name": "Channel 2", "url": "https://t.me/SNYPER_DEVIL"},
    {"id": "@PAGEL_ZONE", "name": "Channel 3", "url": "https://t.me/PAGEL_ZONE"},
    {"id": "@pagel_D2", "name": "Channel 4", "url": "https://t.me/pagel_D2"},
]

REFER_REWARD = 0.50   # ₹ per refer
MIN_WITHDRAW = 10.0   # ₹
MAX_WITHDRAW = 5000.0 # ₹

# Conversation states
ASK_AMOUNT, ASK_UPI = 1, 2

# ─── Supabase ──────────────────────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ══════════════════════════════════════════════════════════════════════════════
# DB HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_user(user_id: int):
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None


def create_user(user_id: int, username: str, referred_by=None):
    supabase.table("users").insert({
        "user_id": user_id,
        "username": username or f"user_{user_id}",
        "balance": 0.0,
        "referred_by": referred_by,
        "joined_at": datetime.utcnow().isoformat()
    }).execute()


# ══════════════════════════════════════════════════════════════════════════════
# CHANNEL CHECK
# ══════════════════════════════════════════════════════════════════════════════

async def check_all_channels(bot, user_id: int) -> bool:
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(ch["id"], user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True


# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def join_keyboard():
    buttons = [[InlineKeyboardButton(f"👉 {ch['name']}", url=ch["url"])] for ch in CHANNELS]
    buttons.append([InlineKeyboardButton("✅ Maine Join Kar Liya", callback_data="check_join")])
    return InlineKeyboardMarkup(buttons)


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Refer",         callback_data="refer"),
         InlineKeyboardButton("📋 Refer List",    callback_data="refer_list")],
        [InlineKeyboardButton("💰 Check Balance", callback_data="balance"),
         InlineKeyboardButton("💸 Withdraw",      callback_data="withdraw")],
    ])


def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])


# ══════════════════════════════════════════════════════════════════════════════
# REFERRAL CREDIT
# ══════════════════════════════════════════════════════════════════════════════

async def grant_referral_credit(bot, user_id: int):
    db_user = get_user(user_id)
    if not db_user:
        return
    ref_by = db_user.get("referred_by")
    if not ref_by:
        return

    # Sirf ek baar credit milega
    existing = supabase.table("referrals") \
        .select("id").eq("referrer_id", ref_by).eq("referred_id", user_id).execute()
    if existing.data:
        return

    supabase.table("referrals").insert({
        "referrer_id": ref_by,
        "referred_id": user_id,
        "amount": REFER_REWARD,
        "created_at": datetime.utcnow().isoformat()
    }).execute()

    referrer = get_user(ref_by)
    if referrer:
        new_bal = referrer["balance"] + REFER_REWARD
        supabase.table("users").update({"balance": new_bal}).eq("user_id", ref_by).execute()
        try:
            await bot.send_message(
                ref_by,
                f"🎉 *+₹{REFER_REWARD:.2f} Mila!*\n"
                f"Aapke refer link se ek naya user join kiya!\n"
                f"💰 Naya Balance: ₹{new_bal:.2f}",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    args   = context.args
    ref_by = None

    if args and args[0].isdigit():
        ref_id = int(args[0])
        if ref_id != user.id:
            ref_by = ref_id

    db_user = get_user(user.id)
    if not db_user:
        create_user(user.id, user.username, ref_by)

    joined = await check_all_channels(context.bot, user.id)
    if not joined:
        await update.message.reply_text(
            "👋 *Welcome!*\n\nBot use karne ke liye pehle *4 channels join karo*:",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    await grant_referral_credit(context.bot, user.id)
    await update.message.reply_text(
        f"✅ *Welcome, {user.first_name}!*\n\nKya karna chahte ho?",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACK QUERY HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    # ── Check join ────────────────────────────────────────────────────────────
    if data == "check_join":
        joined = await check_all_channels(context.bot, user.id)
        if not joined:
            await query.edit_message_text(
                "❌ Saare channels join nahi kiye abhi tak!\nJoin karo phir button dabao.",
                reply_markup=join_keyboard()
            )
            return
        await grant_referral_credit(context.bot, user.id)
        await query.edit_message_text(
            f"✅ *Welcome, {user.first_name}!*\nSaare channels join ho gaye! 🎉",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return

    # ── Channel check for remaining buttons ──────────────────────────────────
    joined = await check_all_channels(context.bot, user.id)
    if not joined:
        await query.edit_message_text(
            "⚠️ Aapne channel(s) unjoin kar diye!\nDobara join karo:",
            reply_markup=join_keyboard()
        )
        return

    # ── Refer ─────────────────────────────────────────────────────────────────
    if data == "refer":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user.id}"
        db_user = get_user(user.id)
        refs = supabase.table("referrals").select("id").eq("referrer_id", user.id).execute()
        await query.edit_message_text(
            f"🔗 *Aapka Refer Link:*\n`{link}`\n\n"
            f"👥 Total Refers: *{len(refs.data)}*\n"
            f"💰 Balance: *₹{db_user['balance']:.2f}*\n\n"
            f"Har naye refer pe *₹{REFER_REWARD:.2f}* milega!\n"
            "⚠️ Dusra user saare channels join kare tab hi credit milega.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )

    # ── Refer List ────────────────────────────────────────────────────────────
    elif data == "refer_list":
        refs = supabase.table("referrals") \
            .select("referred_id, amount, created_at") \
            .eq("referrer_id", user.id) \
            .order("created_at", desc=True) \
            .execute()
        if not refs.data:
            text = "📋 *Aapka Refer List*\n\nAbhi tak koi refer nahi kiya."
        else:
            text = f"📋 *Aapka Refer List* ({len(refs.data)} users)\n\n"
            for i, r in enumerate(refs.data[:20], 1):
                date = r["created_at"][:10]
                text += f"{i}. `{r['referred_id']}` | ₹{r['amount']:.2f} | {date}\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard())

    # ── Balance ───────────────────────────────────────────────────────────────
    elif data == "balance":
        db_user = get_user(user.id)
        bal = db_user["balance"] if db_user else 0.0
        refs = supabase.table("referrals").select("id").eq("referrer_id", user.id).execute()
        await query.edit_message_text(
            f"💰 *Aapka Balance*\n\n"
            f"Balance: *₹{bal:.2f}*\n"
            f"Total Refers: *{len(refs.data)}*\n\n"
            f"Min Withdraw: ₹{MIN_WITHDRAW:.0f} | Max: ₹{MAX_WITHDRAW:.0f}",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )

    # ── Withdraw ──────────────────────────────────────────────────────────────
    elif data == "withdraw":
        db_user = get_user(user.id)
        bal = db_user["balance"] if db_user else 0.0
        if bal < MIN_WITHDRAW:
            await query.edit_message_text(
                f"❌ *Withdraw nahi ho sakta!*\n\n"
                f"Minimum balance chahiye: *₹{MIN_WITHDRAW:.0f}*\n"
                f"Aapka balance: *₹{bal:.2f}*\n\n"
                f"Aur refer karo aur balance badhao! 🔗",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return
        context.user_data["state"] = ASK_AMOUNT
        context.user_data["withdraw_bal"] = bal
        await query.edit_message_text(
            f"💸 *Withdraw Request*\n\n"
            f"Aapka Balance: ₹{bal:.2f}\n"
            f"Min: ₹{MIN_WITHDRAW:.0f} | Max: ₹{MAX_WITHDRAW:.0f}\n\n"
            "Kitna withdraw karna hai? *Amount bhejo* (sirf number):",
            parse_mode="Markdown"
        )

    # ── Back ──────────────────────────────────────────────────────────────────
    elif data == "back_main":
        await query.edit_message_text(
            "📌 *Main Menu*", parse_mode="Markdown", reply_markup=main_keyboard()
        )

    # ── Admin: Approve ────────────────────────────────────────────────────────
    elif data.startswith("approve_"):
        if user.id != ADMIN_ID:
            await query.answer("❌ Permission nahi!", show_alert=True)
            return
        wd_id = int(data.split("_")[1])
        wd    = supabase.table("withdrawals").select("*").eq("id", wd_id).execute().data
        if not wd or wd[0]["status"] != "pending":
            await query.answer("Already processed!", show_alert=True)
            return
        wd = wd[0]
        supabase.table("withdrawals").update({"status": "approved"}).eq("id", wd_id).execute()
        await context.bot.send_message(
            wd["user_id"],
            f"✅ *Withdraw Successful!*\n\n"
            f"💰 Amount: ₹{wd['amount']:.2f}\n"
            f"📱 UPI: `{wd['upi_id']}`\n\n"
            "Payment process ho gayi! Thank you. 🎉",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"✅ *Approved!*\nRequest #{wd_id} | User `{wd['user_id']}` | ₹{wd['amount']:.2f}",
            parse_mode="Markdown"
        )

    # ── Admin: Cancel & Refund ────────────────────────────────────────────────
    elif data.startswith("cancel_"):
        if user.id != ADMIN_ID:
            await query.answer("❌ Permission nahi!", show_alert=True)
            return
        wd_id = int(data.split("_")[1])
        wd    = supabase.table("withdrawals").select("*").eq("id", wd_id).execute().data
        if not wd or wd[0]["status"] != "pending":
            await query.answer("Already processed!", show_alert=True)
            return
        wd = wd[0]
        supabase.table("withdrawals").update({"status": "cancelled"}).eq("id", wd_id).execute()
        # Refund
        db_user = get_user(wd["user_id"])
        if db_user:
            new_bal = db_user["balance"] + wd["amount"]
            supabase.table("users").update({"balance": new_bal}).eq("user_id", wd["user_id"]).execute()
        await context.bot.send_message(
            wd["user_id"],
            f"❌ *Aapka Withdraw Cancel Ho Gaya!*\n\n"
            f"💰 Amount: ₹{wd['amount']:.2f} *refund* ho gaya aapke balance mein.\n\n"
            "Koi problem ho to admin se contact karo.",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"❌ *Cancelled & Refunded!*\nRequest #{wd_id} | User `{wd['user_id']}` | ₹{wd['amount']:.2f} refund ho gaya.",
            parse_mode="Markdown"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TEXT MESSAGE HANDLER (Withdraw conversation)
# ══════════════════════════════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    state = context.user_data.get("state")
    text  = update.message.text.strip()

    if state == ASK_AMOUNT:
        try:
            amount = float(text)
        except ValueError:
            await update.message.reply_text("❌ Sirf number bhejo! Jaise: 50")
            return
        bal = context.user_data.get("withdraw_bal", 0)
        if amount < MIN_WITHDRAW or amount > MAX_WITHDRAW:
            await update.message.reply_text(
                f"❌ Amount ₹{MIN_WITHDRAW:.0f} se ₹{MAX_WITHDRAW:.0f} ke beech honi chahiye!"
            )
            return
        if amount > bal:
            await update.message.reply_text(f"❌ Aapke paas sirf ₹{bal:.2f} hai!")
            return
        context.user_data["withdraw_amount"] = amount
        context.user_data["state"] = ASK_UPI
        await update.message.reply_text(
            f"✅ Amount: ₹{amount:.2f}\n\nAb apna *UPI ID* bhejo:\n(Jaise: name@paytm, 9999999999@upi)",
            parse_mode="Markdown"
        )

    elif state == ASK_UPI:
        upi = text
        if "@" not in upi or len(upi) < 5:
            await update.message.reply_text("❌ Valid UPI ID bhejo! Jaise: name@paytm")
            return

        amount  = context.user_data["withdraw_amount"]
        db_user = get_user(user.id)
        if not db_user or db_user["balance"] < amount:
            await update.message.reply_text("❌ Balance nahi hai!")
            context.user_data.clear()
            return

        new_bal = db_user["balance"] - amount
        supabase.table("users").update({"balance": new_bal}).eq("user_id", user.id).execute()

        res = supabase.table("withdrawals").insert({
            "user_id":    user.id,
            "username":   user.username or f"user_{user.id}",
            "amount":     amount,
            "upi_id":     upi,
            "status":     "pending",
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        wd_id = res.data[0]["id"]

        await update.message.reply_text(
            f"✅ *Withdraw Request Submit!*\n\n"
            f"💰 Amount: ₹{amount:.2f}\n"
            f"📱 UPI: `{upi}`\n"
            f"📊 Bacha Balance: ₹{new_bal:.2f}\n\n"
            "Admin jald process karega. ⏳",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

        # Admin ko notify
        admin_text = (
            f"💸 *Naya Withdraw Request!*\n\n"
            f"🆔 ID: #{wd_id}\n"
            f"👤 @{user.username or 'N/A'} (`{user.id}`)\n"
            f"💰 Amount: ₹{amount:.2f}\n"
            f"📱 UPI: `{upi}`\n"
            f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
        )
        admin_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approved",        callback_data=f"approve_{wd_id}"),
            InlineKeyboardButton("❌ Cancel & Refund", callback_data=f"cancel_{wd_id}")
        ]])
        try:
            await context.bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=admin_kb)
        except Exception as e:
            logger.error(f"Admin notify error: {e}")

        context.user_data.clear()
    else:
        # Default response
        joined = await check_all_channels(context.bot, user.id)
        if joined:
            await update.message.reply_text("Menu:", reply_markup=main_keyboard())


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    pending = supabase.table("withdrawals") \
        .select("*").eq("status", "pending") \
        .order("created_at", desc=True).execute()
    if not pending.data:
        await update.message.reply_text("✅ Koi pending request nahi.")
        return
    for wd in pending.data[:10]:
        text = (
            f"💸 *Request #{wd['id']}*\n"
            f"👤 @{wd['username']} (`{wd['user_id']}`)\n"
            f"💰 ₹{wd['amount']:.2f} | UPI: `{wd['upi_id']}`\n"
            f"⏰ {wd['created_at'][:16]}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approved",        callback_data=f"approve_{wd['id']}"),
            InlineKeyboardButton("❌ Cancel & Refund", callback_data=f"cancel_{wd['id']}")
        ]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def admin_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /userinfo <user_id>")
        return
    uid     = int(context.args[0])
    db_user = get_user(uid)
    if not db_user:
        await update.message.reply_text("User nahi mila!")
        return
    refs = supabase.table("referrals").select("*").eq("referrer_id", uid).execute()
    text = (
        f"👤 *User Info*\n"
        f"ID: `{uid}`\n"
        f"Username: @{db_user['username']}\n"
        f"💰 Balance: ₹{db_user['balance']:.2f}\n"
        f"👥 Total Refers: {len(refs.data)}\n"
        f"📅 Joined: {db_user['joined_at'][:10]}\n"
    )
    if refs.data:
        text += "\n📋 *Recent Refers:*\n"
        for i, r in enumerate(refs.data[:10], 1):
            text += f"{i}. `{r['referred_id']}` | ₹{r['amount']:.2f} | {r['created_at'][:10]}\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users    = supabase.table("users").select("user_id", count="exact").execute()
    total_refs     = supabase.table("referrals").select("id", count="exact").execute()
    pending_wd     = supabase.table("withdrawals").select("id", count="exact").eq("status", "pending").execute()
    approved_wd    = supabase.table("withdrawals").select("amount").eq("status", "approved").execute()
    total_paid_out = sum(w["amount"] for w in approved_wd.data) if approved_wd.data else 0
    await update.message.reply_text(
        f"📊 *Bot Stats*\n\n"
        f"👥 Total Users: {total_users.count}\n"
        f"🔗 Total Refers: {total_refs.count}\n"
        f"⏳ Pending Withdrawals: {pending_wd.count}\n"
        f"💸 Total Paid Out: ₹{total_paid_out:.2f}",
        parse_mode="Markdown"
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("withdrawals", admin_withdrawals))
    app.add_handler(CommandHandler("userinfo",    admin_userinfo))
    app.add_handler(CommandHandler("stats",       admin_stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    logger.info("✅ Bot chal raha hai...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
