import os
import json
import shutil
import threading
from pathlib import Path

from flask import Flask, jsonify
import discord
from discord.ext import commands

# =========================
# RENDER / DOSYA AYARLARI
# =========================

# Render'da persistent disk mount path'in buysa bunu kullan:
# /var/data
# İstersen Render env'e RENDER_DISK_MOUNT_PATH ekleyebilirsin.
DATA_DIR = os.getenv("RENDER_DISK_MOUNT_PATH", "/var/data")
SETTINGS_FILE = Path(DATA_DIR) / "settings.json"

# Repoda varsayılan bir settings.json varsa ilk açılışta buradan kopyalanır
DEFAULT_SETTINGS_FILE = Path("settings.json")

def ensure_settings_file():
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not SETTINGS_FILE.exists():
        if DEFAULT_SETTINGS_FILE.exists():
            shutil.copy(DEFAULT_SETTINGS_FILE, SETTINGS_FILE)
            print(f"[OK] Varsayılan settings dosyası kopyalandı -> {SETTINGS_FILE}")
        else:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=4)
            print(f"[OK] Yeni boş settings dosyası oluşturuldu -> {SETTINGS_FILE}")

def load_settings():
    ensure_settings_file()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("[HATA] settings.json bozuk. Boş veri ile devam ediliyor.")
        return {}
    except Exception as e:
        print(f"[HATA] Settings yüklenemedi: {e}")
        return {}

def save_settings(data):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_guild_settings(guild_id: int):
    global settings
    gid = str(guild_id)

    if gid not in settings:
        settings[gid] = {
            "partner_channel": None,
            "log_channel": None,
            "warn_limit": 3,
            "warnings": {},
            "afk_users": {},
            "ticket_category": None
        }
        save_settings(settings)

    return settings[gid]

# İlk yükleme
settings = load_settings()

# =========================
# DISCORD BOT AYARLARI
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "!")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable bulunamadı.")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f"[BOT] Giriş yapıldı: {bot.user}")
    print(f"[BOT] Settings dosya yolu: {SETTINGS_FILE}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel):
    guild_data = get_guild_settings(ctx.guild.id)
    guild_data["log_channel"] = channel.id
    save_settings(settings)
    await ctx.send(f"Log kanalı ayarlandı: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setpartner(ctx, channel: discord.TextChannel):
    guild_data = get_guild_settings(ctx.guild.id)
    guild_data["partner_channel"] = channel.id
    save_settings(settings)
    await ctx.send(f"Partner kanalı ayarlandı: {channel.mention}")

@bot.command()
async def settingsgoster(ctx):
    guild_data = get_guild_settings(ctx.guild.id)
    await ctx.send(
        f"Sunucu ayarları:\n"
        f"- log_channel: {guild_data.get('log_channel')}\n"
        f"- partner_channel: {guild_data.get('partner_channel')}\n"
        f"- warn_limit: {guild_data.get('warn_limit')}\n"
        f"- ticket_category: {guild_data.get('ticket_category')}"
    )

@bot.command()
@commands.has_permissions(administrator=True)
async def warnlimit(ctx, sayı: int):
    guild_data = get_guild_settings(ctx.guild.id)
    guild_data["warn_limit"] = sayı
    save_settings(settings)
    await ctx.send(f"Uyarı limiti {sayı} olarak ayarlandı.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="Sebep belirtilmedi"):
    guild_data = get_guild_settings(ctx.guild.id)
    warnings = guild_data.setdefault("warnings", {})

    user_id = str(member.id)
    if user_id not in warnings:
        warnings[user_id] = []

    warnings[user_id].append(reason)
    save_settings(settings)

    warn_count = len(warnings[user_id])
    warn_limit_value = guild_data.get("warn_limit", 3)

    await ctx.send(f"{member.mention} uyarıldı. Toplam uyarı: {warn_count}/{warn_limit_value}")

    log_channel_id = guild_data.get("log_channel")
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            await log_channel.send(
                f"{member.mention} uyarıldı.\n"
                f"Sebep: {reason}\n"
                f"Toplam: {warn_count}/{warn_limit_value}"
            )

@bot.command()
async def warnings(ctx, member: discord.Member = None):
    guild_data = get_guild_settings(ctx.guild.id)
    warnings = guild_data.setdefault("warnings", {})

    target = member or ctx.author
    user_warnings = warnings.get(str(target.id), [])

    if not user_warnings:
        await ctx.send(f"{target.mention} için uyarı bulunamadı.")
        return

    text = "\n".join([f"{i+1}. {w}" for i, w in enumerate(user_warnings)])
    await ctx.send(f"{target.mention} uyarıları:\n{text}")

@bot.command()
async def afk(ctx, *, reason="AFK"):
    guild_data = get_guild_settings(ctx.guild.id)
    afk_users = guild_data.setdefault("afk_users", {})

    afk_users[str(ctx.author.id)] = reason
    save_settings(settings)

    await ctx.send(f"{ctx.author.mention} artık AFK: {reason}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.guild:
        guild_data = get_guild_settings(message.guild.id)
        afk_users = guild_data.setdefault("afk_users", {})

        # AFK'den çıkar
        if str(message.author.id) in afk_users:
            del afk_users[str(message.author.id)]
            save_settings(settings)
            await message.channel.send(f"{message.author.mention}, artık AFK değilsin.")

        # Mentionlenen AFK kullanıcıları kontrol et
        for member in message.mentions:
            if str(member.id) in afk_users:
                await message.channel.send(
                    f"{member.mention} şu anda AFK: {afk_users[str(member.id)]}"
                )

    await bot.process_commands(message)

# =========================
# FLASK APP
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot çalışıyor."

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "bot_user": str(bot.user) if bot.user else None,
        "settings_file": str(SETTINGS_FILE),
        "settings_exists": SETTINGS_FILE.exists()
    })

# =========================
# BOT THREAD
# =========================

def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
