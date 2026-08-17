from flask import Flask
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- 1. FLASK SUNUCUSU (7/24 Aktif Kalması İçin) ---
app = Flask('')


@app.route('/')
def home():
  return "Bot aktif ve çalışıyor!"


def run():
  app.run(host='0.0.0.0', port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# --- BURAYI KENDİ HESAPLARINA GÖRE DÜZENLE ---
DRIVE_ACCOUNTS = {
    "Ana Proje": {"folder_id": "KLASOR_ID_1", "json": "hesap1.json"},
    "Yedek Proje": {"folder_id": "KLASOR_ID_2", "json": "hesap2.json"},
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# --- DRIVE İZİN FONKSİYONU ---
def add_permission(proje_ismi, target_email):
  try:
    acc = DRIVE_ACCOUNTS[proje_ismi]
    creds = service_account.Credentials.from_service_account_file(
        acc["json"], scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds)

    service.permissions().create(
        fileId=acc["folder_id"],
        body={
            "type": "user",
            "role": "reader",
            "emailAddress": target_email,
        },
        sendNotificationEmail=True,
    ).execute()
    return True
  except Exception as e:
    print(f"Hata: {e}")
    return False


# --- DÜĞME (SELECT MENU) YAPISI ---
class ProjectSelect(discord.ui.Select):

  def __init__(self, user_email):
    self.user_email = user_email
    options = [
        discord.SelectOption(label=name) for name in DRIVE_ACCOUNTS.keys()
    ]
    super().__init__(
        placeholder="Hangi projeye erişim istiyorsun?", options=options
    )

  async def callback(self, interaction: discord.Interaction):
    proje = self.values[0]
    success = add_permission(proje, self.user_email)

    if success:
      await interaction.response.send_message(
          f"✅ {proje} için `{self.user_email}` adresine erişim verildi!",
          ephemeral=True,
      )
    else:
      await interaction.response.send_message(
          "❌ Bir hata oluştu!", ephemeral=True
      )


class ProjectView(discord.ui.View):

  def __init__(self, user_email):
    super().__init__()
    self.add_item(ProjectSelect(user_email))


# --- KOMUTLAR ---
@bot.tree.command(name="erisim", description="Drive erişimi al")
async def erisim(interaction: discord.Interaction, gmail: str):
  # Basit bir kayıt/işlem sonrası menüyü aç
  view = ProjectView(user_email=gmail)
  await interaction.response.send_message(
      "Hangi hesaptan erişim alalım?", view=view, ephemeral=True
  )


@bot.event
async def on_ready():
  await bot.tree.sync()
  print("Bot hazır!")


# --- 2. SUNUCUYU BAŞLAT VE BOTU ÇALIŞTIR ---
keep_alive()  # Önce Flask sunucusunu arka planda ayağa kaldırıyoruz
bot.run("TOKEN_BURAYA")  # En sonda bot çalışıyor
