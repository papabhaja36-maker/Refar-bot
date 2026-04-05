import os
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN    = os.environ["BOT_TOKEN"]
ADMIN_ID     = int(os.environ["ADMIN_ID"])
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

CHANNELS = [
    {"id": "@BLACK_DEVIL_z_x", "name": "Channel 1", "url": "https://t.me/BLACK_DEVIL_z_x"},
    {"id": "@SNYPER_DEVIL", "name": "Channel 2", "url": "https://t.me/SNYPER_DEVIL"},
    {"id": "@PAGEL_ZONE", "name": "Channel 3", "url": "https://t.me/PAGEL_ZONE"},
    {"id": "@pagel_D2", "name": "Channel 4", "url": "https://t.me/pagel_D2"},
]

REFER_REWARD = 0.50
MIN_WITHDRAW = 10.0
MAX_WITHDRAW = 5000.0
ASK_AMOUNT, ASK_UPI = 1, 2

def get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def db_get(table, filters=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*"
    if filters:
        for k, v in filters.items():
            url += f"&{k}=eq.{v}"
    r = httpx.get(url, headers=get_headers())
    return r.json() if r.status_code == 200 else []

def db_insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = httpx.post(url, headers=get_headers(), json=data)
    return r.json() if r.status_code in (200, 201) else []

def db_update(table, filters, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?"
    for k, v in filters.items():
        url += f"{k}=eq.{v}&"
    url = url.rstrip("&")
    r = httpx.patch(url, headers=get_headers(), json=data)
    return r.status_code in (200, 204)

def get_user(user_id):
    res = db_get("users", {"user_id": user_id})
    return res[0] if res else None

def create_user(user_id, username, referred_by=None):
    db_insert("users", {
        "user_id": user_id,
        "username": username or f"user_{user_id}",
        "balance": 0.0,
        "referred_by": referred_by,
        "joined_at": datetime.utcnow().isoformat()
    })

async def check_all_channels(bot, user_id):
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(ch["id"], user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True

def join_keyboard():
    buttons = [[InlineKeyboardButton(f"👉 {ch['name']}", url=ch["url"])] for ch in CHANNELS]
    buttons.append([InlineKeyboardButton("✅ Maine Join Kar Liya", callback_data="check_join")])
    return InlineKeyboardMarkup(buttons)

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Refer", callback_data="refer"),
         InlineKeyboardButton("📋 Refer List", callback_data="refer_list")],
        [InlineKeyboardButton("💰 Check Balance", callback_data="balance"),
         InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
    ])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])

