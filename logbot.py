"""
Discord Log Botu - discord.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kanal ID'lerini kod içine yazmak gerekmez!
Tüm ayarlar Discord komutlarıyla yapılır ve
settings.json dosyasına otomatik kaydedilir.

Gereksinimler:
    pip install discord.py

Komutlar (Slash komutları):
    /log-kur <tür> <kanal>     → Belirli bir log türü için kanal atar
    /log-kaldır <tür>          → Belirli bir log türünü devre dışı bırakır
    /log-durum                 → Tüm log kanallarını listeler
    /log-sifirla               → Tüm ayarları siler
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import asyncio
import json
import os
from flask import Flask
from threading import Thread

# ─────────────────────────────────────────
#  AYARLAR
# ─────────────────────────────────────────

# Token environment variable'dan okunur
# Render: Dashboard → Environment → BOT_TOKEN ekle
# Lokal:  export BOT_TOKEN="token_buraya"  (Linux/Mac)
#         set BOT_TOKEN=token_buraya       (Windows)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable ayarlanmamis! Render'da Environment sekmesine ekle.")
AYAR_DOSYASI = "settings.json"      # Kanal ID'leri burada saklanır

# ─────────────────────────────────────────
#  SABİT LOG KANALLARI (deploy'dan etkilenmez)
#  Kod güncellendiğinde settings.json silinse bile
#  bu ID'ler otomatik olarak yeniden yüklenir.
# ─────────────────────────────────────────
DEFAULT_LOG_KANALLARI = {
    "ban_log":     1484564146111647917,
    "mute_log":    1484564329549267104,
    "mod_log":     1484564481257508874,
    "rol_log":     1484564569446944949,
    "mesaj_log":   1484564647704137879,
    "kanal_log":   1484565700969496606,
    "ses_log":     1484564774648938496,
    "davet_log":   1484564912486355106,
}

# ── Sabit Log Kanalları ──────────────────────────────────────────
# Bu kanallar her deploy sonrası otomatik yüklenir.
# Değiştirmek istersen buradan düzenle.
VARSAYILAN_LOG_KANALLARI = {
    "ban_log":     1484564146111647917,
    "mute_log":    1484564329549267104,
    "mod_log":     1484564481257508874,
    "rol_log":     1484564569446944949,
    "mesaj_log":   1484564647704137879,
    "kanal_log":   1484565700969496606,
    "ses_log":     1484564774648938496,
    "davet_log":   1484564912486355106,
}

# Desteklenen log türleri ve açıklamaları
LOG_TURLERI = {
    "ban_log":      "🔨 Ban / Unban logları",
    "mute_log":     "🔇 Mute logları",
    "mod_log":      "🛡️ Genel moderasyon logları",
    "rol_log":      "🎭 Rol değişiklik logları",
    "mesaj_log":    "✉️ Mesaj silme/düzenleme logları",
    "giris_cikis":  "🚪 Üye giriş/çıkış logları",
    "ses_log":      "🔊 Ses kanalı logları",
    "kanal_log":    "📁 Kanal oluşturma/silme logları",
    "davet_log":    "✉️ Davet logları",
}

# Embed renk paleti
RENKLER = {
    "ban":    0xE74C3C,
    "mute":   0xE67E22,
    "unban":  0x2ECC71,
    "rol":    0x9B59B6,
    "izin":   0x3498DB,
    "mesaj":  0xF39C12,
    "giris":  0x1ABC9C,
    "cikis":  0x95A5A6,
    "ses":    0x16A085,
    "bilgi":  0x7F8C8D,
    "basari": 0x2ECC71,
    "hata":   0xE74C3C,
}

# ─────────────────────────────────────────
#  AYAR YÖNETİMİ (settings.json)
# ─────────────────────────────────────────

def ayarlari_yukle() -> dict:
    """
    settings.json dosyasını okur.
    Yapı: { "guild_id": { "log_turu": kanal_id, ... }, ... }
    Dosya yoksa boş dict döndürür.
    """
    if not os.path.exists(AYAR_DOSYASI):
        return {}
    with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
        return json.load(f)


def varsayilan_kanallari_yukle(guild_id: int):
    """
    Varsayılan log kanallarını settings.json'a yazar.
    Her bot başlangıcında çağrılır — mevcut ayarların üzerine yazmaz,
    sadece eksik olanları tamamlar.
    """
    ayarlar = ayarlari_yukle()
    gk = str(guild_id)
    if gk not in ayarlar:
        ayarlar[gk] = {}
    degisti = False
    for tur, kanal_id in VARSAYILAN_LOG_KANALLARI.items():
        if tur not in ayarlar[gk]:
            ayarlar[gk][tur] = kanal_id
            degisti = True
    if degisti:
        ayarlari_kaydet(ayarlar)


def ayarlari_kaydet(veri: dict):
    """Tüm ayarları settings.json dosyasına yazar."""
    with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(veri, f, indent=2, ensure_ascii=False)


def kanal_al(guild_id: int, tur: str) -> int | None:
    """
    Belirli bir sunucu ve log türü için kayıtlı kanal ID'sini döndürür.
    Kayıtlı değilse None döndürür.
    """
    ayarlar = ayarlari_yukle()
    return ayarlar.get(str(guild_id), {}).get(tur)


def kanal_kaydet(guild_id: int, tur: str, kanal_id: int):
    """Bir log türü için kanal ID'sini settings.json'a kaydeder."""
    ayarlar = ayarlari_yukle()
    guild_key = str(guild_id)
    if guild_key not in ayarlar:
        ayarlar[guild_key] = {}
    ayarlar[guild_key][tur] = kanal_id
    ayarlari_kaydet(ayarlar)


def kanal_sil(guild_id: int, tur: str):
    """Bir log türünün kanal kaydını siler (devre dışı bırakır)."""
    ayarlar = ayarlari_yukle()
    guild_key = str(guild_id)
    if guild_key in ayarlar and tur in ayarlar[guild_key]:
        del ayarlar[guild_key][tur]
        ayarlari_kaydet(ayarlar)


def guild_ayarlari_sil(guild_id: int):
    """Bir sunucunun tüm log ayarlarını tamamen siler."""
    ayarlar = ayarlari_yukle()
    guild_key = str(guild_id)
    if guild_key in ayarlar:
        del ayarlar[guild_key]
        ayarlari_kaydet(ayarlar)


# ─────────────────────────────────────────
#  BOT KURULUMU
# ─────────────────────────────────────────

intents = discord.Intents.default()
intents.guilds          = True
intents.members         = True
intents.bans            = True
intents.message_content = True
intents.messages        = True
intents.voice_states    = True
intents.invites         = True

bot = commands.Bot(command_prefix=".", intents=intents, case_insensitive=True, help_command=None)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Bilinmeyen komutları sessizce geç


# ─────────────────────────────────────────
#  YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────

async def log_gonder(guild: discord.Guild, tur: str, embed: discord.Embed):
    """
    settings.json'dan ilgili log kanalını bulup embed gönderir.
    Kanal ayarlanmamışsa veya bulunamazsa sessizce geçer.
    """
    kanal_id = kanal_al(guild.id, tur)
    if not kanal_id:
        return  # Bu log türü için kanal ayarlanmamış

    kanal = guild.get_channel(kanal_id)
    if not kanal:
        return  # Kanal daha sonra silinmiş olabilir

    try:
        await kanal.send(embed=embed)
    except discord.Forbidden:
        print(f"[HATA] '{tur}' kanalına yazma izni yok.")
    except discord.HTTPException as e:
        print(f"[HATA] Log gönderilemedi: {e}")


def zaman_damgasi() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("📅 %d.%m.%Y — ⏰ %H:%M:%S UTC")


async def audit_log_bul(guild: discord.Guild, eylem: discord.AuditLogAction, hedef=None):
    """Audit log üzerinden en son işlemi yapan kişiyi bulur."""
    try:
        async for log in guild.audit_logs(limit=5, action=eylem):
            if hedef is None or log.target.id == hedef.id:
                return log.user
    except discord.Forbidden:
        pass
    return None


def izin_adi_getir(perm_adi: str) -> str:
    """İngilizce izin adını Türkçeye çevirir. Bilinmeyenler aynen döndürülür."""
    ceviriler = {
        "administrator":            "⚡ Yönetici",
        "manage_guild":             "🏠 Sunucuyu Yönet",
        "manage_roles":             "🎭 Rolleri Yönet",
        "manage_channels":          "📁 Kanalları Yönet",
        "manage_messages":          "✉️ Mesajları Yönet",
        "manage_nicknames":         "✏️ Takma Adları Yönet",
        "manage_webhooks":          "🔗 Webhook'ları Yönet",
        "manage_expressions":       "😄 İfadeleri Yönet",
        "manage_threads":           "🧵 Konuları Yönet",
        "kick_members":             "👢 Üye At",
        "ban_members":              "🔨 Üye Banla",
        "moderate_members":         "🔇 Üyeleri Sustur",
        "view_audit_log":           "📋 Denetim Günlüğünü Gör",
        "view_guild_insights":      "📊 Sunucu İçgörülerini Gör",
        "send_messages":            "💬 Mesaj Gönder",
        "send_tts_messages":        "🔊 TTS Mesajı Gönder",
        "embed_links":              "🔗 Link Önizlemesi",
        "attach_files":             "📎 Dosya Ekle",
        "read_message_history":     "📜 Mesaj Geçmişini Oku",
        "mention_everyone":         "📣 @everyone Etiketle",
        "use_external_emojis":      "😎 Harici Emoji Kullan",
        "use_external_stickers":    "🖼️ Harici Çıkartma Kullan",
        "add_reactions":            "👍 Tepki Ekle",
        "use_slash_commands":       "🤖 Slash Komutlarını Kullan",
        "connect":                  "🔌 Ses Kanalına Bağlan",
        "speak":                    "🎙️ Konuş",
        "stream":                   "📡 Yayın Yap",
        "use_voice_activation":     "🎤 Sesle Etkinleştir",
        "mute_members":             "🔇 Üyeleri Sustur (Ses)",
        "deafen_members":           "🔕 Üyeleri Sağırlaştır",
        "move_members":             "↔️ Üyeleri Taşı",
        "priority_speaker":         "🎖️ Öncelikli Konuşmacı",
        "create_instant_invite":    "✉️ Anında Davet Oluştur",
        "change_nickname":          "📝 Takma Ad Değiştir",
        "view_channel":             "👁️ Kanalı Gör",
        "request_to_speak":         "✋ Konuşma İsteği",
        "use_embedded_activities":  "🎮 Aktiviteleri Kullan",
        "send_messages_in_threads": "🧵 Konularda Mesaj Gönder",
        "create_public_threads":    "📢 Herkese Açık Konu Oluştur",
        "create_private_threads":   "🔒 Özel Konu Oluştur",
    }
    return ceviriler.get(perm_adi, f"🔧 {perm_adi.replace('_', ' ').title()}")


def izin_farklarini_bul(eski: discord.Permissions, yeni: discord.Permissions):
    """
    İki Permissions nesnesi arasındaki farkları hesaplar.

    Mantık:
        - Her izin True/False değeri taşır.
        - Eski ve yeni değerleri karşılaştırarak:
            * False → True  : izin EKLENDİ
            * True  → False : izin KALDIRILDI
        - Değişmeyenler atlanır.

    Döndürür:
        eklenenler   : list[str] — eklenen izinlerin Türkçe isimleri
        kaldirlanlar : list[str] — kaldırılan izinlerin Türkçe isimleri
    """
    eklenenler   = []
    kaldirlanlar = []

    # discord.Permissions.__iter__() → (izin_adı, bool) çiftleri döndürür
    eski_dict = dict(eski)
    yeni_dict = dict(yeni)

    for perm_adi in eski_dict:
        eski_deger = eski_dict[perm_adi]
        yeni_deger = yeni_dict.get(perm_adi, False)

        if eski_deger == yeni_deger:
            continue  # Değişiklik yok, atla

        ad = izin_adi_getir(perm_adi)

        if not eski_deger and yeni_deger:
            eklenenler.append(ad)       # False → True: eklendi
        elif eski_deger and not yeni_deger:
            kaldirlanlar.append(ad)     # True → False: kaldırıldı

    return eklenenler, kaldirlanlar


# ─────────────────────────────────────────
#  SLASH KOMUTLARI — LOG AYARLARI
# ─────────────────────────────────────────

# Slash komutlarında açılır menü için seçenek listesi
LOG_TUR_SECENEKLERI = [
    app_commands.Choice(name=aciklama, value=tur)
    for tur, aciklama in LOG_TURLERI.items()
]


@bot.tree.command(name="log-kur", description="Bir log türü için kanal atar")
@app_commands.describe(
    tur="Hangi log türü için kanal ayarlıyorsunuz?",
    kanal="Logların gönderileceği metin kanalı"
)
@app_commands.choices(tur=LOG_TUR_SECENEKLERI)
@app_commands.checks.has_permissions(manage_guild=True)
async def log_kur(
    interaction: discord.Interaction,
    tur: app_commands.Choice[str],
    kanal: discord.TextChannel
):
    """
    Belirli bir log türü için kanal atar ve settings.json'a kaydeder.
    Sadece 'Sunucuyu Yönet' iznine sahip kişiler kullanabilir.
    """

    # Bota kanalda yazma izni var mı?
    if not kanal.permissions_for(interaction.guild.me).send_messages:
        embed = discord.Embed(
            title="❌ Yetki Hatası",
            description=f"{kanal.mention} kanalına mesaj gönderemiyorum.\nKanal izinlerimi kontrol edin.",
            color=RENKLER["hata"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Ayarı kaydet
    kanal_kaydet(interaction.guild_id, tur.value, kanal.id)

    # ── Sana özel onay mesajı (sadece sen görürsün) ──
    onay_embed = discord.Embed(
        title="✅ Log Kanalı Ayarlandı",
        color=RENKLER["basari"],
        timestamp=datetime.now(timezone.utc)
    )
    onay_embed.add_field(name="📋 Log Türü", value=tur.name,      inline=True)
    onay_embed.add_field(name="📍 Kanal",    value=kanal.mention, inline=True)
    onay_embed.set_footer(text=f"Ayarlayan: {interaction.user} • {zaman_damgasi()}")
    await interaction.response.send_message(embed=onay_embed, ephemeral=True)

    # ── Log kanalına bilgilendirme mesajı ─────────────
    kanal_embed = discord.Embed(
        title="🔔 Log Kanalı Aktif",
        description=f"Bu kanal **{tur.name}** için log kanalı olarak ayarlandı.\nArtık ilgili olaylar buraya düşecek.",
        color=RENKLER["basari"],
        timestamp=datetime.now(timezone.utc)
    )
    kanal_embed.add_field(name="⚙️ Ayarlayan", value=interaction.user.mention, inline=True)
    kanal_embed.set_footer(text=zaman_damgasi())
    await kanal.send(embed=kanal_embed)


@bot.tree.command(name="log-kaldir", description="Bir log türünü devre dışı bırakır")
@app_commands.describe(tur="Devre dışı bırakılacak log türü")
@app_commands.choices(tur=LOG_TUR_SECENEKLERI)
@app_commands.checks.has_permissions(manage_guild=True)
async def log_kaldir(
    interaction: discord.Interaction,
    tur: app_commands.Choice[str]
):
    """Belirtilen log türünün kanal kaydını siler ve o logu durdurur."""

    mevcut = kanal_al(interaction.guild_id, tur.value)
    if not mevcut:
        embed = discord.Embed(
            title="⚠️ Zaten Devre Dışı",
            description=f"**{tur.name}** için zaten bir kanal ayarlanmamış.",
            color=RENKLER["bilgi"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    kanal_sil(interaction.guild_id, tur.value)

    embed = discord.Embed(
        title="🗑️ Log Kanalı Kaldırıldı",
        description=f"**{tur.name}** artık log göndermeyecek.",
        color=RENKLER["hata"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"Kaldıran: {interaction.user}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="log-durum", description="Tüm log kanallarını ve durumlarını gösterir")
@app_commands.checks.has_permissions(manage_guild=True)
async def log_durum(interaction: discord.Interaction):
    """
    Bu sunucudaki tüm log türlerini ve atanmış kanallarını listeler.
    Kanal ayarlanmamışsa '🔴 Deaktif' olarak gösterilir.
    """
    ayarlar = ayarlari_yukle().get(str(interaction.guild_id), {})

    embed = discord.Embed(
        title="📋 Log Sistemi Durumu",
        description=f"**{interaction.guild.name}** sunucusundaki log ayarları",
        color=RENKLER["bilgi"],
        timestamp=datetime.now(timezone.utc)
    )

    mod_turleri   = {"ban_log", "mute_log", "mod_log"}
    mod_satirlar  = []
    genel_satirlar = []

    for tur, aciklama in LOG_TURLERI.items():
        kanal_id = ayarlar.get(tur)
        if kanal_id:
            kanal = interaction.guild.get_channel(kanal_id)
            durum = kanal.mention if kanal else "⚠️ Kanal Silinmiş"
        else:
            durum = "🔴 Deaktif"

        satir = f"**{aciklama}**\n╰ {durum}"

        if tur in mod_turleri:
            mod_satirlar.append(satir)
        else:
            genel_satirlar.append(satir)

    if mod_satirlar:
        embed.add_field(
            name="🛡️ Moderasyon Logları",
            value="\n\n".join(mod_satirlar),
            inline=False
        )
    if genel_satirlar:
        embed.add_field(
            name="📁 Genel Loglar",
            value="\n\n".join(genel_satirlar),
            inline=False
        )

    aktif = len([t for t in LOG_TURLERI if t in ayarlar])
    embed.set_footer(text=f"{aktif}/{len(LOG_TURLERI)} log türü aktif • {zaman_damgasi()}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="log-sifirla", description="Bu sunucunun tüm log ayarlarını siler")
@app_commands.checks.has_permissions(administrator=True)
async def log_sifirla(interaction: discord.Interaction):
    """
    Onay butonlu mesaj göstererek tüm log ayarlarını sıfırlar.
    Sadece 'Yönetici' iznine sahip kişiler kullanabilir.
    """

    class OnayView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)

        @discord.ui.button(label="Evet, Sıfırla", style=discord.ButtonStyle.danger, emoji="⚠️")
        async def onayla(self, btn_i: discord.Interaction, button: discord.ui.Button):
            guild_ayarlari_sil(btn_i.guild_id)
            embed = discord.Embed(
                title="🗑️ Tüm Log Ayarları Silindi",
                description="Bu sunucuya ait tüm log kanalı kayıtları kaldırıldı.",
                color=RENKLER["hata"]
            )
            await btn_i.response.edit_message(embed=embed, view=None)

        @discord.ui.button(label="İptal", style=discord.ButtonStyle.secondary, emoji="✖️")
        async def iptal(self, btn_i: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="✅ İptal Edildi",
                description="Sıfırlama işlemi iptal edildi, ayarlar korundu.",
                color=RENKLER["basari"]
            )
            await btn_i.response.edit_message(embed=embed, view=None)

    embed = discord.Embed(
        title="⚠️ Emin misiniz?",
        description="Bu işlem tüm log kanalı ayarlarını **kalıcı olarak** silecek.\nGeri alınamaz!",
        color=RENKLER["hata"]
    )
    await interaction.response.send_message(embed=embed, view=OnayView(), ephemeral=True)


# Yetki hataları için ortak yakalayıcı
@log_kur.error
@log_kaldir.error
@log_durum.error
@log_sifirla.error
async def komut_hata(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Yetersiz Yetki",
            description="Bu komutu kullanmak için **Sunucuyu Yönet** iznine ihtiyacınız var.",
            color=RENKLER["hata"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────
#  OLAYLAR — MODERASYON LOGLARI
# ─────────────────────────────────────────

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    sorumlu = await audit_log_bul(guild, discord.AuditLogAction.ban, hedef=user)

    embed = discord.Embed(title="🔨 Üye Banlandı", color=RENKLER["ban"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👤 Kullanıcı",    value=f"{user.mention} `{user}`",                   inline=True)
    embed.add_field(name="🆔 ID",            value=f"`{user.id}`",                               inline=True)
    embed.add_field(name="🛡️ İşlemi Yapan", value=sorumlu.mention if sorumlu else "Bilinmiyor", inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=zaman_damgasi())
    await log_gonder(guild, "ban_log", embed)


@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    sorumlu = await audit_log_bul(guild, discord.AuditLogAction.unban, hedef=user)

    embed = discord.Embed(title="✅ Ban Kaldırıldı", color=RENKLER["unban"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👤 Kullanıcı",    value=f"{user.mention} `{user}`",                   inline=True)
    embed.add_field(name="🛡️ İşlemi Yapan", value=sorumlu.mention if sorumlu else "Bilinmiyor", inline=True)
    embed.set_footer(text=zaman_damgasi())
    await log_gonder(guild, "ban_log", embed)


@bot.event
async def on_member_join(member: discord.Member):
    embed = discord.Embed(title="🎉 Yeni Üye Katıldı", color=RENKLER["giris"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👤 Kullanıcı",       value=f"{member.mention} `{member}`",         inline=True)
    embed.add_field(name="📅 Hesap Oluşturma", value=member.created_at.strftime("%d.%m.%Y"), inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=zaman_damgasi())
    await log_gonder(member.guild, "giris_cikis", embed)


@bot.event
async def on_member_remove(member: discord.Member):
    await asyncio.sleep(1)
    sorumlu = await audit_log_bul(member.guild, discord.AuditLogAction.kick, hedef=member)

    if sorumlu:
        embed = discord.Embed(title="👢 Üye Atıldı (Kick)", color=RENKLER["mute"], timestamp=datetime.now(timezone.utc))
        embed.add_field(name="👤 Kullanıcı",    value=f"{member.mention} `{member}`", inline=True)
        embed.add_field(name="🛡️ İşlemi Yapan", value=sorumlu.mention,                inline=True)
        embed.set_footer(text=zaman_damgasi())
        await log_gonder(member.guild, "mod_log", embed)
    else:
        embed = discord.Embed(title="🚪 Üye Ayrıldı", color=RENKLER["cikis"], timestamp=datetime.now(timezone.utc))
        embed.add_field(name="👤 Kullanıcı", value=f"`{member}`",    inline=True)
        embed.add_field(name="🆔 ID",        value=f"`{member.id}`", inline=True)
        embed.set_footer(text=zaman_damgasi())
        await log_gonder(member.guild, "giris_cikis", embed)


# ─────────────────────────────────────────
#  OLAYLAR — ROL İZİN DEĞİŞİKLİĞİ LOGU
# ─────────────────────────────────────────

@bot.event
async def on_guild_role_update(onceki: discord.Role, sonraki: discord.Role):
    """
    Bir rol güncellendiğinde tetiklenir.

    İzin değişikliklerini tespit eder:
        1. izin_farklarini_bul() ile eklenen/kaldırılan izinleri hesaplar.
        2. Audit log'dan değişikliği yapan kişiyi bulur.
        3. Estetik bir embed oluşturup rol_log kanalına gönderir.
    """

    # ── 1. İzin farklarını hesapla ──────────────────────────
    eklenenler, kaldirlanlar = izin_farklarini_bul(onceki.permissions, sonraki.permissions)

    # İzin değişikliği yoksa diğer değişiklikleri kontrol et (isim, renk vb.)
    if not eklenenler and not kaldirlanlar:
        degisiklikler = []
        if onceki.name  != sonraki.name:  degisiklikler.append(f"📝 İsim: `{onceki.name}` → `{sonraki.name}`")
        if onceki.color != sonraki.color: degisiklikler.append(f"🎨 Renk: `{onceki.color}` → `{sonraki.color}`")
        if onceki.hoist != sonraki.hoist: degisiklikler.append(f"📌 Ayrı Göster: `{onceki.hoist}` → `{sonraki.hoist}`")

        if not degisiklikler:
            return  # Hiçbir değişiklik yok

        sorumlu = await audit_log_bul(sonraki.guild, discord.AuditLogAction.role_update, hedef=sonraki)
        embed = discord.Embed(
            title=f"🎭 Rol Güncellendi — {sonraki.name}",
            color=sonraki.color.value or RENKLER["rol"],
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="🔄 Değişiklikler",  value="\n".join(degisiklikler),                     inline=False)
        embed.add_field(name="🛡️ İşlemi Yapan",   value=sorumlu.mention if sorumlu else "Bilinmiyor", inline=True)
        embed.set_footer(text=zaman_damgasi())
        await log_gonder(sonraki.guild, "rol_log", embed)
        return

    # ── 2. Audit log'dan sorumluyu bul ──────────────────────
    await asyncio.sleep(0.5)  # Audit log'un güncellenmesi için kısa bekleme
    sorumlu = await audit_log_bul(sonraki.guild, discord.AuditLogAction.role_update, hedef=sonraki)

    # ── 3. İzin değişikliği embedini oluştur ────────────────
    embed = discord.Embed(
        title=f"🔐 Rol İzinleri Değişti — {sonraki.name}",
        description=(
            f"**{sonraki.mention}** rolünün izinleri güncellendi.\n"
            f"**{len(eklenenler)}** izin eklendi · **{len(kaldirlanlar)}** izin kaldırıldı."
        ),
        color=RENKLER["izin"],
        timestamp=datetime.now(timezone.utc)
    )

    # Eklenen izinler (yeşil ✅)
    if eklenenler:
        embed.add_field(
            name="✅ Eklenen İzinler",
            value="\n".join(f"`+` {izin}" for izin in eklenenler),
            inline=True
        )

    # Kaldırılan izinler (kırmızı ❌)
    if kaldirlanlar:
        embed.add_field(
            name="❌ Kaldırılan İzinler",
            value="\n".join(f"`-` {izin}" for izin in kaldirlanlar),
            inline=True
        )

    # İki sütun varsa hizalama için boş alan
    if eklenenler and kaldirlanlar:
        embed.add_field(name="\u200b", value="\u200b", inline=True)

    # Toplam izin sayısı özeti
    eski_toplam = sum(1 for _, v in onceki.permissions if v)
    yeni_toplam = sum(1 for _, v in sonraki.permissions if v)
    fark = yeni_toplam - eski_toplam

    embed.add_field(
        name="📊 İzin Özeti",
        value=(
            f"Önceki: `{eski_toplam}` aktif\n"
            f"Şimdiki: `{yeni_toplam}` aktif\n"
            f"Fark: `{'+' if fark >= 0 else ''}{fark}`"
        ),
        inline=True
    )
    embed.add_field(name="🛡️ Yapan",  value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor", inline=True)
    embed.add_field(name="🆔 Rol ID", value=f"`{sonraki.id}`",                                inline=True)
    embed.set_footer(text=zaman_damgasi())

    await log_gonder(sonraki.guild, "rol_log", embed)


# ─────────────────────────────────────────
#  OLAYLAR — MESAJ LOGLARI
# ─────────────────────────────────────────

@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot:
        return

    embed = discord.Embed(title="🗑️ Mesaj Silindi", color=RENKLER["mesaj"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👤 Yazar",  value=f"{message.author.mention} `{message.author}`", inline=True)
    embed.add_field(name="📍 Kanal", value=message.channel.mention,                          inline=True)
    embed.add_field(name="💬 İçerik", value=message.content[:1024] or "*[Boş veya medya]*",  inline=False)
    embed.set_footer(text=zaman_damgasi())
    await log_gonder(message.guild, "mesaj_log", embed)


@bot.event
async def on_message_edit(onceki: discord.Message, sonraki: discord.Message):
    if onceki.author.bot or onceki.content == sonraki.content:
        return

    embed = discord.Embed(title="✏️ Mesaj Düzenlendi", color=RENKLER["bilgi"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👤 Yazar",      value=sonraki.author.mention,       inline=True)
    embed.add_field(name="📍 Kanal",      value=sonraki.channel.mention,       inline=True)
    embed.add_field(name="📄 Eski Mesaj", value=onceki.content[:512] or "—",  inline=False)
    embed.add_field(name="📝 Yeni Mesaj", value=sonraki.content[:512] or "—", inline=False)
    embed.set_footer(text=zaman_damgasi())
    await log_gonder(sonraki.guild, "mesaj_log", embed)


# ─────────────────────────────────────────
#  OLAYLAR — SES KANALI LOGLARI
# ─────────────────────────────────────────

@bot.event
async def on_voice_state_update(member: discord.Member, onceki: discord.VoiceState, sonraki: discord.VoiceState):
    if onceki.channel == sonraki.channel:
        return  # Mute/deafen gibi değişiklikleri loglama

    embed = discord.Embed(color=RENKLER["ses"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👤 Üye", value=f"{member.mention} `{member}`", inline=False)

    if onceki.channel is None:
        embed.title = "🔊 Ses Kanalına Katıldı"
        embed.add_field(name="📍 Kanal", value=sonraki.channel.mention, inline=True)
    elif sonraki.channel is None:
        embed.title = "🔇 Ses Kanalından Ayrıldı"
        embed.add_field(name="📍 Kanal", value=onceki.channel.mention, inline=True)
    else:
        embed.title = "↔️ Ses Kanalı Değiştirildi"
        embed.add_field(name="⬅️ Önceki", value=onceki.channel.mention, inline=True)
        embed.add_field(name="➡️ Yeni",   value=sonraki.channel.mention, inline=True)

    embed.set_footer(text=zaman_damgasi())
    await log_gonder(member.guild, "ses_log", embed)


# ─────────────────────────────────────────
#  OLAYLAR — TIMEOUT (ZAMAN ASIMI) LOGU
# ─────────────────────────────────────────

@bot.event
async def on_member_update(onceki: discord.Member, sonraki: discord.Member):
    """
    Bu event hem rol değişikliklerini hem de timeout değişikliklerini yakalar.
    İkisini birden burada handle ediyoruz.

    NOT: Rol değişikliği için yukarıda ayrı bir on_member_update var,
    ama discord.py'de aynı event'i iki kez tanımlayamazsınız.
    Bu yüzden rol + timeout kontrolü tek fonksiyonda birleştirildi.
    Eğer önceki on_member_update varsa onu SİLİP bununla DEĞİŞTİRİN.
    """

    # ── Timeout (Zaman Aşımı) Kontrolü ──────────────────────
    # timed_out_until: None ise timeout yok, datetime ise aktif timeout
    eski_timeout = onceki.timed_out_until
    yeni_timeout = sonraki.timed_out_until

    if eski_timeout != yeni_timeout:
        await asyncio.sleep(0.5)
        sorumlu = await audit_log_bul(sonraki.guild, discord.AuditLogAction.member_update, hedef=sonraki)

        if yeni_timeout is not None:
            # Timeout uygulandı
            bitis = yeni_timeout.strftime("%d.%m.%Y %H:%M UTC")
            embed = discord.Embed(
                title="🔇 Zaman Aşımı Uygulandı (Timeout)",
                color=RENKLER["mute"],
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="👤 Üye",            value=f"{sonraki.mention} `{sonraki}`",                inline=True)
            embed.add_field(name="🛡️ İşlemi Yapan",   value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor", inline=True)
            embed.add_field(name="⏰ Bitiş Zamanı",   value=f"`{bitis}`",                                    inline=False)
            embed.set_thumbnail(url=sonraki.display_avatar.url)
            embed.set_footer(text=zaman_damgasi())
            await log_gonder(sonraki.guild, "mute_log", embed)

        else:
            # Timeout kaldırıldı (erken veya süre doldu)
            embed = discord.Embed(
                title="🔊 Zaman Aşımı Kaldırıldı",
                color=RENKLER["unban"],
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="👤 Üye",           value=f"{sonraki.mention} `{sonraki}`",                inline=True)
            embed.add_field(name="🛡️ İşlemi Yapan",  value=sorumlu.mention if sorumlu else "⚠️ Otomatik",  inline=True)
            embed.set_thumbnail(url=sonraki.display_avatar.url)
            embed.set_footer(text=zaman_damgasi())
            await log_gonder(sonraki.guild, "mute_log", embed)

    # ── Rol Değişikliği Kontrolü ─────────────────────────────
    eski_roller = set(onceki.roles)
    yeni_roller = set(sonraki.roles)

    eklenen_roller   = yeni_roller - eski_roller
    cikarilan_roller = eski_roller - yeni_roller

    if not eklenen_roller and not cikarilan_roller:
        return

    await asyncio.sleep(0.5)
    sorumlu = await audit_log_bul(sonraki.guild, discord.AuditLogAction.member_role_update, hedef=sonraki)

    if eklenen_roller:
        embed = discord.Embed(title="🟢 Üyeye Rol Eklendi", color=RENKLER["giris"], timestamp=datetime.now(timezone.utc))
        embed.add_field(name="👤 Üye",           value=f"{sonraki.mention} `{sonraki}`",                inline=True)
        embed.add_field(name="🛡️ İşlemi Yapan",  value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor", inline=True)
        embed.add_field(
            name=f"➕ Eklenen Rol{'ler' if len(eklenen_roller) > 1 else ''}",
            value="\n".join(r.mention for r in eklenen_roller),
            inline=False
        )
        embed.set_thumbnail(url=sonraki.display_avatar.url)
        embed.set_footer(text=zaman_damgasi())
        await log_gonder(sonraki.guild, "rol_log", embed)

    if cikarilan_roller:
        embed = discord.Embed(title="🔴 Üyeden Rol Çıkarıldı", color=RENKLER["cikis"], timestamp=datetime.now(timezone.utc))
        embed.add_field(name="👤 Üye",           value=f"{sonraki.mention} `{sonraki}`",                inline=True)
        embed.add_field(name="🛡️ İşlemi Yapan",  value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor", inline=True)
        embed.add_field(
            name=f"➖ Çıkarılan Rol{'ler' if len(cikarilan_roller) > 1 else ''}",
            value="\n".join(r.mention for r in cikarilan_roller),
            inline=False
        )
        embed.set_thumbnail(url=sonraki.display_avatar.url)
        embed.set_footer(text=zaman_damgasi())
        await log_gonder(sonraki.guild, "rol_log", embed)


# ─────────────────────────────────────────
#  OLAYLAR — DAVETİYE LOGLARI
# ─────────────────────────────────────────

@bot.event
async def on_invite_create(invite: discord.Invite):
    """Yeni bir davet bağlantısı oluşturulduğunda tetiklenir."""
    embed = discord.Embed(
        title="✉️ Yeni Davet Oluşturuldu",
        color=RENKLER["bilgi"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="👤 Oluşturan",   value=invite.inviter.mention if invite.inviter else "Bilinmiyor", inline=True)
    embed.add_field(name="📍 Kanal",        value=invite.channel.mention if invite.channel else "—",         inline=True)
    embed.add_field(name="🔗 Davet Kodu",   value=f"`{invite.code}`",                                        inline=True)

    # Kullanım limiti: 0 = sınırsız
    kullanim = str(invite.max_uses) if invite.max_uses else "Sınırsız"
    embed.add_field(name="🔢 Kullanım Limiti", value=kullanim, inline=True)

    # Süre: 0 = hiç dolmaz
    if invite.max_age:
        sure = f"{invite.max_age // 3600} saat" if invite.max_age >= 3600 else f"{invite.max_age // 60} dakika"
    else:
        sure = "Süresiz"
    embed.add_field(name="⏳ Geçerlilik",   value=sure,    inline=True)
    embed.add_field(name="🌐 URL",          value=f"discord.gg/{invite.code}", inline=True)

    embed.set_footer(text=zaman_damgasi())
    await log_gonder(invite.guild, "davet_log", embed)


@bot.event
async def on_invite_delete(invite: discord.Invite):
    """Bir davet bağlantısı silindiğinde tetiklenir."""
    embed = discord.Embed(
        title="🗑️ Davet Silindi",
        color=RENKLER["hata"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="🔗 Davet Kodu", value=f"`{invite.code}`",                                        inline=True)
    embed.add_field(name="📍 Kanal",       value=invite.channel.mention if invite.channel else "—",         inline=True)
    embed.set_footer(text=zaman_damgasi())
    await log_gonder(invite.guild, "davet_log", embed)


# ─────────────────────────────────────────
#  OLAYLAR — KANAL LOGLARI
# ─────────────────────────────────────────

@bot.event
async def on_guild_channel_create(kanal: discord.abc.GuildChannel):
    """Yeni bir kanal oluşturulduğunda tetiklenir."""
    sorumlu = await audit_log_bul(kanal.guild, discord.AuditLogAction.channel_create, hedef=kanal)

    # Kanal türünü belirle
    tur_simge = {
        discord.TextChannel:     "💬 Metin Kanalı",
        discord.VoiceChannel:    "🔊 Ses Kanalı",
        discord.CategoryChannel: "📁 Kategori",
        discord.ForumChannel:    "📋 Forum Kanalı",
        discord.StageChannel:    "🎙️ Sahne Kanalı",
    }.get(type(kanal), "📌 Kanal")

    embed = discord.Embed(
        title="✅ Kanal Oluşturuldu",
        color=RENKLER["giris"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📍 Kanal",        value=f"{kanal.mention} `{kanal.name}`",                        inline=True)
    embed.add_field(name="📂 Tür",           value=tur_simge,                                               inline=True)
    embed.add_field(name="🛡️ İşlemi Yapan", value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor",          inline=True)
    embed.add_field(name="🆔 Kanal ID",     value=f"`{kanal.id}`",                                          inline=True)

    # Kategorisi varsa göster
    if hasattr(kanal, "category") and kanal.category:
        embed.add_field(name="📁 Kategori", value=kanal.category.name, inline=True)

    embed.set_footer(text=zaman_damgasi())
    await log_gonder(kanal.guild, "kanal_log", embed)


@bot.event
async def on_guild_channel_delete(kanal: discord.abc.GuildChannel):
    """Bir kanal silindiğinde tetiklenir."""
    sorumlu = await audit_log_bul(kanal.guild, discord.AuditLogAction.channel_delete, hedef=kanal)

    tur_simge = {
        discord.TextChannel:     "💬 Metin Kanalı",
        discord.VoiceChannel:    "🔊 Ses Kanalı",
        discord.CategoryChannel: "📁 Kategori",
        discord.ForumChannel:    "📋 Forum Kanalı",
        discord.StageChannel:    "🎙️ Sahne Kanalı",
    }.get(type(kanal), "📌 Kanal")

    embed = discord.Embed(
        title="🗑️ Kanal Silindi",
        color=RENKLER["hata"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📍 Kanal Adı",    value=f"`{kanal.name}`",                                        inline=True)
    embed.add_field(name="📂 Tür",           value=tur_simge,                                               inline=True)
    embed.add_field(name="🛡️ İşlemi Yapan", value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor",          inline=True)
    embed.add_field(name="🆔 Kanal ID",     value=f"`{kanal.id}`",                                          inline=True)

    if hasattr(kanal, "category") and kanal.category:
        embed.add_field(name="📁 Kategori", value=kanal.category.name, inline=True)

    embed.set_footer(text=zaman_damgasi())
    await log_gonder(kanal.guild, "kanal_log", embed)


def kanal_izin_farklarini_bul(onceki: discord.abc.GuildChannel, sonraki: discord.abc.GuildChannel):
    """
    İki kanal arasındaki izin (overwrite) farklarını bulur.

    Kanal izinleri rol/üye bazlı OverwriteType nesneleridir.
    Her overwrite'ın allow ve deny listeleri karşılaştırılır:
        - Yeni eklenmiş overwrite  → o rol/üye için yeni izin ayarı yapılmış
        - Silinmiş overwrite       → o rol/üye için izin ayarı kaldırılmış
        - Değişmiş overwrite       → allow/deny değerleri farklılaşmış

    Döndürür:
        list[str] — okunabilir değişiklik satırları
    """
    satirlar = []

    eski_ow = dict(onceki.overwrites)   # {rol/üye: PermissionOverwrite}
    yeni_ow = dict(sonraki.overwrites)

    tum_hedefler = set(eski_ow) | set(yeni_ow)

    for hedef in tum_hedefler:
        eski = eski_ow.get(hedef)
        yeni = yeni_ow.get(hedef)

        hedef_adi = f"@{hedef.name}" if hasattr(hedef, 'name') else str(hedef)

        if eski is None and yeni is not None:
            # Yeni overwrite eklendi
            izinler = [izin_adi_getir(p) for p, v in iter(yeni) if v is not None]
            satirlar.append(f"➕ **{hedef_adi}** için izin ayarı eklendi")

        elif eski is not None and yeni is None:
            # Overwrite tamamen silindi
            satirlar.append(f"➖ **{hedef_adi}** için izin ayarı kaldırıldı")

        else:
            # Her iki tarafta da var, farkları bul
            eklenen_izinler  = []
            kaldirilan_izinler = []
            reddedilen_izinler = []
            red_kaldirilan   = []

            for perm, yeni_deger in iter(yeni):
                eski_deger = getattr(eski, perm, None)
                if eski_deger == yeni_deger:
                    continue

                ad = izin_adi_getir(perm)

                if yeni_deger is True and eski_deger is not True:
                    eklenen_izinler.append(ad)       # ✅ İzin verildi
                elif yeni_deger is False and eski_deger is not False:
                    reddedilen_izinler.append(ad)    # ❌ İzin reddedildi
                elif yeni_deger is None:
                    if eski_deger is True:
                        kaldirilan_izinler.append(ad)   # ✅ kaldırıldı → nötr
                    elif eski_deger is False:
                        red_kaldirilan.append(ad)       # ❌ kaldırıldı → nötr

            if any([eklenen_izinler, kaldirilan_izinler, reddedilen_izinler, red_kaldirilan]):
                satirlar.append(f"🔧 **{hedef_adi}** izinleri değişti:")
                if eklenen_izinler:
                    satirlar.append("  `✅` " + ", ".join(eklenen_izinler))
                if reddedilen_izinler:
                    satirlar.append("  `❌` " + ", ".join(reddedilen_izinler))
                if kaldirilan_izinler:
                    satirlar.append("  `↩️` Nötre alındı: " + ", ".join(kaldirilan_izinler))
                if red_kaldirilan:
                    satirlar.append("  `↩️` Red kaldırıldı: " + ", ".join(red_kaldirilan))

    return satirlar


@bot.event
async def on_guild_channel_update(onceki: discord.abc.GuildChannel, sonraki: discord.abc.GuildChannel):
    """
    Bir kanalın adı, ayarları veya izinleri değiştiğinde tetiklenir.
    Genel değişiklikler ve izin (overwrite) değişiklikleri ayrı embedler olarak gönderilir.
    """

    # ── 1. Genel ayar değişiklikleri ────────────────────────
    degisiklikler = []

    if onceki.name != sonraki.name:
        degisiklikler.append(f"📝 İsim: `{onceki.name}` → `{sonraki.name}`")

    if isinstance(onceki, discord.TextChannel) and isinstance(sonraki, discord.TextChannel):
        if onceki.topic != sonraki.topic:
            eski = onceki.topic or "*(boş)*"
            yeni = sonraki.topic or "*(boş)*"
            degisiklikler.append(f"📋 Konu: `{eski}` → `{yeni}`")
        if onceki.slowmode_delay != sonraki.slowmode_delay:
            degisiklikler.append(f"🐢 Yavaş Mod: `{onceki.slowmode_delay}sn` → `{sonraki.slowmode_delay}sn`")
        if onceki.nsfw != sonraki.nsfw:
            degisiklikler.append(f"🔞 NSFW: `{onceki.nsfw}` → `{sonraki.nsfw}`")

    if degisiklikler:
        sorumlu = await audit_log_bul(sonraki.guild, discord.AuditLogAction.channel_update, hedef=sonraki)
        embed = discord.Embed(
            title="✏️ Kanal Güncellendi",
            color=RENKLER["bilgi"],
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="📍 Kanal",         value=sonraki.mention,                                        inline=True)
        embed.add_field(name="🛡️ İşlemi Yapan",  value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor",        inline=True)
        embed.add_field(name="🔄 Değişiklikler", value="\n".join(degisiklikler),                                inline=False)
        embed.set_footer(text=zaman_damgasi())
        await log_gonder(sonraki.guild, "kanal_log", embed)

    # ── 2. İzin (overwrite) değişiklikleri ──────────────────
    izin_satirlari = kanal_izin_farklarini_bul(onceki, sonraki)

    if izin_satirlari:
        sorumlu = await audit_log_bul(sonraki.guild, discord.AuditLogAction.overwrite_update, hedef=sonraki)

        # Discord embed field değeri max 1024 karakter, uzunsa böl
        parca = ""
        parcalar = []
        for satir in izin_satirlari:
            if len(parca) + len(satir) + 1 > 1000:
                parcalar.append(parca)
                parca = satir
            else:
                parca += ("\n" if parca else "") + satir
        if parca:
            parcalar.append(parca)

        embed = discord.Embed(
            title="🔐 Kanal İzinleri Değişti",
            color=RENKLER["izin"],
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="📍 Kanal",        value=sonraki.mention,                                        inline=True)
        embed.add_field(name="🛡️ İşlemi Yapan", value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor",        inline=True)

        for i, parca in enumerate(parcalar):
            embed.add_field(
                name="🔄 Değişiklikler" if i == 0 else "\u200b",
                value=parca,
                inline=False
            )

        embed.set_footer(text=zaman_damgasi())
        await log_gonder(sonraki.guild, "kanal_log", embed)


# ─────────────────────────────────────────
#  BOT HAZIR OLAYI
# ─────────────────────────────────────────


@bot.event
async def on_command_error(ctx, error):
    """CommandNotFound ve diğer bilinen hataları sessizce geçer."""
    if isinstance(error, commands.CommandNotFound):
        return  # Bilinmeyen komutları yoksay
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bu komutu kullanmak için yetkin yok.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Üye bulunamadı.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Eksik parametre. ``.yardım` ile kullanımı görebilirsin.")


@bot.event
async def on_ready():
    # Slash komutlarını Discord'a senkronize et
    try:
        synced = await bot.tree.sync()
        print(f"  ✅ {len(synced)} slash komutu senkronize edildi.")
    except Exception as e:
        print(f"  ❌ Komut senkronizasyonu başarısız: {e}")

    # ── Sabit log kanallarını settings.json'a yükle ──────────
    # Her bot başladığında DEFAULT_LOG_KANALLARI settings.json'a yazılır.
    # Böylece deploy sonrası settings.json silinse bile kanallar kaybolmaz.
    for guild in bot.guilds:
        ayarlar = ayarlari_yukle()
        gk = str(guild.id)
        if gk not in ayarlar:
            ayarlar[gk] = {}
        for tur, kanal_id in DEFAULT_LOG_KANALLARI.items():
            ayarlar[gk][tur] = kanal_id
        ayarlari_kaydet(ayarlar)

        # Her kanala "sistem aktif" mesajı gönder
        for tur, kanal_id in DEFAULT_LOG_KANALLARI.items():
            kanal = guild.get_channel(kanal_id)
            if kanal:
                try:
                    await kanal.send(embed=discord.Embed(
                        title="✅ Log Sistemi Yeniden Başlatıldı",
                        description=f"Bot yeniden başlatıldı. **{LOG_TURLERI.get(tur, tur)}** aktif.",
                        color=RENKLER["basari"]
                    ))
                except Exception:
                    pass
    print("  ✅ Sabit log kanalları yüklendi.")

    # Varsayılan log kanallarını tüm sunuculara yükle
    for guild in bot.guilds:
        varsayilan_kanallari_yukle(guild.id)
        print(f"  ✅ {guild.name} için varsayılan kanallar yüklendi.")

    # Mod log kanalına yeniden başlatma bildirimi gönder
    for guild in bot.guilds:
        mod_kanal_id = VARSAYILAN_LOG_KANALLARI.get("mod_log")
        if mod_kanal_id:
            kanal = guild.get_channel(mod_kanal_id)
            if kanal:
                try:
                    await kanal.send(embed=discord.Embed(
                        title="🟢 Bot Yeniden Başlatıldı",
                        description="Bot yeniden başlatıldı, tüm log kanalları otomatik yüklendi.",
                        color=RENKLER["basari"],
                        timestamp=datetime.now(timezone.utc)
                    ))
                except Exception:
                    pass

    print("━" * 52)
    print(f"  🤖 Bot    : {bot.user} ({bot.user.id})")
    print(f"  📡 Sunucu : {len(bot.guilds)} adet")
    print(f"  ⚙️  Ayarlar: {AYAR_DOSYASI}")
    print("━" * 52)
    print("  Kullanılabilir slash komutları:")
    print("    /log-kur <tür> <kanal>  → Kanal ata")
    print("    /log-kaldir <tür>       → Logu kapat")
    print("    /log-durum              → Durumu gör")
    print("    /log-sifirla            → Tümünü sil")
    print("━" * 52)

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="sunucu loglarını 👁️"
        )
    )

# ═══════════════════════════════════════════════════════════════
#  PARTNER SİSTEMİ
# ═══════════════════════════════════════════════════════════════
#
#  Veri yapısı (settings.json içinde):
#  {
#    "guild_id": {
#      "partner_log": kanal_id,          ← partner log kanalı
#      "partners": {
#        "hedef_guild_id": {
#          "guild_name": "Sunucu Adı",
#          "guild_id": 123,
#          "yapan": "kullanici#0000",
#          "yapan_id": 123,
#          "zaman": "2026-03-20T16:00:00",  ← ISO format
#          "son_partner": "2026-03-20T16:00:00"
#        }
#      }
#    }
#  }
# ───────────────────────────────────────────────────────────────

PARTNER_BEKLEME_SURESI = 3600  # saniye (1 saat)


def partner_verisi_al(guild_id: int) -> dict:
    """Bu sunucunun partner verisini döndürür."""
    ayarlar = ayarlari_yukle()
    return ayarlar.get(str(guild_id), {}).get("partners", {})


def partner_kaydet_db(guild_id: int, hedef_guild_id: int, veri: dict):
    """Bir partner kaydını settings.json'a yazar."""
    ayarlar = ayarlari_yukle()
    guild_key = str(guild_id)
    if guild_key not in ayarlar:
        ayarlar[guild_key] = {}
    if "partners" not in ayarlar[guild_key]:
        ayarlar[guild_key]["partners"] = {}
    ayarlar[guild_key]["partners"][str(hedef_guild_id)] = veri
    ayarlari_kaydet(ayarlar)


