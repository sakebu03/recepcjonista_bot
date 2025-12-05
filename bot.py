import os
import discord
from discord.ext import commands
from discord.utils import get
import asyncio

# ===================== KONFIGURACJA POD CIEBIE =====================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Nazwa roli startowej (tworzy się sama, jeśli jej nie ma)
START_ROLE_NAME = "Nowy"

# Nazwa kategorii, w której bot będzie tworzył kanały ankiet
WELCOME_CATEGORY_NAME = "Powitania"

# ----- WIEK -----
# Emoji -> kod wewnętrzny
AGE_EMOJIS = {
    "1️⃣": "under_13",
    "2️⃣": "13_15",
    "3️⃣": "16_17",
    "4️⃣": "18_20",
    "5️⃣": "21_24",
    "6️⃣": "25_plus",
}

# Kod wewnętrzny -> nazwa roli (takie dokładnie nazwy ról stworzy bot)
AGE_ROLE_NAMES = {
    "under_13": "Wiek < 13",
    "13_15": "Wiek 13–15",
    "16_17": "Wiek 16–17",
    "18_20": "Wiek 18–20",
    "21_24": "Wiek 21–24",
    "25_plus": "Wiek 25+",
}

AGE_ROLE_NAME_SET = set(AGE_ROLE_NAMES.values())

# ----- PŁEĆ -----
SEX_EMOJIS = {
    "♂️": "male",
    "♀️": "female",
    "⚧️": "other",
}

SEX_ROLE_NAMES = {
    "male": "Mężczyzna",
    "female": "Kobieta",
    "other": "Inna płeć",
}

SEX_ROLE_NAME_SET = set(SEX_ROLE_NAMES.values())

# ----- WOJEWÓDZTWA -----
# Emoji -> nazwa województwa (równocześnie nazwa roli)
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

# ===================== USTAWIENIA BOTA =====================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user} (ID: {bot.user.id})")


# ===================== POMOCNICZE FUNKCJE =====================

async def get_or_create_role(guild: discord.Guild, name: str) -> discord.Role:
    """Znajdź rolę po nazwie, a jeśli nie istnieje – utwórz ją."""
    role = get(guild.roles, name=name)
    if role is not None:
        return role

    # Możesz tu dodać kolory dla konkretnych ról jeśli chcesz
    print(f"ℹ️ Tworzę nową rolę: {name} na serwerze {guild.name}")
    role = await guild.create_role(
        name=name,
        reason="Automatycznie utworzone przez bota (brakowało roli)",
    )
    return role


async def get_or_create_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    """Znajdź kategorię po nazwie, a jeśli nie istnieje – utwórz ją."""
    category = get(guild.categories, name=name)
    if category is not None:
        return category

    print(f"ℹ️ Tworzę kategorię: {name} na serwerze {guild.name}")
    category = await guild.create_category(name=name, reason="Kategoria na kanały ankiet bota")
    return category


# ===================== GŁÓWNA FUNKCJA ANKIETY =====================

