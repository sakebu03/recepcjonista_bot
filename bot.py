import os
import asyncio
import discord
from discord.ext import commands
from discord.utils import get

# ===================== TOKEN (z Railway ENV) =====================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# ===================== INTENTS =====================

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===================== KONFIGURACJA =====================

WELCOME_CATEGORY_NAME = "Powitania"
START_ROLE_NAME = "Nowy"

PLUS18_ROLE_NAME = "+18"
AGE_KEYS_PLUS18 = {"k19", "k22", "k26"}

# ----- WIEK -----
AGE_EMOJIS = {
    "1️⃣": "k12",
    "2️⃣": "k16",
    "3️⃣": "k19",
    "4️⃣": "k22",
    "5️⃣": "k26",
}

AGE_ROLE_NAMES = {
    "k12": "12-15",
    "k16": "16-18",
    "k19": "19-21",
    "k22": "22-25",
    "k26": "26+",
}
AGE_ROLE_NAME_SET = set(AGE_ROLE_NAMES.values())

# ----- PŁEĆ -----
SEX_EMOJIS = {
    "1️⃣": "male",
    "2️⃣": "female",
    "3️⃣": "other",
}
SEX_ROLE_NAMES = {
    "male": "Mężczyzna",
    "female": "Kobieta",
    "other": "Inna",
}
SEX_ROLE_NAME_SET = set(SEX_ROLE_NAMES.values())

# ----- WOJEWÓDZTWA (tu masz pełny zestaw) -----
VOIVODESHIP_EMOJIS = {
    "1️⃣":  "dolnośląskie",
    "2️⃣":  "kujawsko-pomorskie",
    "3️⃣":  "lubelskie",
    "4️⃣":  "lubuskie",
    "5️⃣":  "łódzkie",
    "6️⃣":  "małopolskie",
    "7️⃣":  "mazowieckie",
    "8️⃣":  "opolskie",
    "9️⃣":  "podkarpackie",
    "🔟":  "podlaskie",
    "🅰️": "pomorskie",
    "🅱️": "śląskie",
    "🆎": "świętokrzyskie",
    "🆑": "warmińsko-mazurskie",
    "🅾️": "wielkopolskie",
    "🆘": "zachodniopomorskie",
}
VOIVODESHIP_ROLE_NAME_SET = set(VOIVODESHIP_EMOJIS.values())

# ===================== POMOCNICZE =====================

@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user} (ID: {bot.user.id})")

async def get_or_create_role(guild: discord.Guild, name: str) -> discord.Role:
    role = get(guild.roles, name=name)
    if role is not None:
        return role
    print(f"ℹ️ Tworzę nową rolę: {name} na serwerze {guild.name}")
    return await guild.create_role(name=name, reason="Auto-rola bota")

async def get_or_create_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    cat = get(guild.categories, name=name)
    if cat is not None:
        return cat
    print(f"ℹ️ Tworzę kategorię: {name} na serwerze {guild.name}")
    return await guild.create_category(name=name, reason="Kategoria na ankiety bota")

async def remove_roles_by_name_set(member: discord.Member, name_set: set[str], reason: str):
    roles_to_remove = [r for r in member.roles if r.name in name_set]
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove, reason=reason)

async def aktualizuj_role_18plus(member: discord.Member, age_key: str):
    guild = member.guild
    role_18 = get(guild.roles, name=PLUS18_ROLE_NAME)
    if role_18 is None:
        role_18 = await guild.create_role(name=PLUS18_ROLE_NAME, reason="Rola dostępu NSFW (+18)")

    if age_key in AGE_KEYS_PLUS18:
        if role_18 not in member.roles:
            await member.add_roles(role_18, reason="Wiek 18+")
    else:
        if role_18 in member.roles:
            await member.remove_roles(role_18, reason="Wiek < 18")

async def wait_for_reaction(member: discord.Member, message: discord.Message, emoji_map: dict, timeout: int = 300):
    # dodaj reakcje
    for emoji in emoji_map.keys():
        await message.add_reaction(emoji)

    def check(reaction: discord.Reaction, user: discord.User):
        return (
            user.id == member.id
            and reaction.message.id == message.id
            and str(reaction.emoji) in emoji_map
        )

    reaction, _ = await bot.wait_for("reaction_add", timeout=timeout, check=check)
    return emoji_map[str(reaction.emoji)]