def partner_log_kanali_kaydet(guild_id: int, kanal_id: int):
    """Partner log kanalını kaydeder."""
    ayarlar = ayarlari_yukle()
    guild_key = str(guild_id)
    if guild_key not in ayarlar:
        ayarlar[guild_key] = {}
    ayarlar[guild_key]["partner_log"] = kanal_id
    ayarlari_kaydet(ayarlar)


def partner_log_kanali_al(guild_id: int) -> int | None:
    """Partner log kanalı ID'sini döndürür."""
    ayarlar = ayarlari_yukle()
    return ayarlar.get(str(guild_id), {}).get("partner_log")


def partner_istatistik_hesapla(guild_id: int) -> dict:
    """
    Günlük, haftalık, aylık ve toplam partner sayısını hesaplar.

    Mantık:
        - Her partner kaydındaki 'zaman' alanı ISO format datetime'dır.
        - Şu anki zamandan farkı hesaplayarak hangi periyoda girdiğini belirleriz.
    """
    partners = partner_verisi_al(guild_id)
    simdi = datetime.now(timezone.utc)

    gunluk = haftalik = aylik = toplam = 0

    for p in partners.values():
        try:
            zaman = datetime.fromisoformat(p["zaman"]).replace(tzinfo=timezone.utc)
        except Exception:
            continue

        fark = simdi - zaman
        toplam += 1

        if fark.days < 1:
            gunluk += 1
        if fark.days < 7:
            haftalik += 1
        if fark.days < 30:
            aylik += 1

    return {
        "gunluk": gunluk,
        "haftalik": haftalik,
        "aylik": aylik,
        "toplam": toplam
    }