async def grant_referral_credit(bot, user_id):
    db_user = get_user(user_id)
    if not db_user:
        return
    ref_by = db_user.get("referred_by")
    if not ref_by:
        return
    existing = db_get("referrals", {"referrer_id": ref_by, "referred_id": user_id})
    if existing:
        return
    db_insert("referrals", {
        "referrer_id": ref_by,
        "referred_id": user_id,
        "amount": REFER_REWARD,
        "created_at": datetime.utcnow().isoformat()
    })
    referrer = get_user(ref_by)
    if referrer:
        new_bal = referrer["balance"] + REFER_REWARD
        db_update("users", {"user_id": ref_by}, {"balance": new_bal})
        try:
            await bot.send_message(ref_by,
                f"🎉 *+₹{REFER_REWARD:.2f} Mila!*\nAapke refer link se naya user join kiya!\n💰 Naya Balance: ₹{new_bal:.2f}",
                parse_mode="Markdown")
        except Exception:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_by = None
    if args and args[0].isdigit():
        ref_id = int(args[0])
        if ref_id != user.id:
            ref_by = ref_id
    if not get_user(user.id):
        create_user(user.id, user.username, ref_by)
    joined = await check_all_channels(context.bot, user.id)
    if not joined:
        await update.message.reply_text(
            "👋 *Welcome!*\n\nBot use karne ke liye pehle *4 channels join karo*:",
            parse_mode="Markdown", reply_markup=join_keyboard())
        return
    await grant_referral_credit(context.bot, user.id)
    await update.message.reply_text(
        f"✅ *Welcome, {user.first_name}!*\n\nKya karna chahte ho?",
        parse_mode="Markdown", reply_markup=main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "check_join":
        joined = await check_all_channels(context.bot, user.id)
        if not joined:
            await query.edit_message_text("❌ Saare channels join nahi kiye!\nJoin karo phir button dabao.", reply_markup=join_keyboard())
            return
        await grant_referral_credit(context.bot, user.id)
        await query.edit_message_text(f"✅ *Welcome, {user.first_name}!*\nSaare channels join ho gaye! 🎉",
            parse_mode="Markdown", reply_markup=main_keyboard())
        return

    joined = await check_all_channels(context.bot, user.id)
    if not joined:
        await query.edit_message_text("⚠️ Aapne channel(s) unjoin kar diye!\nDobara join karo:", reply_markup=join_keyboard())
        return

    if data == "refer":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user.id}"
        db_user = get_user(user.id)
        refs = db_get("referrals", {"referrer_id": user.id})
        await query.edit_message_text(
            f"🔗 *Aapka Refer Link:*\n`{link}`\n\n👥 Total Refers: *{len(refs)}*\n💰 Balance: *₹{db_user['balance']:.2f}*\n\nHar naye refer pe *₹{REFER_REWARD:.2f}* milega!",
            parse_mode="Markdown", reply_markup=back_keyboard())

    elif data == "refer_list":
        refs = db_get("referrals", {"referrer_id": user.id})
        if not refs:
            text = "📋 *Aapka Refer List*\n\nAbhi tak koi refer nahi kiya."
        else:
            text = f"📋 *Aapka Refer List* ({len(refs)} users)\n\n"
            for i, r in enumerate(refs[:20], 1):
                text += f"{i}. `{r['referred_id']}` | ₹{r['amount']:.2f} | {r['created_at'][:10]}\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard())

    elif data == "balance":
        db_user = get_user(user.id)
        bal = db_user["balance"] if db_user else 0.0
        refs = db_get("referrals", {"referrer_id": user.id})
        await query.edit_message_text(
            f"💰 *Aapka Balance*\n\nBalance: *₹{bal:.2f}*\nTotal Refers: *{len(refs)}*\n\nMin Withdraw: ₹{MIN_WITHDRAW:.0f} | Max: ₹{MAX_WITHDRAW:.0f}",
            parse_mode="Markdown", reply_markup=back_keyboard())

    elif data == "withdraw":
        db_user = get_user(user.id)
        bal = db_user["balance"] if db_user else 0.0
        if bal < MIN_WITHDRAW:
            await query.edit_message_text(
                f"❌ *Withdraw nahi ho sakta!*\n\nMinimum: *₹{MIN_WITHDRAW:.0f}*\nAapka balance: *₹{bal:.2f}*",
                parse_mode="Markdown", reply_markup=back_keyboard())
            return
        context.user_data["state"] = ASK_AMOUNT
        context.user_data["withdraw_bal"] = bal
        await query.edit_message_text(
            f"💸 *Withdraw Request*\n\nBalance: ₹{bal:.2f}\nMin: ₹{MIN_WITHDRAW:.0f} | Max: ₹{MAX_WITHDRAW:.0f}\n\nKitna withdraw karna hai? *Sirf number bhejo:*",
            parse_mode="Markdown")

    elif data == "back_main":
        await query.edit_message_text("📌 *Main Menu*", parse_mode="Markdown", reply_markup=main_keyboard())

    elif data.startswith("approve_"):
        if user.id != ADMIN_ID:
            await query.answer("❌ Permission nahi!", show_alert=True)
            return
        wd_id = int(data.split("_")[1])
        wd = db_get("withdrawals", {"id": wd_id})
        if not wd or wd[0]["status"] != "pending":
            await query.answer("Already processed!", show_alert=True)
            return
        wd = wd[0]
        db_update("withdrawals", {"id": wd_id}, {"status": "approved"})
        try:
            await context.bot.send_message(wd["user_id"],
                f"✅ *Withdraw Successful!*\n\n💰 Amount: ₹{wd['amount']:.2f}\n📱 UPI: `{wd['upi_id']}`\n\nPayment process ho gayi! 🎉",
                parse_mode="Markdown")
        except Exception:
            pass
        await query.edit_message_text(f"✅ *Approved!* Request #{wd_id} | ₹{wd['amount']:.2f}", parse_mode="Markdown")

    elif data.startswith("cancel_"):
        if user.id != ADMIN_ID:
            await query.answer("❌ Permission nahi!", show_alert=True)
            return
        wd_id = int(data.split("_")[1])
        wd = db_get("withdrawals", {"id": wd_id})
        if not wd or wd[0]["status"] != "pending":
            await query.answer("Already processed!", show_alert=True)
            return
        wd = wd[0]
        db_update("withdrawals", {"id": wd_id}, {"status": "cancelled"})
        db_user = get_user(wd["user_id"])
        if db_user:
            db_update("users", {"user_id": wd["user_id"]}, {"balance": db_user["balance"] + wd["amount"]})
        try:
            await context.bot.send_message(wd["user_id"],
                f"❌ *Withdraw Cancel Ho Gaya!*\n\n💰 ₹{wd['amount']:.2f} refund ho gaya aapke balance mein.",
                parse_mode="Markdown")
        except Exception:
            pass
        await query.edit_message_text(f"❌ *Cancelled & Refunded!* Request #{wd_id} | ₹{wd['amount']:.2f}", parse_mode="Markdown")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = context.user_data.get("state")
    text = update.message.text.strip()

    if state == ASK_AMOUNT:
        try:
            amount = float(text)
        except ValueError:
            await update.message.reply_text("❌ Sirf number bhejo! Jaise: 50")
            return
        bal = context.user_data.get("withdraw_bal", 0)
        if amount < MIN_WITHDRAW or amount > MAX_WITHDRAW:
            await update.message.reply_text(f"❌ Amount ₹{MIN_WITHDRAW:.0f} se ₹{MAX_WITHDRAW:.0f} ke beech honi chahiye!")
            return
        if amount > bal:
            await update.message.reply_text(f"❌ Aapke paas sirf ₹{bal:.2f} hai!")
            return
        context.user_data["withdraw_amount"] = amount
        context.user_data["state"] = ASK_UPI
        await update.message.reply_text(
            f"✅ Amount: ₹{amount:.2f}\n\nAb apna *UPI ID* bhejo:\n(Jaise: name@paytm)",
            parse_mode="Markdown")

    elif state == ASK_UPI:
        upi = text
        if "@" not in upi or len(upi) < 5:
            await update.message.reply_text("❌ Valid UPI ID bhejo! Jaise: name@paytm")
            return
        amount = context.user_data["withdraw_amount"]
        db_user = get_user(user.id)
        if not db_user or db_user["balance"] < amount:
            await update.message.reply_text("❌ Balance nahi hai!")
            context.user_data.clear()
            return
        new_bal = db_user["balance"] - amount
        db_update("users", {"user_id": user.id}, {"balance": new_bal})
        res = db_insert("withdrawals", {
            "user_id": user.id,
            "username": user.username or f"user_{user.id}",
            "amount": amount,
            "upi_id": upi,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        })
        wd_id = res[0]["id"] if res else "?"
        await update.message.reply_text(
            f"✅ *Withdraw Request Submit!*\n\n💰 Amount: ₹{amount:.2f}\n📱 UPI: `{upi}`\n📊 Bacha Balance: ₹{new_bal:.2f}\n\nAdmin jald process karega. ⏳",
            parse_mode="Markdown", reply_markup=main_keyboard())
        try:
            await context.bot.send_message(ADMIN_ID,
                f"💸 *Naya Withdraw!*\n🆔 #{wd_id}\n👤 @{user.username or 'N/A'} (`{user.id}`)\n💰 ₹{amount:.2f}\n📱 `{upi}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Approved", callback_data=f"approve_{wd_id}"),
                    InlineKeyboardButton("❌ Cancel & Refund", callback_data=f"cancel_{wd_id}")
                ]]))
        except Exception as e:
            logger.error(f"Admin notify: {e}")
        context.user_data.clear()
    else:
        joined = await check_all_channels(context.bot, user.id)
        if joined:
            await update.message.reply_text("📌 Menu:", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("⚠️ Pehle channels join karo:", reply_markup=join_keyboard())

async def admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    pending = db_get("withdrawals", {"status": "pending"})
    if not pending:
        await update.message.reply_text("✅ Koi pending request nahi.")
        return
    for wd in pending[:10]:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approved", callback_data=f"approve_{wd['id']}"),
            InlineKeyboardButton("❌ Cancel & Refund", callback_data=f"cancel_{wd['id']}")
        ]])
        await update.message.reply_text(
            f"💸 *Request #{wd['id']}*\n👤 @{wd['username']} (`{wd['user_id']}`)\n💰 ₹{wd['amount']:.2f} | UPI: `{wd['upi_id']}`",
            parse_mode="Markdown", reply_markup=kb)

