import asyncio
from datetime import time, timezone
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

# --- BOT VE SUNUCU AYARLARI ---
TOKEN = "MTUzODUwOTQxNzMzMzUyMjQ1Mg.Gb9qIo.oaKFBlGYZ66kN0oNhwRq470hJwVceaCghz6I2o"  # <--- Bot Token'ını buraya tırnakların içine yapıştır
GUILD_ID = 1429466809110626377
PREMIUM_ROLE_ID = 1429471364225433620
MAX_KOTA = 10

# --- BOT TANIMLAMA ---
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=".", intents=intents)

# --- VERİTABANI İŞLEMLERİ ---
async def init_db():
    async with aiosqlite.connect("kota.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kullanicilar (
                user_id INTEGER PRIMARY KEY,
                kalan_kota INTEGER DEFAULT 10
            )
        """)
        await db.commit()

async def get_kota(user_id: int) -> int:
    async with aiosqlite.connect("kota.db") as db:
        async with db.execute("SELECT kalan_kota FROM kullanicilar WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                await db.execute("INSERT INTO kullanicilar (user_id, kalan_kota) VALUES (?, ?)", (user_id, MAX_KOTA))
                await db.commit()
                return MAX_KOTA
            return row[0]

async def update_kota(user_id: int, yeni_kota: int):
    async with aiosqlite.connect("kota.db") as db:
        await db.execute("UPDATE kullanicilar SET kalan_kota = ? WHERE user_id = ?", (yeni_kota, user_id))
        await db.commit()

# --- GECE 00:00 KOTA SIFIRLAMA ---
@tasks.loop(time=time(hour=0, minute=0, second=0, tzinfo=timezone.utc))
async def reset_kotalar():
    async with aiosqlite.connect("kota.db") as db:
        await db.execute("UPDATE kullanicilar SET kalan_kota = ?", (MAX_KOTA,))
        await db.commit()
    print("[SİSTEM] Gece 00:00: Tüm kotalar 10 olarak yenilendi.")

# --- BOT OLAYLARI ---
@bot.event
async def on_ready():
    await init_db()
    if not reset_kotalar.is_running():
        reset_kotalar.start()
    
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"✅ {bot.user.name} OGS Community için başarıyla bağlandı!")

# --- SLASH KOMUTLARI ---

@bot.tree.command(name="kota", description="Kalan clip alma kotanı gösterir.")
async def kota_sorgula(interaction: discord.Interaction):
    role = interaction.guild.get_role(PREMIUM_ROLE_ID)
    if role not in interaction.user.roles:
        await interaction.response.send_message("❌ Bu komutu sadece **OGS Premium** üyeleri kullanabilir.", ephemeral=True)
        return

    kalan = await get_kota(interaction.user.id)
    embed = discord.Embed(
        title="🎬 OGS Premium Clip Kotası",
        description=f"Merhaba {interaction.user.mention},\n\n**Kalan Clip Hakkın:** `{kalan} / {MAX_KOTA}`\n**Sıfırlanma Saati:** Gece 00:00 (TSİ)",
        color=discord.Color.gold()
    )
    embed.set_footer(text="OGS Community • Premium Clip Sistemi")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="clip", description="Clip alma isteği gönderir ve kotadan 1 düşer.")
async def clip_al(interaction: discord.Interaction, clip_url: str):
    role = interaction.guild.get_role(PREMIUM_ROLE_ID)
    if role not in interaction.user.roles:
        await interaction.response.send_message("❌ Clip almak için **OGS Premium** üyesi olmalısın.", ephemeral=True)
        return

    kalan = await get_kota(interaction.user.id)
    if kalan <= 0:
        await interaction.response.send_message("⚠️ Günlük **10/10** clip alma limitine ulaştın! Kotan gece 00:00'da yenilenecek.", ephemeral=True)
        return

    yeni_kota = kalan - 1
    await update_kota(interaction.user.id, yeni_kota)

    embed = discord.Embed(
        title="✅ Clip İsteği Alındı",
        description=f"**Link:** {clip_url}\n\n**Kalan Kotan:** `{yeni_kota} / {MAX_KOTA}`",
        color=discord.Color.green()
    )
    embed.set_footer(text="OGS Community • Premium Clip Sistemi")
    await interaction.response.send_message(embed=embed)
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Bot Aktif!"
Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()

bot.run(TOKEN)