def partner_sira_bul(guild_id: int) -> int:
    """
    Bu sunucunun toplam partner sayısına göre sıralamasını döndürür.
    Tüm sunucuların toplam partner sayılarını karşılaştırır.
    """
    ayarlar = ayarlari_yukle()
    sayilar = []

    for gid, veri in ayarlar.items():
        if "partners" in veri:
            sayilar.append((gid, len(veri["partners"])))

    # Büyükten küçüğe sırala
    sayilar.sort(key=lambda x: x[1], reverse=True)

    for i, (gid, _) in enumerate(sayilar, 1):
        if gid == str(guild_id):
            return i
    return 1




# ── Partner Slash Komutları & Mesaj Kontrolü ─────────────────────

def partner_kanal_id_al(guild_id: int):
    """Partner text kanalı ID'sini döndürür."""
    return ayarlari_yukle().get(str(guild_id), {}).get("partner_kanal")

def partner_kanal_id_kaydet(guild_id: int, kanal_id: int):
    """Partner text kanalını kaydeder."""
    ayarlar = ayarlari_yukle()
    gk = str(guild_id)
    if gk not in ayarlar: ayarlar[gk] = {}
    ayarlar[gk]["partner_kanal"] = kanal_id
    ayarlari_kaydet(ayarlar)

