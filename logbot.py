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

BOT_TOKEN    = "BOT_TOKEN_BURAYA"   # Bot tokenınızı buraya girin
AYAR_DOSYASI = "settings.json"      # Kanal ID'leri burada saklanır

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

bot = commands.Bot(command_prefix="!", intents=intents)


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


@bot.event
async def on_guild_channel_update(onceki: discord.abc.GuildChannel, sonraki: discord.abc.GuildChannel):
    """Bir kanalın adı veya ayarları değiştiğinde tetiklenir."""
    degisiklikler = []

    if onceki.name != sonraki.name:
        degisiklikler.append(f"📝 İsim: `{onceki.name}` → `{sonraki.name}`")

    # Metin kanalına özel: topic değişikliği
    if isinstance(onceki, discord.TextChannel) and isinstance(sonraki, discord.TextChannel):
        if onceki.topic != sonraki.topic:
            eski = onceki.topic or "*(boş)*"
            yeni = sonraki.topic or "*(boş)*"
            degisiklikler.append(f"📋 Konu: `{eski}` → `{yeni}`")
        if onceki.slowmode_delay != sonraki.slowmode_delay:
            degisiklikler.append(f"🐢 Yavaş Mod: `{onceki.slowmode_delay}sn` → `{sonraki.slowmode_delay}sn`")
        if onceki.nsfw != sonraki.nsfw:
            degisiklikler.append(f"🔞 NSFW: `{onceki.nsfw}` → `{sonraki.nsfw}`")

    if not degisiklikler:
        return  # Önemli bir değişiklik yok

    sorumlu = await audit_log_bul(sonraki.guild, discord.AuditLogAction.channel_update, hedef=sonraki)

    embed = discord.Embed(
        title="✏️ Kanal Güncellendi",
        color=RENKLER["bilgi"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📍 Kanal",         value=sonraki.mention,                                          inline=True)
    embed.add_field(name="🛡️ İşlemi Yapan",  value=sorumlu.mention if sorumlu else "⚠️ Bilinmiyor",          inline=True)
    embed.add_field(name="🔄 Değişiklikler", value="\n".join(degisiklikler),                                  inline=False)
    embed.set_footer(text=zaman_damgasi())
    await log_gonder(sonraki.guild, "kanal_log", embed)


# ─────────────────────────────────────────
#  BOT HAZIR OLAYI
# ─────────────────────────────────────────

@bot.event
async def on_ready():
    # Slash komutlarını Discord'a senkronize et
    try:
        synced = await bot.tree.sync()
        print(f"  ✅ {len(synced)} slash komutu senkronize edildi.")
    except Exception as e:
        print(f"  ❌ Komut senkronizasyonu başarısız: {e}")

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

# ================= FLASK (REPLIT PREVIEW İÇİN) =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot çalışıyor"

def run_flask():
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()


# ─────────────────────────────────────────
#  BOTU BAŞLAT
# ─────────────────────────────────────────

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