async def przeprowadz_ankiete(member: discord.Member, uzyj_roli_startowej: bool):
    """
    Tworzy prywatny kanał, zadaje 3 pytania na reakcjach (wiek, województwo, płeć),
    ustawia role i na końcu usuwa kanał.

    uzyj_roli_startowej = True  -> tryb dla nowych użytkowników (on_member_join)
    uzyj_roli_startowej = False -> tryb komendy !ankieta (bez blokady serwera)
    """
    guild = member.guild

    # 0. Upewniamy się, że podstawowe rzeczy istnieją (rola startowa, kategoria)
    start_role = await get_or_create_role(guild, START_ROLE_NAME)
    category = await get_or_create_category(guild, WELCOME_CATEGORY_NAME)

    # 1. Nadaj rolę startową tylko dla nowych userów
    if uzyj_roli_startowej and start_role not in member.roles:
        await member.add_roles(start_role, reason="Nowy użytkownik - rola startowa")

    # 2. Utwórz prywatny kanał
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True
        ),
    }

    channel_name = f"ankieta-{member.name}-{member.id}".lower().replace(" ", "-")
    if len(channel_name) > 90:
        channel_name = channel_name[:90]

    welcome_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        reason=f"Kanał ankiety dla {member}",
    )

    try:
        # 3. Powitanie
        if uzyj_roli_startowej:
            intro = (
                f"Hej {member.mention}! 👋\n"
                f"Witamy na serwerze! Mam krótką ankietę, żeby nadać Ci odpowiednie role."
            )
        else:
            intro = (
                f"Hej {member.mention}! 👋\n"
                f"Tutaj możesz zmienić swoje główne role (wiek, województwo, płeć)."
            )
        await welcome_channel.send(intro)

        # ========== PYTANIE 1: WIEK (REACTIONS) ==========
        age_text = (
            "**Pytanie 1:** Ile masz lat?\n"
            "Reaguj:\n"
            "1️⃣  -  mniej niż 13 lat\n"
            "2️⃣  -  13–15 lat\n"
            "3️⃣  -  16–17 lat\n"
            "4️⃣  -  18–20 lat\n"
            "5️⃣  -  21–24 lata\n"
            "6️⃣  -  25+ lat\n"
        )
        msg_age = await welcome_channel.send(age_text)
        for emoji in AGE_EMOJIS.keys():
            await msg_age.add_reaction(emoji)

        def check_age(reaction, user):
            return (
                user == member
                and reaction.message.id == msg_age.id
                and str(reaction.emoji) in AGE_EMOJIS
            )

        reaction_age, _ = await bot.wait_for("reaction_add", timeout=300, check=check_age)
        age_choice_key = AGE_EMOJIS[str(reaction_age.emoji)]  # np. "16_17"

        # ========== PYTANIE 2: WOJEWÓDZTWO (REACTIONS) ==========
        woj_text_lines = [
            "**Pytanie 2:** Z jakiego województwa jesteś?\n",
            "Wybierz reakcję:",
        ]
        for emoji, name in VOIVODESHIP_EMOJIS.items():
            woj_text_lines.append(f"{emoji}  -  {name}")

        msg_woj = await welcome_channel.send("\n".join(woj_text_lines))
        for emoji in VOIVODESHIP_EMOJIS.keys():
            await msg_woj.add_reaction(emoji)

        def check_woj(reaction, user):
            return (
                user == member
                and reaction.message.id == msg_woj.id
                and str(reaction.emoji) in VOIVODESHIP_EMOJIS
            )

        reaction_woj, _ = await bot.wait_for("reaction_add", timeout=300, check=check_woj)
        woj_choice_name = VOIVODESHIP_EMOJIS[str(reaction_woj.emoji)]  # np. "mazowieckie"

        # ========== PYTANIE 3: PŁEĆ (REACTIONS) ==========
        sex_text = (
            "**Pytanie 3:** Jaką masz płeć?\n"
            "Reaguj:\n"
            "♂️  -  mężczyzna\n"
            "♀️  -  kobieta\n"
            "⚧️  -  inna\n"
        )
        msg_sex = await welcome_channel.send(sex_text)
        for emoji in SEX_EMOJIS.keys():
            await msg_sex.add_reaction(emoji)

        def check_sex(reaction, user):
            return (
                user == member
                and reaction.message.id == msg_sex.id
                and str(reaction.emoji) in SEX_EMOJIS
            )

        reaction_sex, _ = await bot.wait_for("reaction_add", timeout=300, check=check_sex)
        sex_choice_key = SEX_EMOJIS[str(reaction_sex.emoji)]  # "male"/"female"/"other"

        # ================== NADAWANIE RÓL ==================

        # ---- WIEK ----
        # usuwamy wszystkie stare role wiekowe
        age_roles_to_remove = [r for r in member.roles if r.name in AGE_ROLE_NAME_SET]
        if age_roles_to_remove:
            await member.remove_roles(*age_roles_to_remove, reason="Czyszczenie starych ról wiekowych")

        age_role_name = AGE_ROLE_NAMES.get(age_choice_key)
        if age_role_name:
            new_age_role = await get_or_create_role(guild, age_role_name)
            await member.add_roles(new_age_role, reason="Ustawienie roli wiekowej")

        # ---- WOJEWÓDZTWO ----
        voiv_roles_to_remove = [r for r in member.roles if r.name in VOIVODESHIP_ROLE_NAME_SET]
        if voiv_roles_to_remove:
            await member.remove_roles(*voiv_roles_to_remove, reason="Czyszczenie starego województwa")

        if woj_choice_name in VOIVODESHIP_ROLE_NAME_SET:
            new_voiv_role = await get_or_create_role(guild, woj_choice_name)
            await member.add_roles(new_voiv_role, reason="Ustawienie roli województwa")

        # ---- PŁEĆ ----
        sex_roles_to_remove = [r for r in member.roles if r.name in SEX_ROLE_NAME_SET]
        if sex_roles_to_remove:
            await member.remove_roles(*sex_roles_to_remove, reason="Czyszczenie starych ról płci")

        sex_role_name = SEX_ROLE_NAMES.get(sex_choice_key)
        if sex_role_name:
            new_sex_role = await get_or_create_role(guild, sex_role_name)
            await member.add_roles(new_sex_role, reason="Ustawienie roli płci")

        # 6. Zabierz rolę startową (tylko dla nowych)
        if uzyj_roli_startowej and start_role in member.roles:
            await member.remove_roles(start_role, reason="Zakończona weryfikacja")

        # 7. Info końcowe
        if uzyj_roli_startowej:
            msg = (
                "✅ Dzięki za odpowiedzi! Role zostały nadane, a reszta serwera powinna być już widoczna.\n"
                "Ten kanał za chwilę zniknie. Miłego pobytu! 🎉"
            )
        else:
            msg = (
                "✅ Zaktualizowałem Twoje role (wiek, województwo, płeć).\n"
                "Ten kanał zaraz usunę. Jeśli chcesz, możesz kiedyś znowu użyć komendy `!ankieta`."
            )

        await welcome_channel.send(msg)
        await asyncio.sleep(5)

    except asyncio.TimeoutError:
        await welcome_channel.send(
            "⏰ Minął czas na odpowiedź (5 minut). Spróbuj ponownie później albo poproś administrację."
        )
        await asyncio.sleep(5)
    finally:
        # 8. Usuń kanał
        try:
            await welcome_channel.delete(reason="Zakończono lub przerwano proces ankiety")
        except discord.Forbidden:
            print("❌ Nie mam uprawnień do usunięcia kanału ankiety.")


# ===================== NOWY USER – ON_MEMBER_JOIN =====================

@bot.event
async def on_member_join(member: discord.Member):
    print(f"👤 Nowy użytkownik: {member} dołączył na {member.guild.name}")
    await przeprowadz_ankiete(member, uzyj_roli_startowej=True)


# ===================== KOMENDA !ankieta =====================

@bot.command(name="ankieta")
async def ankieta_cmd(ctx: commands.Context):
    """Pozwala użytkownikowi zmienić swoje główne role (wiek, województwo, płeć)."""
    if ctx.author.bot:
        return

    await ctx.send(f"{ctx.author.mention} tworzę dla Ciebie prywatny kanał z ankietą 🔐", delete_after=10)

    # (opcjonalnie) usuń wiadomość z komendą, żeby nie zaśmiecać
    try:
        await ctx.message.delete(delay=2)
    except discord.Forbidden:
        pass

    await przeprowadz_ankiete(ctx.author, uzyj_roli_startowej=False)


# ===================== START BOTA =====================

bot.run(TOKEN)