def yetkili_partner_sayisi_guncelle(guild_id: int, yetkili_id: int, yetkili_adi: str):
    """
    Yetkili bazlı partner sayacını günceller.
    Her partnerlik yapıldığında ilgili yetkilinin sayısını 1 artırır.
    Yapı: ayarlar[guild_id]["yetkili_partnerleri"][yetkili_id] = {"ad": ..., "sayi": ...}
    """
    ayarlar = ayarlari_yukle()
    gk = str(guild_id)
    yk = str(yetkili_id)
    if gk not in ayarlar: ayarlar[gk] = {}
    if "yetkili_partnerleri" not in ayarlar[gk]: ayarlar[gk]["yetkili_partnerleri"] = {}
    if yk not in ayarlar[gk]["yetkili_partnerleri"]:
        ayarlar[gk]["yetkili_partnerleri"][yk] = {"ad": yetkili_adi, "sayi": 0}
    ayarlar[gk]["yetkili_partnerleri"][yk]["sayi"] += 1
    ayarlar[gk]["yetkili_partnerleri"][yk]["ad"] = yetkili_adi  # güncel isim
    ayarlari_kaydet(ayarlar)

def yetkili_siralamasi_al(guild_id: int) -> list:
    """
    Yetkilileri partner sayısına göre büyükten küçüğe sıralar.
    Döndürür: [{"id": ..., "ad": ..., "sayi": ...}, ...]
    """
    ayarlar = ayarlari_yukle()
    veri = ayarlar.get(str(guild_id), {}).get("yetkili_partnerleri", {})
    liste = [{"id": kid, "ad": v["ad"], "sayi": v["sayi"]} for kid, v in veri.items()]
    liste.sort(key=lambda x: x["sayi"], reverse=True)
    return liste


