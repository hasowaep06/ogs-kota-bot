import os
import sqlite3
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import datetime

# --- FLASK WEB SERVER (Render 7/24 Aktif Tutmak İçin) ---
app = Flask('')

@app.route('/')
def home():
    return "OGS Kota Botu 7/24 Aktif!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- DISCORD BOT AYARLARI ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = 1429466809110626377  # OGS Community Sunucu ID
MY_ID = 1266281343957078029     # Hasan (Kurucu ID)
GUILD_OBJ = discord.Object(id=GUILD_ID)

SUP_ROLE_NAME = "Sup"  # Sunucundaki Sup rolünün adı
DRIVE_LINK = "https://drive.google.com/your-folder-link"  # Buraya Google Drive / Comp Linkini Koy!

# --- YETKİ KONTROL YARDIMCISI ---
def is_unlimited(member: discord.Member) -> bool:
    if member.id == MY_ID:
        return True
    if hasattr(member, "roles"):
        return any(role.name == SUP_ROLE_NAME for role in member.roles)
    return False

# --- VERİTABANI İŞLEMLERİ ---
async def init_db():
    async with aiosqlite.connect("kota.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quotas (
                user_id INTEGER PRIMARY KEY,
                remaining_quota INTEGER DEFAULT 10,
                last_reset DATE
            )
        """)
        await db.commit()

# --- GECE 00:00 KOTA SIFIRLAMA GÖREVİ ---
@tasks.loop(minutes=1)
async def check_daily_reset():
    now = datetime.datetime.utcnow()
    if now.hour == 0 and now.minute == 0:
        async with aiosqlite.connect("kota.db") as db:
            await db.execute("UPDATE quotas SET remaining_quota = 10")
            await db.commit()
        print("✅ Tüm kullanıcıların günlük kotaları 10/10 olarak sıfırlandı.")

# --- ERİŞİM ONAY / RED BUTONLARI ---
class AccessRequestView(discord.ui.View):
    def __init__(self, requester: discord.User, comp_name: str):
        super().__init__(timeout=None)
        self.requester = requester
        self.comp_name = comp_name

    @discord.ui.button(label="Onayla ✅", style=discord.ButtonStyle.green, custom_id="access_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = bot.get_guild(GUILD_ID)
        requester_member = guild.get_member(self.requester.id) if guild else None
        
        # Sınırsız yetkisi yoksa kotadan düşüyoruz
        if not (requester_member and is_unlimited(requester_member)):
            user_id = self.requester.id
            async with aiosqlite.connect("kota.db") as db:
                async with db.execute("SELECT remaining_quota FROM quotas WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    remaining = row[0] if row is not None else 10

                    if remaining <= 0:
                        await interaction.response.send_message(
                            f"⚠️ {self.requester.mention} adlı kullanıcının kotası dolduğu için işlem başarısız oldu!", 
                            ephemeral=True
                        )
                        return

                    new_quota = remaining - 1
                    await db.execute(
                        "INSERT INTO quotas (user_id, remaining_quota) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET remaining_quota = ?",
                        (user_id, new_quota, new_quota)
                    )
                    await db.commit()

        for child in self.children:
            child.disabled = True
        
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="📌 Durum", value="🟢 **ONAYLANDI**", inline=False)
        embed.add_field(name="👑 İşlemi Yapan Yetkili", value=f"{interaction.user.mention} (`{interaction.user.name}`)", inline=False)
        embed.add_field(name="📅 İşlem Tarihi", value=f"<t:{int(datetime.datetime.utcnow().timestamp())}:F>", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

        # Üyeye DM Gönderimi & Drive Linki İletimi
        try:
            user_embed = discord.Embed(
                title="🎉 Erişim Talebiniz Onaylandı!",
                description=f"**{self.comp_name}** projesi için erişim talebiniz yetkililer tarafından onaylandı.",
                color=discord.Color.green()
            )
            user_embed.add_field(name="📁 Drive / İndirme Linki", value=f"[Açmak için tıklayın]({DRIVE_LINK})", inline=False)
            user_embed.add_field(name="Yetkili", value=interaction.user.display_name, inline=True)
            user_embed.set_footer(text="OGS Community • Premium Clip Sistemi")
            
            await self.requester.send(embed=user_embed)
        except Exception:
            pass

    @discord.ui.button(label="Reddet ❌", style=discord.ButtonStyle.danger, custom_id="access_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="📌 Durum", value="🔴 **REDDEDİLDİ**", inline=False)
        embed.add_field(name="👑 İşlemi Yapan Yetkili", value=f"{interaction.user.mention} (`{interaction.user.name}`)", inline=False)
        embed.add_field(name="📅 İşlem Tarihi", value=f"<t:{int(datetime.datetime.utcnow().timestamp())}:F>", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            user_embed = discord.Embed(
                title="❌ Erişim Talebiniz Reddedildi",
                description=f"**{self.comp_name}** projesi için erişim talebiniz yetkili tarafından reddedildi.",
                color=discord.Color.red()
            )
            user_embed.add_field(name="Yetkili", value=interaction.user.display_name, inline=True)
            user_embed.set_footer(text="OGS Community • Premium Clip Sistemi")

            await self.requester.send(embed=user_embed)
        except Exception:
            pass

# --- /KOTA KOMUTU ---
@bot.tree.command(name="kota", description="Mevcut günlük klip kotanızı kontrol edin.", guild=GUILD_OBJ)
async def kota(interaction: discord.Interaction):
    member = interaction.user

    if isinstance(member, discord.Member) and is_unlimited(member):
        embed = discord.Embed(
            title="📊 Günlük Klip Kotan",
            description="Kalan Kotan: **∞ / Sınırsız** (Yetkili İzni)",
            color=discord.Color.gold()
        )
        embed.set_footer(text="OGS Community • Premium Clip Sistemi")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    async with aiosqlite.connect("kota.db") as db:
        async with db.execute("SELECT remaining_quota FROM quotas WHERE user_id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
            remaining = row[0] if row else 10

    embed = discord.Embed(
        title="📊 Günlük Klip Kotan",
        description=f"Kalan Kotan: **{remaining} / 10**",
        color=discord.Color.blue()
    )
    embed.set_footer(text="OGS Community • Premium Clip Sistemi")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- /CLIP KOMUTU ---
@bot.tree.command(name="clip", description="Clip linki gönderirsiniz ve kotanızdan 1 düşer.", guild=GUILD_OBJ)
async def clip(interaction: discord.Interaction, link: str):
    member = interaction.user

    if isinstance(member, discord.Member) and is_unlimited(member):
        embed = discord.Embed(
            title="✅ Clip İsteği Alındı",
            color=discord.Color.gold()
        )
        embed.add_field(name="Link:", value=link, inline=False)
        embed.add_field(name="Kalan Kotan:", value="∞ / Sınırsız", inline=False)
        embed.set_footer(text="OGS Community • Premium Clip Sistemi")

        await interaction.response.send_message(embed=embed)
        return

    async with aiosqlite.connect("kota.db") as db:
        async with db.execute("SELECT remaining_quota FROM quotas WHERE user_id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
            remaining = row[0] if row is not None else 10

            if remaining <= 0:
                await interaction.response.send_message(
                    "❌ Bugünkü klip kotan doldu! Yarın gece 00:00'da tekrar yenilenecektir.", 
                    ephemeral=True
                )
                return

            new_quota = remaining - 1
            await db.execute(
                "INSERT INTO quotas (user_id, remaining_quota) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET remaining_quota = ?",
                (member.id, new_quota, new_quota)
            )
            await db.commit()

            embed = discord.Embed(
                title="✅ Clip İsteği Alındı",
                color=discord.Color.green()
            )
            embed.add_field(name="Link:", value=link, inline=False)
            embed.add_field(name="Kalan Kotan:", value=f"{new_quota} / 10", inline=False)
            embed.set_footer(text="OGS Community • Premium Clip Sistemi")

            await interaction.response.send_message(embed=embed)

# --- /ERISIM KOMUTU ---
@bot.tree.command(name="erisim", description="Bir comp için erişim talebinde bulunursunuz.", guild=GUILD_OBJ)
@app_commands.describe(comp_adi="Erişim istemek istediğiniz comp veya projenin adı")
async def erisim(interaction: discord.Interaction, comp_adi: str):
    requester = interaction.user
    guild = interaction.guild

    embed = discord.Embed(
        title="📩 Yeni Erişim Talebi",
        color=discord.Color.gold()
    )
    embed.add_field(name="👤 Talep Eden Üye", value=f"{requester.mention} (`{requester.name}` - ID: `{requester.id}`)", inline=False)
    embed.add_field(name="📁 Erişim İstenen Comp", value=f"**{comp_adi}**", inline=False)
    embed.set_footer(text="OGS Community • Erişim Onay Sistemi")

    # Yetkili Listesi Oluştur (Sen + Sup Rolündekiler)
    authorized_users = []
    
    # 1. Sana DM Bildirimi
    try:
        admin_user = await bot.fetch_user(MY_ID)
        authorized_users.append(admin_user)
    except Exception:
        pass

    # 2. Sup Rolündekilere DM Bildirimi
    if guild:
        sup_role = discord.utils.get(guild.roles, name=SUP_ROLE_NAME)
        if sup_role:
            for member in sup_role.members:
                if member.id != MY_ID:  # Tekrar mesaj gitmesin diye kontrol
                    authorized_users.append(member)

    # Bildirimleri Gönder
    sent_count = 0
    for target in set(authorized_users):
        try:
            view = AccessRequestView(requester=requester, comp_name=comp_adi)
            await target.send(embed=embed, view=view)
            sent_count += 1
        except Exception:
            pass

    await interaction.response.send_message(
        f"✅ **{comp_adi}** için erişim talebiniz yetkililere ({sent_count} yetkili) iletildi! Onaylandığında bilgilendirileceksiniz.",
        ephemeral=True
    )

# --- BOT HAZIR OLDUĞUNDA ---
@bot.event
async def on_ready():
    await init_db()
    
    if not check_daily_reset.is_running():
        check_daily_reset.start()
    
    try:
        synced = await bot.tree.sync(guild=GUILD_OBJ)
        print(f"✅ {len(synced)} komut OGS sunucusuna başarıyla yüklendi!")
    except Exception as e:
        print(f"❌ Komut senkronizasyon hatası: {e}")

    print(f"✅ {bot.user.name} başarıyla bağlandı!")

# --- BOTU BAŞLAT ---
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ HATA: DISCORD_TOKEN çevre değişkeni bulunamadı!")