# ===================== ANKIETA (kanał prywatny) =====================

async def przeprowadz_ankiete(member: discord.Member, uzyj_roli_startowej: bool):
    guild = member.guild

    start_role = await get_or_create_role(guild, START_ROLE_NAME)
    category = await get_or_create_category(guild, WELCOME_CATEGORY_NAME)

    if uzyj_roli_startowej and start_role not in member.roles:
        await member.add_roles(start_role, reason="Nowy użytkownik")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
    }

    channel_name = f"ankieta-{member.name}-{member.id}".lower().replace(" ", "-")[:90]
    ch = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites, reason="Kanał ankiety")

    try:
        await ch.send(f"Hej {member.mention}! 👋 Zróbmy krótką ankietę na role.")

        # 1) WIEK
        msg_age = await ch.send(
            "**Pytanie 1:** Ile masz lat?\n"
            "1️⃣ 12–15\n"
            "2️⃣ 16–18\n"
            "3️⃣ 19–21\n"
            "4️⃣ 22–25\n"
            "5️⃣ 26+\n"
        )
        age_key = await wait_for_reaction(member, msg_age, AGE_EMOJIS)

        await remove_roles_by_name_set(member, AGE_ROLE_NAME_SET, "Czyszczenie ról wieku")
        age_role = await get_or_create_role(guild, AGE_ROLE_NAMES[age_key])
        await member.add_roles(age_role, reason="Ustawienie roli wieku")
        await aktualizuj_role_18plus(member, age_key)

        # 2) WOJEWÓDZTWO
        lines = ["**Pytanie 2:** Z jakiego województwa jesteś?", "Wybierz reakcję:"]
        for emoji, name in VOIVODESHIP_EMOJIS.items():
            lines.append(f"{emoji} - {name}")
        msg_woj = await ch.send("\n".join(lines))
        woj_name = await wait_for_reaction(member, msg_woj, VOIVODESHIP_EMOJIS)

        await remove_roles_by_name_set(member, VOIVODESHIP_ROLE_NAME_SET, "Czyszczenie ról województw")
        woj_role = await get_or_create_role(guild, woj_name)
        await member.add_roles(woj_role, reason="Ustawienie województwa")

        # 3) PŁEĆ
        msg_sex = await ch.send(
            "**Pytanie 3:** Jaką masz płeć?\n"
            "1️⃣ Mężczyzna\n"
            "2️⃣ Kobieta\n"
            "3️⃣ Inna\n"
        )
        sex_key = await wait_for_reaction(member, msg_sex, SEX_EMOJIS)

        await remove_roles_by_name_set(member, SEX_ROLE_NAME_SET, "Czyszczenie ról płci")
        sex_role = await get_or_create_role(guild, SEX_ROLE_NAMES[sex_key])
        await member.add_roles(sex_role, reason="Ustawienie płci")

        if uzyj_roli_startowej and start_role in member.roles:
            await member.remove_roles(start_role, reason="Ankieta zakończona")

        await ch.send("✅ Gotowe! Nadałem role. Ten kanał zaraz zniknie.")
        await asyncio.sleep(5)

    except asyncio.TimeoutError:
        await ch.send("⏰ Minął czas na odpowiedź. Użyj `!ankieta` ponownie.")
        await asyncio.sleep(5)

    finally:
        try:
            await ch.delete(reason="Sprzątanie kanału ankiety")
        except discord.Forbidden:
            print("❌ Brak uprawnień do usunięcia kanału ankiety.")

# ===================== KOMENDA =====================

@bot.command(name="ankieta")
async def ankieta_cmd(ctx: commands.Context):
    if ctx.author.bot:
        return
    try:
        await ctx.message.delete(delay=2)
    except discord.Forbidden:
        pass
    await przeprowadz_ankiete(ctx.author, uzyj_roli_startowej=False)

# ===================== START =====================

if not TOKEN:
    raise RuntimeError("Brak DISCORD_BOT_TOKEN w zmiennych środowiskowych!")

bot.run(TOKEN)