# ── Partner Prefix Komutları ─────────────────────────────────────

@bot.command(name="partner-kur")
@commands.has_permissions(manage_guild=True)
async def partner_kur(ctx, text_kanal: discord.TextChannel = None, log_kanal: discord.TextChannel = None):
    """
    .partner-kur #text-kanal #log-kanal
    Partner text ve log kanallarını ayarlar.
    """
    if not text_kanal or not log_kanal:
        await ctx.send("📌 Kullanım: `.partner-kur #text-kanal #log-kanal`")
        return

    partner_kanal_id_kaydet(ctx.guild.id, text_kanal.id)
    partner_log_kanali_kaydet(ctx.guild.id, log_kanal.id)

    embed = discord.Embed(title="✅ Partner Kanalları Ayarlandı", color=RENKLER["basari"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="📢 Partner Text", value=text_kanal.mention, inline=True)
    embed.add_field(name="📋 Partner Log",  value=log_kanal.mention,  inline=True)
    embed.set_footer(text=f"Ayarlayan: {ctx.author}")
    await ctx.send(embed=embed)
    await text_kanal.send(embed=discord.Embed(
        title="🤝 Partner Kanalı Aktif",
        description="Bu kanal partner text kanalı olarak ayarlandı.\nDavet linki içermeyen mesajlar otomatik silinecek.",
        color=RENKLER["basari"]
    ))
    await log_kanal.send(embed=discord.Embed(
        title="📋 Partner Log Kanalı Aktif",
        description="Partner logları bu kanala gönderilecek.",
        color=RENKLER["basari"]
    ))


@bot.command(name="partner-istatistik", aliases=["p-istat", "pistat"])
@commands.has_permissions(manage_guild=True)
async def partner_istatistik(ctx):
    """.partner-istatistik — Sunucunun partner istatistiklerini gösterir."""
    stats = partner_istatistik_hesapla(ctx.guild.id)
    sira  = partner_sira_bul(ctx.guild.id)

    embed = discord.Embed(
        title="📊 Partner İstatistikleri",
        description=f"**{ctx.guild.name}** sunucusunun partner verileri",
        color=0x57F287,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📊 Sıralaman", value=f"**#{sira}**", inline=False)
    embed.add_field(
        name="🕐 Zamana Dayalı:",
        value=(
            f"› Günlük: **{stats['gunluk']}**\n"
            f"› Haftalık: **{stats['haftalik']}**\n"
            f"› Aylık: **{stats['aylik']}**"
        ),
        inline=True
    )
    embed.add_field(name="• Toplam", value=f"**{stats['toplam']}**", inline=True)
    embed.set_footer(text=f"{ctx.bot.user.name} • Partner Sistemi • {zaman_damgasi()}")
    await ctx.send(embed=embed)


@bot.command(name="partner-top", aliases=["p-top", "ptop"])
@commands.has_permissions(manage_guild=True)
async def partner_top(ctx):
    """.partner-top — Yetkililerin partner sıralamasını gösterir."""
    sıralama = yetkili_siralamasi_al(ctx.guild.id)

    if not sıralama:
        await ctx.send(embed=discord.Embed(
            title="📋 Partner Sıralaması",
            description="Henüz hiç partnerlik kaydı yok.",
            color=RENKLER["bilgi"]
        ))
        return

    madalyalar = ["🥇", "🥈", "🥉"]
    satirlar = []
    for i, yetkili in enumerate(sıralama[:20], 1):
        madalya = madalyalar[i-1] if i <= 3 else f"`{i}.`"
        satirlar.append(f"{madalya} <@{yetkili['id']}> — **{yetkili['sayi']}** partnerlik")

    embed = discord.Embed(
        title="🏆 Partner Sıralaması",
        description="\n".join(satirlar),
        color=0xF1C40F,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"Toplam {len(sıralama)} yetkili • {zaman_damgasi()}")
    await ctx.send(embed=embed)


@bot.command(name="partner-liste", aliases=["p-liste", "pliste"])
@commands.has_permissions(manage_guild=True)
async def partner_liste(ctx):
    """.partner-liste — Tüm partner sunucularını listeler."""
    partners = partner_verisi_al(ctx.guild.id)
    if not partners:
        await ctx.send(embed=discord.Embed(
            title="📋 Partner Listesi",
            description="Henüz hiç partner kaydı yok.",
            color=RENKLER["bilgi"]
        ))
        return

    satirlar = []
    for i, (gid, p) in enumerate(partners.items(), 1):
        try:
            zaman = datetime.fromisoformat(p["zaman"]).strftime("%d.%m.%Y")
        except Exception:
            zaman = "—"
        satirlar.append(f"`{i}.` **{p['guild_name']}** — {zaman} — <@{p['yapan_id']}>")

    # Sayfalama — her sayfada 10 partner
    sayfalar = [satirlar[i:i+10] for i in range(0, len(satirlar), 10)]

    class SayfaView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.sayfa = 0

        def embed_olustur(self):
            e = discord.Embed(
                title=f"📋 Partner Listesi — Toplam {len(partners)}",
                description="\n".join(sayfalar[self.sayfa]),
                color=0x57F287,
                timestamp=datetime.now(timezone.utc)
            )
            e.set_footer(text=f"Sayfa {self.sayfa+1}/{len(sayfalar)} • {zaman_damgasi()}")
            return e

        @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
        async def geri(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.sayfa > 0:
                self.sayfa -= 1
            await interaction.response.edit_message(embed=self.embed_olustur(), view=self)

        @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
        async def ileri(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.sayfa < len(sayfalar) - 1:
                self.sayfa += 1
            await interaction.response.edit_message(embed=self.embed_olustur(), view=self)

    view = SayfaView()
    await ctx.send(embed=view.embed_olustur(), view=view if len(sayfalar) > 1 else None)


@bot.command(name="partner-sifirla", aliases=["p-sifirla"])
@commands.has_permissions(administrator=True)
async def partner_sifirla(ctx):
    """.partner-sifirla — Tüm partner kayıtlarını siler (onay butonu ile)."""

    class OnayView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)

        @discord.ui.button(label="✅ Evet, Sıfırla", style=discord.ButtonStyle.danger)
        async def onayla(self, interaction: discord.Interaction, button: discord.ui.Button):
            ayarlar = ayarlari_yukle()
            gk = str(interaction.guild_id)
            if gk in ayarlar:
                ayarlar[gk].pop("partners", None)
                ayarlar[gk].pop("yetkili_partnerleri", None)
                ayarlari_kaydet(ayarlar)
            await interaction.response.edit_message(embed=discord.Embed(
                title="🗑️ Partner Kayıtları Silindi",
                description="Tüm partner kayıtları ve yetkili sıralaması silindi.",
                color=RENKLER["hata"]
            ), view=None)

        @discord.ui.button(label="✖️ İptal", style=discord.ButtonStyle.secondary)
        async def iptal(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=discord.Embed(
                title="✅ İptal Edildi",
                description="İşlem iptal edildi, kayıtlar korundu.",
                color=RENKLER["basari"]
            ), view=None)

    await ctx.send(embed=discord.Embed(
        title="⚠️ Emin misiniz?",
        description="Tüm partner kayıtları ve yetkili sıralaması **kalıcı olarak** silinecek!",
        color=RENKLER["hata"]
    ), view=OnayView())





# ═══════════════════════════════════════════════════════════════
#  MODERASYON KOMUTLARI (Prefix: !)
# ═══════════════════════════════════════════════════════════════

def mod_embed(baslik: str, renk: int, **alanlar) -> discord.Embed:
    """Standart moderasyon embed'i oluşturur."""
    embed = discord.Embed(title=baslik, color=renk, timestamp=datetime.now(timezone.utc))
    for ad, deger in alanlar.items():
        embed.add_field(name=ad, value=deger, inline=True)
    embed.set_footer(text=zaman_damgasi())
    return embed


# ── !ban ────────────────────────────────────────────────────────
@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
    """.ban @üye [sebep]"""
    if uye == ctx.author:
        await ctx.send("❌ Kendinizi banlayamazsınız."); return
    if uye.top_role >= ctx.author.top_role:
        await ctx.send("❌ Bu üyeyi banlayacak yetkiniz yok."); return

    await uye.ban(reason=f"{ctx.author} tarafından: {sebep}")

    embed = mod_embed("🔨 Üye Banlandı", RENKLER["ban"],
        **{"👤 Üye": f"{uye.mention} `{uye}`",
           "📝 Sebep": sebep,
           "🛡️ Yetkili": ctx.author.mention})
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, "ban_log", embed)

    try:
        await uye.send(embed=discord.Embed(
            title="🔨 Sunucudan Banlandınız",
            description=f"**{ctx.guild.name}** sunucusundan banlandınız.\n**Sebep:** {sebep}",
            color=RENKLER["ban"]
        ))
    except discord.Forbidden:
        pass


@ban.error
async def ban_hata(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Ban yetkine sahip değilsin.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Üye bulunamadı.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("📌 Kullanım: ``.ban @üye [sebep]`")


# ── !unban ───────────────────────────────────────────────────────
@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, kullanici_id: int, *, sebep: str = "Sebep belirtilmedi"):
    """.unban <kullanıcı_id> [sebep]"""
    try:
        kullanici = await bot.fetch_user(kullanici_id)
        await ctx.guild.unban(kullanici, reason=f"{ctx.author} tarafından: {sebep}")

        embed = mod_embed("✅ Ban Kaldırıldı", RENKLER["unban"],
            **{"👤 Kullanıcı": f"`{kullanici}`",
               "📝 Sebep": sebep,
               "🛡️ Yetkili": ctx.author.mention})
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, "ban_log", embed)

    except discord.NotFound:
        await ctx.send("❌ Bu ID'ye sahip banlı bir kullanıcı bulunamadı.")


@unban.error
async def unban_hata(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Ban yetkine sahip değilsin.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("📌 Kullanım: ``.unban <kullanıcı_id> [sebep]`")


# ── !kick ────────────────────────────────────────────────────────
@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
    """.kick @üye [sebep]"""
    if uye == ctx.author:
        await ctx.send("❌ Kendinizi atamazsınız."); return
    if uye.top_role >= ctx.author.top_role:
        await ctx.send("❌ Bu üyeyi atacak yetkiniz yok."); return

    await uye.kick(reason=f"{ctx.author} tarafından: {sebep}")

    embed = mod_embed("👢 Üye Atıldı", RENKLER["mute"],
        **{"👤 Üye": f"{uye.mention} `{uye}`",
           "📝 Sebep": sebep,
           "🛡️ Yetkili": ctx.author.mention})
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, "mod_log", embed)

    try:
        await uye.send(embed=discord.Embed(
            title="👢 Sunucudan Atıldınız",
            description=f"**{ctx.guild.name}** sunucusundan atıldınız.\n**Sebep:** {sebep}",
            color=RENKLER["mute"]
        ))
    except discord.Forbidden:
        pass


@kick.error
async def kick_hata(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Kick yetkine sahip değilsin.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Üye bulunamadı.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("📌 Kullanım: ``.kick @üye [sebep]`")


# ── .mute (timeout) ──────────────────────────────────────────────
@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, uye: discord.Member, *, arguman: str = ""):
    """
    .mute @üye [süre] [sebep]
    Tüm argümanları tek string olarak alır, sonra parse eder.
    Böylece .mute @üye, .mute @üye sebep, .mute @üye 10m sebep hepsi çalışır.
    """
    if uye == ctx.author:
        await ctx.send("❌ Kendinizi susturamassınız."); return
    if uye.top_role >= ctx.author.top_role:
        await ctx.send("❌ Bu üyeyi susturacak yetkiniz yok."); return

    birimler = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    parcalar = arguman.strip().split()

    # İlk kelime süre formatında mı? (örn: 10m, 2h, 1d, 30s)
    if parcalar and parcalar[0][-1] in birimler and parcalar[0][:-1].isdigit():
        sure_str = parcalar[0]
        saniye = int(sure_str[:-1]) * birimler[sure_str[-1]]
        sebep = " ".join(parcalar[1:]) if len(parcalar) > 1 else "Sebep belirtilmedi"
        sure_goster = sure_str
        if saniye > 2419200:
            await ctx.send("❌ Maksimum süre 28 gündür."); return
    else:
        # Süre yok → tüm argüman sebep, süresiz mute
        saniye = 2419200
        sure_goster = "Süresiz"
        sebep = arguman.strip() if arguman.strip() else "Sebep belirtilmedi"

    bitis = datetime.now(timezone.utc) + discord.utils.timedelta(seconds=saniye)
    await uye.timeout(discord.utils.timedelta(seconds=saniye), reason=f"{ctx.author}: {sebep}")

    embed = mod_embed("🔇 Üye Susturuldu", RENKLER["mute"],
        **{"👤 Üye": f"{uye.mention} `{uye}`",
           "⏱️ Süre": sure_goster,
           "⏰ Bitiş": bitis.strftime("%d.%m.%Y %H:%M UTC"),
           "📝 Sebep": sebep,
           "🛡️ Yetkili": ctx.author.mention})
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, "mute_log", embed)


