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
MY_ID = 1266281343957078029     # Hasan (Sınırsız Kota & Yetkili)
GUILD_OBJ = discord.Object(id=GUILD_ID)

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
        for child in self.children:
            child.disabled = True
        
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Durum", value="🟢 **ONAYLANDI**", inline=False)
        embed.add_field(name="Erişimi Veren Yetkili", value=interaction.user.mention, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            await self.requester.send(
                f"🎉 **{self.comp_name}** comp'u için erişim talebiniz **{interaction.user.display_name}** tarafından **ONAYLANDI**!"
            )
        except Exception:
            pass

    @discord.ui.button(label="Reddet ❌", style=discord.ButtonStyle.danger, custom_id="access_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="Durum", value="🔴 **REDDEDİLDİ**", inline=False)
        embed.add_field(name="İşlemi Yapan Yetkili", value=interaction.user.mention, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            await self.requester.send(
                f"❌ **{self.comp_name}** comp'u için erişim talebiniz **{interaction.user.display_name}** tarafından **REDDEDİLDİ**."
            )
        except Exception:
            pass

# --- /KOTA KOMUTU ---
@bot.tree.command(name="kota", description="Mevcut günlük klip kotanızı kontrol edin.", guild=GUILD_OBJ)
async def kota(interaction: discord.Interaction):
    user_id = interaction.user.id

    if user_id == MY_ID:
        embed = discord.Embed(
            title="📊 Günlük Klip Kotan",
            description="Kalan Kotan: **∞ / Sınırsız** (Kurucu Yetkisi)",
            color=discord.Color.gold()
        )
        embed.set_footer(text="OGS Community • Premium Clip Sistemi")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    async with aiosqlite.connect("kota.db") as db:
        async with db.execute("SELECT remaining_quota FROM quotas WHERE user_id = ?", (user_id,)) as cursor:
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
    user_id = interaction.user.id

    if user_id == MY_ID:
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
        async with db.execute("SELECT remaining_quota FROM quotas WHERE user_id = ?", (user_id,)) as cursor:
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
                (user_id, new_quota, new_quota)
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

    try:
        admin_user = await bot.fetch_user(MY_ID)
        
        embed = discord.Embed(
            title="📩 Yeni Erişim Talebi",
            color=discord.Color.gold()
        )
        embed.add_field(name="Talep Eden Üye", value=f"{requester.mention} (`{requester.id}`)", inline=False)
        embed.add_field(name="Erişim İstenen Comp", value=f"**{comp_adi}**", inline=False)
        embed.set_footer(text="OGS Community • Erişim Onay Sistemi")
        
        view = AccessRequestView(requester=requester, comp_name=comp_adi)
        await admin_user.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ **{comp_adi}** için erişim talebiniz yetkililere iletildi! Onaylandığında bilgilendirileceksiniz.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Talebiniz iletilirken bir hata oluştu: {e}",
            ephemeral=True
        )

# --- BOT HAZIR OLDUĞUNDA ---
@bot.event
async def on_ready():
    await init_db()
    
    if not check_daily_reset.is_running():
        check_daily_reset.start()
    
    try:
        # Doğrudan OGS sunucusuna tanımlanan komutları senkronize et
        synced = await bot.tree.sync(guild=GUILD_OBJ)
        print(f"✅ BİNGO: {len(synced)} komut OGS sunucusuna sıfır hatayla yüklendi!")
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