async def admin_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /userinfo <user_id>")
        return
    uid = int(context.args[0])
    db_user = get_user(uid)
    if not db_user:
        await update.message.reply_text("User nahi mila!")
        return
    refs = db_get("referrals", {"referrer_id": uid})
    text = f"👤 *User Info*\nID: `{uid}`\nUsername: @{db_user['username']}\n💰 Balance: ₹{db_user['balance']:.2f}\n👥 Refers: {len(refs)}\n📅 Joined: {db_user['joined_at'][:10]}"
    if refs:
        text += "\n\n📋 *Refers:*\n"
        for i, r in enumerate(refs[:10], 1):
            text += f"{i}. `{r['referred_id']}` | ₹{r['amount']:.2f}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = db_get("users")
    refs = db_get("referrals")
    pending = db_get("withdrawals", {"status": "pending"})
    approved = db_get("withdrawals", {"status": "approved"})
    paid = sum(w["amount"] for w in approved) if approved else 0
    await update.message.reply_text(
        f"📊 *Bot Stats*\n\n👥 Users: {len(users)}\n🔗 Refers: {len(refs)}\n⏳ Pending: {len(pending)}\n💸 Paid Out: ₹{paid:.2f}",
        parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("withdrawals", admin_withdrawals))
    app.add_handler(CommandHandler("userinfo", admin_userinfo))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    logger.info("✅ Bot chal raha hai...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