@mute.error
async def mute_hata(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Timeout yetkine sahip değilsin.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Üye bulunamadı.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("📌 Kullanım: `.mute @üye [süre] [sebep]`")


# ── !unmute ──────────────────────────────────────────────────────
@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
    """.unmute @üye [sebep]"""
    await uye.timeout(None, reason=f"{ctx.author}: {sebep}")

    embed = mod_embed("🔊 Timeout Kaldırıldı", RENKLER["unban"],
        **{"👤 Üye": f"{uye.mention} `{uye}`",
           "📝 Sebep": sebep,
           "🛡️ Yetkili": ctx.author.mention})
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, "mute_log", embed)


@unmute.error
async def unmute_hata(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Timeout kaldırma yetkine sahip değilsin.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Üye bulunamadı.")


# ── !sil ─────────────────────────────────────────────────────────
@bot.command(name="sil")
@commands.has_permissions(manage_messages=True)
async def sil(ctx, adet: int = 5):
    """.sil [adet] — Belirtilen sayıda mesajı siler (max 100)"""
    if adet < 1 or adet > 100:
        await ctx.send("❌ 1 ile 100 arasında bir sayı girin."); return

    await ctx.message.delete()
    silinen = await ctx.channel.purge(limit=adet)

    bilgi = await ctx.send(embed=discord.Embed(
        title="🗑️ Mesajlar Silindi",
        description=f"**{len(silinen)}** mesaj silindi.",
        color=RENKLER["mesaj"]
    ))
    await asyncio.sleep(3)
    await bilgi.delete()


@sil.error
async def sil_hata(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Mesaj silme yetkine sahip değilsin.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("📌 Kullanım: ``.sil [adet]`")


# ── !warn ────────────────────────────────────────────────────────
@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
    """.warn @üye [sebep] — Üyeye uyarı verir ve settings.json'a kaydeder."""
    # Uyarıyı kaydet
    ayarlar = ayarlari_yukle()
    guild_key = str(ctx.guild.id)
    if guild_key not in ayarlar:
        ayarlar[guild_key] = {}
    if "uyarilar" not in ayarlar[guild_key]:
        ayarlar[guild_key]["uyarilar"] = {}

    uye_key = str(uye.id)
    if uye_key not in ayarlar[guild_key]["uyarilar"]:
        ayarlar[guild_key]["uyarilar"][uye_key] = []

    kayit = {
        "sebep":    sebep,
        "yetkili":  str(ctx.author),
        "zaman":    datetime.now(timezone.utc).isoformat()
    }
    ayarlar[guild_key]["uyarilar"][uye_key].append(kayit)
    ayarlari_kaydet(ayarlar)

    toplam = len(ayarlar[guild_key]["uyarilar"][uye_key])

    embed = mod_embed(f"⚠️ Uyarı Verildi ({toplam}. uyarı)", RENKLER["mesaj"],
        **{"👤 Üye": f"{uye.mention} `{uye}`",
           "📝 Sebep": sebep,
           "🔢 Toplam Uyarı": str(toplam),
           "🛡️ Yetkili": ctx.author.mention})
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, "mod_log", embed)

    try:
        await uye.send(embed=discord.Embed(
            title="⚠️ Uyarı Aldınız",
            description=f"**{ctx.guild.name}** sunucusunda uyarıldınız.\n**Sebep:** {sebep}\n**Toplam uyarı:** {toplam}",
            color=RENKLER["mesaj"]
        ))
    except discord.Forbidden:
        pass


@warn.error
async def warn_hata(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Uyarı verme yetkine sahip değilsin.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Üye bulunamadı.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("📌 Kullanım: ``.warn @üye [sebep]`")


# ── !uyarılar ────────────────────────────────────────────────────
@bot.command(name="uyarılar", aliases=["warnings", "uyarilar"])
@commands.has_permissions(manage_messages=True)
async def uyarilar(ctx, uye: discord.Member):
    """.uyarılar @üye — Üyenin uyarı geçmişini gösterir."""
    ayarlar = ayarlari_yukle()
    liste = ayarlar.get(str(ctx.guild.id), {}).get("uyarilar", {}).get(str(uye.id), [])

    if not liste:
        await ctx.send(embed=discord.Embed(
            title=f"📋 {uye.display_name} — Uyarı Yok",
            description="Bu üyenin hiç uyarısı bulunmuyor.",
            color=RENKLER["bilgi"]
        ))
        return

    embed = discord.Embed(
        title=f"⚠️ {uye.display_name} — {len(liste)} Uyarı",
        color=RENKLER["mesaj"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=uye.display_avatar.url)

    for i, u in enumerate(liste[-10:], 1):  # Son 10 uyarı
        try:
            zaman = datetime.fromisoformat(u["zaman"]).strftime("%d.%m.%Y %H:%M")
        except Exception:
            zaman = "—"
        embed.add_field(
            name=f"#{i} — {zaman}",
            value=f"**Sebep:** {u['sebep']}\n**Yetkili:** {u['yetkili']}",
            inline=False
        )

    embed.set_footer(text=zaman_damgasi())
    await ctx.send(embed=embed)


@uyarilar.error
async def uyarilar_hata(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Üye bulunamadı.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("📌 Kullanım: ``.uyarılar @üye`")


# ── !uyarısil ────────────────────────────────────────────────────
@bot.command(name="uyarısil", aliases=["uyarisil", "clearwarns"])
@commands.has_permissions(manage_guild=True)
async def uyari_sil(ctx, uye: discord.Member):
    """.uyarısil @üye — Üyenin tüm uyarılarını siler."""
    ayarlar = ayarlari_yukle()
    guild_key = str(ctx.guild.id)
    uye_key = str(uye.id)

    if guild_key in ayarlar and "uyarilar" in ayarlar[guild_key] and uye_key in ayarlar[guild_key]["uyarilar"]:
        del ayarlar[guild_key]["uyarilar"][uye_key]
        ayarlari_kaydet(ayarlar)
        await ctx.send(embed=discord.Embed(
            title="✅ Uyarılar Silindi",
            description=f"{uye.mention} adlı üyenin tüm uyarıları silindi.",
            color=RENKLER["basari"]
        ))
    else:
        await ctx.send(f"❌ {uye.mention} adlı üyenin zaten uyarısı yok.")


# ── !yardım ──────────────────────────────────────────────────────
@bot.command(name="yardım", aliases=["yardim", "help"])
async def yardim(ctx):
    embed = discord.Embed(
        title="📖 Komut Rehberi",
        description="Botun tüm komutları aşağıda listelenmiştir.",
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(
        name="🛡️ Moderasyon",
        value=(
            "`.ban @üye [sebep]` ┗ Banlar\n"
            "`.unban <id> [sebep]` ┗ Ban kaldırır\n"
            "`.kick @üye [sebep]` ┗ Atar\n"
            "`.mute @üye [süre] [sebep]` ┗ Susturur · süre boş = kalıcı\n"
            "`.unmute @üye` ┗ Susturmayı kaldırır\n"
            "`.sil [adet]` ┗ Mesaj siler (max 100)\n"
            "`.warn @üye [sebep]` ┗ Uyarı verir\n"
            "`.uyarılar @üye` ┗ Uyarıları gösterir\n"
            "`.uyarısil @üye` ┗ Uyarıları temizler"
        ),
        inline=False
    )
    embed.add_field(
        name="🤝 Partner Sistemi",
        value=(
            "`.partner-kur #text #log` ┗ Kanalları ayarlar\n"
            "`.partner-istatistik` ┗ Günlük/haftalık/aylık/toplam\n"
            "`.partner-top` ┗ 🥇🥈🥉 Yetkili sıralaması\n"
            "`.partner-liste` ┗ Tüm partner sunucuları\n"
            "`.partner-sifirla` ┗ Tüm kayıtları sıfırlar"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Log Sistemi (/slash)",
        value=(
            "`/log-kur` ┗ Log kanalı atar\n"
            "`/log-kaldir` ┗ Log türünü kapatır\n"
            "`/log-durum` ┗ Tüm log durumlarını gösterir\n"
            "`/log-sifirla` ┗ Log ayarlarını sıfırlar"
        ),
        inline=False
    )
    embed.set_footer(text=f"{ctx.guild.name} • {zaman_damgasi()}")
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    await ctx.send(embed=embed)


# ─────────────────────────────────────────
#  BOTU BAŞLAT
# ─────────────────────────────────────────



# ─────────────────────────────────────────
#  PARTNER KANALI — MESAJ KONTROLÜ
# ─────────────────────────────────────────

import re
DAVET_REGEX = re.compile(r"discord(?:\.gg|app\.com/invite|\.com/invite)/[a-zA-Z0-9\-]+")

@bot.event
async def on_message(message: discord.Message):
    """
    Partner kanalına gelen mesajları kontrol eder:
      - Davet linki YOK → mesajı sil, 5sn uyarı
      - Davet linki VAR ama 1 saat geçmemiş → sil, bekleme süresi söyle
      - Davet linki VAR ve geçerli → kaydet, istatistik göster, log at
    Diğer kanallarda prefix komutlarını işle.
    """
    if message.author.bot:
        await bot.process_commands(message)
        return

    if message.guild:
        partner_ch_id = partner_kanal_id_al(message.guild.id)
        if partner_ch_id and message.channel.id == partner_ch_id:

            # Davet linki var mı?
            eslesen = DAVET_REGEX.search(message.content)

            if not eslesen:
                # Davet linki yok → sil ve uyar
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                uyari = await message.channel.send(embed=discord.Embed(
                    title="❌ Geçersiz Partner Metni",
                    description=f"{message.author.mention} Mesajınızda Discord davet linki bulunamadı. Mesajınız silindi.",
                    color=RENKLER["hata"]
                ))
                await asyncio.sleep(5)
                try:
                    await uyari.delete()
                except discord.NotFound:
                    pass
                return

            # Davet kodu
            davet_kodu = eslesen.group(0).split("/")[-1]
            partners = partner_verisi_al(message.guild.id)
            simdi = datetime.now(timezone.utc)

            # 1 saat bekleme kontrolü
            if davet_kodu in partners:
                son_zaman_str = partners[davet_kodu].get("son_partner")
                if son_zaman_str:
                    son_zaman = datetime.fromisoformat(son_zaman_str).replace(tzinfo=timezone.utc)
                    gecen = (simdi - son_zaman).total_seconds()
                    if gecen < PARTNER_BEKLEME_SURESI:
                        kalan = int(PARTNER_BEKLEME_SURESI - gecen)
                        onceki_id = partners[davet_kodu].get("yapan_id")
                        try:
                            await message.delete()
                        except discord.Forbidden:
                            pass
                        uyari = await message.channel.send(embed=discord.Embed(
                            title="⏳ Bekleme Süresi Dolmadı",
                            description=(
                                f"{message.author.mention} Bu sunucuyla tekrar partner yapmak için\n"
                                f"**{kalan // 60} dakika {kalan % 60} saniye** beklemeniz gerekiyor.\n"
                                f"Son partner: <@{onceki_id}> tarafından yapıldı."
                            ),
                            color=RENKLER["mute"]
                        ))
                        await asyncio.sleep(7)
                        try:
                            await uyari.delete()
                        except discord.NotFound:
                            pass
                        return

            # Kaydet
            ilk_satir = message.content.strip().split("\n")[0][:50]
            sunucu_adi = ilk_satir if ilk_satir else "Bilinmiyor"

            kayit = {
                "guild_name":  sunucu_adi,
                "guild_id":    davet_kodu,
                "yapan":       str(message.author),
                "yapan_id":    message.author.id,
                "zaman":       simdi.isoformat(),
                "son_partner": simdi.isoformat()
            }
            ayarlar = ayarlari_yukle()
            gk = str(message.guild.id)
            if gk not in ayarlar: ayarlar[gk] = {}
            if "partners" not in ayarlar[gk]: ayarlar[gk]["partners"] = {}
            ayarlar[gk]["partners"][davet_kodu] = kayit
            ayarlari_kaydet(ayarlar)

            # Yetkili sayacını güncelle
            yetkili_partner_sayisi_guncelle(message.guild.id, message.author.id, str(message.author))

            # İstatistik hesapla
            stats = partner_istatistik_hesapla(message.guild.id)
            sira  = partner_sira_bul(message.guild.id)
            yetkili_liste = yetkili_siralamasi_al(message.guild.id)
            yetkili_sira  = next((i+1 for i, y in enumerate(yetkili_liste) if y["id"] == str(message.author.id)), "?")
            yetkili_toplam = next((y["sayi"] for y in yetkili_liste if y["id"] == str(message.author.id)), 1)

            # İstatistik embed
            stats_embed = discord.Embed(
                title="🤝 Yeni Partner Yapıldı!",
                description=f"{message.author.mention} yeni bir partnerlik yaptı!",
                color=0x57F287,
                timestamp=simdi
            )
            stats_embed.add_field(name="📊 Sunucu Sırası", value=f"**#{sira}**", inline=True)
            stats_embed.add_field(name="👤 Yetkili Sırası", value=f"**#{yetkili_sira}** ({yetkili_toplam} partnerlik)", inline=True)
            stats_embed.add_field(
                name="🕐 Zamana Dayalı:",
                value=(
                    f"› Günlük: **{stats['gunluk']}**\n"
                    f"› Haftalık: **{stats['haftalik']}**\n"
                    f"› Aylık: **{stats['aylik']}**"
                ),
                inline=True
            )
            stats_embed.add_field(name="• Toplam", value=f"**{stats['toplam']}**", inline=True)
            stats_embed.set_footer(text=f"{bot.user.name} • Partner Sistemi")
            if message.guild.icon:
                stats_embed.set_thumbnail(url=message.guild.icon.url)
            await message.channel.send(embed=stats_embed)

            # Log kanalına gönder
            log_kanal_id = partner_log_kanali_al(message.guild.id)
            if log_kanal_id:
                log_kanal = message.guild.get_channel(log_kanal_id)
                if log_kanal:
                    log_embed = discord.Embed(title="📋 Partner Logu", color=0x57F287, timestamp=simdi)
                    log_embed.add_field(name="🔗 Davet",        value=f"`{davet_kodu}`",                       inline=True)
                    log_embed.add_field(name="👤 Yapan",        value=message.author.mention,                  inline=True)
                    log_embed.add_field(name="📅 Zaman",        value=simdi.strftime("%d.%m.%Y %H:%M UTC"),    inline=True)
                    log_embed.add_field(name="📊 Toplam",       value=str(stats["toplam"]),                    inline=True)
                    log_embed.add_field(name="👤 Yetkili Toplamı", value=str(yetkili_toplam),                  inline=True)
                    log_embed.set_footer(text=zaman_damgasi())
                    await log_kanal.send(embed=log_embed)

            return

    await bot.process_commands(message)

# ─────────────────────────────────────────
#  FLASK (RENDER CANLI TUTMAK İÇİN)
# ─────────────────────────────────────────

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot çalışıyor"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
