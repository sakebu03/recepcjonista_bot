import os
import discord
from discord.ext import commands
from discord.utils import get
import asyncio

# ===================== PODSTAWY =====================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===================== KONFIGURACJA =====================

START_ROLE_NAME = "Nowy"
PLUS18_ROLE_NAME = "+18"

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

AGE_KEYS_PLUS18 = {"k19", "k22", "k26"}
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

# ----- WOJEWÓDZTWA (przykład – możesz dodać wszystkie) -----

WOJ_EMOJIS = {
    "1️⃣": "mazowieckie",
    "2️⃣": "malopolskie",
    "3️⃣": "slaskie",
}

WOJ_ROLE_NAMES = {
    "mazowieckie": "Mazowieckie",
    "malopolskie": "Małopolskie",
    "slaskie": "Śląskie",
}

WOJ_ROLE_NAME_SET = set(WOJ_ROLE_NAMES.values())

# ===================== FUNKCJE POMOCNICZE =====================

async def get_or_create_role(guild, role_name):
    role = get(guild.roles, name=role_name)
    if role is None:
        role = await guild.create_role(name=role_name)
    return role

async def remove_roles_by_name_set(member, name_set):
    for role in member.roles:
        if role.name in name_set:
            await member.remove_roles(role)

async def aktualizuj_role_18plus(member, age_key):
    guild = member.guild
    role_18 = get(guild.roles, name=PLUS18_ROLE_NAME)
    if role_18 is None:
        role_18 = await guild.create_role(name=PLUS18_ROLE_NAME)

    if age_key in AGE_KEYS_PLUS18:
        if role_18 not in member.roles:
            await member.add_roles(role_18)
    else:
        if role_18 in member.roles:
            await member.remove_roles(role_18)

async def wait_for_reaction(ctx, message, emoji_map):
    for emoji in emoji_map:
        await message.add_reaction(emoji)

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == message.id
            and str(reaction.emoji) in emoji_map
        )

    reaction, _ = await bot.wait_for("reaction_add", timeout=300, check=check)
    return emoji_map[str(reaction.emoji)]

# ===================== ANKIETA =====================

async def przeprowadz_ankiete(member):
    guild = member.guild

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True),
    }

    channel = await guild.create_text_channel(
        f"ankieta-{member.name}",
        overwrites=overwrites
    )

    ctx = await bot.get_context(await channel.send("Start ankiety"))

    # ----- WIEK -----
    msg = await channel.send(
        "**Pytanie 1:** Ile masz lat?\n"
        "1️⃣ 12–15\n"
        "2️⃣ 16–18\n"
        "3️⃣ 19–21\n"
        "4️⃣ 22–25\n"
        "5️⃣ 26+"
    )
    age_key = await wait_for_reaction(ctx, msg, AGE_EMOJIS)

    await remove_roles_by_name_set(member, AGE_ROLE_NAME_SET)
    age_role = await get_or_create_role(guild, AGE_ROLE_NAMES[age_key])
    await member.add_roles(age_role)
    await aktualizuj_role_18plus(member, age_key)

    # ----- PŁEĆ -----
    msg = await channel.send(
        "**Pytanie 2:** Jaką masz płeć?\n"
        "1️⃣ Mężczyzna\n"
        "2️⃣ Kobieta\n"
        "3️⃣ Inna"
    )
    sex_key = await wait_for_reaction(ctx, msg, SEX_EMOJIS)

    await remove_roles_by_name_set(member, SEX_ROLE_NAME_SET)
    sex_role = await get_or_create_role(guild, SEX_ROLE_NAMES[sex_key])
    await member.add_roles(sex_role)

    # ----- WOJEWÓDZTWO -----
    msg = await channel.send(
        "**Pytanie 3:** Z jakiego województwa jesteś?\n"
        "1️⃣ Mazowieckie\n"
        "2️⃣ Małopolskie\n"
        "3️⃣ Śląskie"
    )
    woj_key = await wait_for_reaction(ctx, msg, WOJ_EMOJIS)

    await remove_roles_by_name_set(member, WOJ_ROLE_NAME_SET)
    woj_role = await get_or_create_role(guild, WOJ_ROLE_NAMES[woj_key])
    await member.add_roles(woj_role)

    await channel.send("✅ Ankieta zakończona. Kanał zostanie usunięty.")
    await asyncio.sleep(5)
    await channel.delete()

# ===================== KOMENDA =====================

@bot.command(name="ankieta")
async def ankieta_cmd(ctx):
    if ctx.author.bot:
        return
    await przeprowadz_ankiete(ctx.author)

# ===================== START =====================

print("TOKEN OK:", TOKEN is not None)
bot.run(TOKEN)
