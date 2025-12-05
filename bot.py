import os
import asyncio
import discord
from discord.ext import commands

# === KONFIGURACJA ===

# TOKEN pobieramy ze zmiennej środowiskowej (Railway → Variables → TOKEN)
TOKEN = os.getenv("TOKEN")

if TOKEN is None:
    raise RuntimeError("Brak zmiennej środowiskowej TOKEN. Ustaw ją w Railway / lokalnie.")

WELCOME_CATEGORY_NAME = "Rejestracja"   # kategoria na kanały rejestracyjne
ADMIN_ROLE_NAME = "Administracja"       # rola administracji, która ma widzieć wszystkie kanały rejestracyjne

intents = discord.Intents.default()
intents.members = True  # wymagane dla on_member_join

bot = commands.Bot(command_prefix="!", intents=intents)

# Flaga, żeby nie odpalać migracji wiele razy
migration_done = False

# Lista województw (wszystkie)
VOIVODESHIPS = [
    "Dolnośląskie",
    "Kujawsko-Pomorskie",
    "Lubelskie",
    "Lubuskie",
    "Łódzkie",
    "Małopolskie",
    "Mazowieckie",
    "Opolskie",
    "Podkarpackie",
    "Podlaskie",
    "Pomorskie",
    "Śląskie",
    "Świętokrzyskie",
    "Warmińsko-Mazurskie",
    "Wielkopolskie",
    "Zachodniopomorskie",
]

AGE_ROLES = ["13-15", "16-18", "19-24", "25+"]


# === EVENT: BOT GOTOWY ===

@bot.event
async def on_ready():
    global migration_done
    print(f"Zalogowano jako {bot.user} (ID: {bot.user.id})")
    print("Bot jest gotowy.")

    # żeby nie odpalać tego przy każdym reconnect
    if migration_done:
        return
    migration_done = True

    # AUTOMATYCZNE wymuszenie rejestracji na wszystkich obecnych użytkownikach
    print("[MIGRACJA] Start automatycznej rejestracji obecnych użytkowników...")

    for guild in bot.guilds:
        admin_role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)

        for member in guild.members:
            # pomijamy boty
            if member.bot:
                continue

            # pomijamy administrację
            if admin_role and admin_role in member.roles:
                continue

            # pomijamy tych, którzy wyglądają na zarejestrowanych
            if is_already_registered(member):
                continue

            print(f"[MIGRACJA] Wymuszam rejestrację na {member} w {guild.name}")
            await start_registration_for_member(member)

            # pauza, żeby nie wpaść w rate limit na większych serwerach
            await asyncio.sleep(1)

    print("[MIGRACJA] Zakończono automatyczną rejestrację obecnych użytkowników.")


# === FUNKCJE POMOCNICZE ===

async def get_or_create_role(guild: discord.Guild, role_name: str):
    """Znajduje lub tworzy rolę o podanej nazwie."""
    role = discord.utils.get(guild.roles, name=role_name)
    if role is not None:
        return role

    try:
        role = await guild.create_role(
            name=role_name,
            reason="Automatyczne tworzenie ról przez bota rejestracyjnego"
        )
        print(f"[INFO] Utworzono rolę: {role_name} na serwerze {guild.name}")
        return role
    except discord.Forbidden:
        print(f"[BŁĄD] Brak uprawnień do tworzenia roli: {role_name}")
    except Exception as e:
        print(f"[BŁĄD] Nie udało się utworzyć roli {role_name}: {e}")
    return None


async def get_or_create_welcome_category(guild: discord.Guild):
    """Znajduje lub tworzy kategorię na kanały rejestracyjne."""
    category = discord.utils.get(guild.categories, name=WELCOME_CATEGORY_NAME)
    if category is not None:
        return category

    try:
        category = await guild.create_category(
            name=WELCOME_CATEGORY_NAME,
            reason="Kategoria na kanały rejestracyjne bota"
        )
        print(f"[INFO] Utworzono kategorię: {WELCOME_CATEGORY_NAME} na serwerze {guild.name}")
        return category
    except discord.Forbidden:
        print("[BŁĄD] Bot nie ma uprawnień do tworzenia kategorii.")
    except Exception as e:
        print(f"[BŁĄD] Nie udało się utworzyć kategorii {WELCOME_CATEGORY_NAME}: {e}")
    return None


async def create_welcome_channel(guild: discord.Guild, member: discord.Member):
    """
    Tworzy prywatny kanał tekstowy dla użytkownika.
    Widziany tylko przez:
      - tego użytkownika
      - bota
      - administrację (rola ADMIN_ROLE_NAME, jeśli istnieje)
    Wszystkie takie kanały lądują w kategorii WELCOME_CATEGORY_NAME.
    """
    # jeśli kanał już istnieje, nie tworzymy drugiego
    existing = discord.utils.get(guild.text_channels, name=f"rejestracja-{member.id}")
    if existing:
        return existing

    channel_name = f"rejestracja-{member.id}"

    category = await get_or_create_welcome_category(guild)
    if category is None:
        return None

    admin_role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)

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
            read_message_history=True,
            manage_channels=True,
            manage_messages=True
        ),
    }

    # administracja ma widzieć wszystkie kanały rejestracyjne
    if admin_role:
        overwrites[admin_role] = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True
        )

    try:
        channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            reason=f"Prywatny kanał rejestracyjny dla {member}"
        )

        print(f"[INFO] Utworzono kanał {channel.name} dla {member}")
        return channel
    except discord.Forbidden:
        print("[BŁĄD] Bot nie ma uprawnień do tworzenia kanałów.")
    except Exception as e:
        print(f"[BŁĄD] Nie udało się stworzyć kanału powitalnego: {e}")
    return None


async def hide_other_channels_for_member(
    guild: discord.Guild,
    member: discord.Member,
    allowed_channel: discord.abc.GuildChannel
):
    """Ukrywa wszystkie inne kanały przed użytkownikiem, zostawiając widoczny tylko allowed_channel."""
    for channel in guild.channels:
        if channel.id == allowed_channel.id:
            continue
        try:
            await channel.set_permissions(member, view_channel=False)
        except discord.Forbidden:
            print(f"[BŁĄD] Brak uprawnień do zmiany permów na kanale {channel}")
        except Exception as e:
            print(f"[BŁĄD] Nie udało się ukryć kanału {channel} dla {member}: {e}")


async def restore_channels_for_member(guild: discord.Guild, member: discord.Member):
    """Przywraca normalny widok kanałów – usuwa indywidualne nadpisania permów dla użytkownika."""
    for channel in guild.channels:
        try:
            await channel.set_permissions(member, overwrite=None)
        except discord.Forbidden:
            print(f"[BŁĄD] Brak uprawnień do przywrócenia permów na {channel}")
        except Exception as e:
            print(f"[BŁĄD] Nie udało się przywrócić permów na {channel} dla {member}: {e}")


def is_correct_user(interaction: discord.Interaction, member: discord.Member) -> bool:
    """Sprawdza, czy klikający interakcję to ta sama osoba, dla której trwa rejestracja."""
    return interaction.user.id == member.id


def is_already_registered(member: discord.Member) -> bool:
    """
    Uznajemy, że ktoś jest 'zarejestrowany', jeśli ma
    jedną z ról wiekowych lub jedną z ról-województw.
    """
    role_names = {r.name for r in member.roles}
    if any(r in role_names for r in AGE_ROLES):
        return True
    if any(v in role_names for v in VOIVODESHIPS):
        return True
    return False


async def start_registration_for_member(member: discord.Member):
    """Wspólny flow rejestracji – używany przy wejściu i przy migracji istniejących."""
    guild = member.guild
    channel = await create_welcome_channel(guild, member)
    if not channel:
        return

    await hide_other_channels_for_member(guild, member, channel)

    await channel.send(
        f"Hej {member.mention}! 👋\n\n"
        f"Witaj na serwerze! Zanim odblokuję Ci cały serwer, odpowiedz proszę na kilka pytań.\n\n"
        f"**1/3** Jaka jest Twoja płeć?",
        view=GenderView(member)
    )


# === UI: PRZYCISKI + SELECTY ===

class GenderView(discord.ui.View):
    """Widok z przyciskami do wyboru płci."""

    def __init__(self, member: discord.Member):
        super().__init__(timeout=300)
        self.member = member

    async def handle_click(self, interaction: discord.Interaction, role_name: str):
        if not is_correct_user(interaction, self.member):
            await interaction.response.send_message(
                "To nie jest Twoja rejestracja 😉",
                ephemeral=True
            )
            return

        role = await get_or_create_role(interaction.guild, role_name)
        if role:
            await self.member.add_roles(role, reason="Płeć podana przy rejestracji")

        # Pytanie o wiek
        await interaction.response.edit_message(
            content="✅ Zapisano płeć.\n\n**2/3** Ile masz lat?",
            view=AgeView(self.member)
        )

    @discord.ui.button(label="Mężczyzna", style=discord.ButtonStyle.primary)
    async def male_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_click(interaction, "Mężczyzna")

    @discord.ui.button(label="Kobieta", style=discord.ButtonStyle.primary)
    async def female_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_click(interaction, "Kobieta")

    @discord.ui.button(label="Inna", style=discord.ButtonStyle.secondary)
    async def other_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_click(interaction, "Inna")


class AgeView(discord.ui.View):
    """Widok z przyciskami do wyboru przedziału wiekowego + blokada < 13."""

    def __init__(self, member: discord.Member):
        super().__init__(timeout=300)
        self.member = member

    async def _age_ok(self, interaction: discord.Interaction, role_name: str):
        """Obsługa poprawnego wieku (13+)."""
        if not is_correct_user(interaction, self.member):
            await interaction.response.send_message(
                "To nie jest Twoja rejestracja 😉",
                ephemeral=True
            )
            return

        role = await get_or_create_role(interaction.guild, role_name)
        if role:
            await self.member.add_roles(role, reason="Wiek podany przy rejestracji")

        # Kolejne pytanie – województwo
        await interaction.response.edit_message(
            content="✅ Zapisano wiek.\n\n**3/3** Z jakiego województwa jesteś?",
            view=VoivodeshipView(self.member)
        )

    @discord.ui.button(label="Mam mniej niż 13 lat", style=discord.ButtonStyle.danger)
    async def under_13(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Osoba ma mniej niż 13 lat – blokujemy dostęp do serwera.
        Kanały pozostają zablokowane, kanał rejestracyjny zostaje (np. dla kontaktu z adminem).
        """
        if not is_correct_user(interaction, self.member):
            await interaction.response.send_message(
                "To nie jest Twoja rejestracja 😉",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content=(
                "❌ Niestety, aby korzystać z tego serwera musisz mieć **co najmniej 13 lat**.\n\n"
                "Twoje konto nie otrzyma dostępu do pozostałych kanałów. "
                "Jeśli to pomyłka, skontaktuj się z administracją."
            ),
            view=None
        )

    @discord.ui.button(label="13-15", style=discord.ButtonStyle.success)
    async def age_13_15(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._age_ok(interaction, "13-15")

    @discord.ui.button(label="16-18", style=discord.ButtonStyle.success)
    async def age_16_18(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._age_ok(interaction, "16-18")

    @discord.ui.button(label="19-24", style=discord.ButtonStyle.primary)
    async def age_19_24(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._age_ok(interaction, "19-24")

    @discord.ui.button(label="25+", style=discord.ButtonStyle.secondary)
    async def age_25_plus(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._age_ok(interaction, "25+")


class VoivodeshipSelect(discord.ui.Select):
    """Select (lista rozwijana) z województwami."""

    def __init__(self, member: discord.Member):
        self.member = member
        options = [
            discord.SelectOption(label=name, value=name)
            for name in VOIVODESHIPS
        ]
        super().__init__(
            placeholder="Wybierz swoje województwo...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_correct_user(interaction, self.member):
            await interaction.response.send_message(
                "To nie jest Twoja rejestracja 😉",
                ephemeral=True
            )
            return

        voivodeship_name = self.values[0]
        role = await get_or_create_role(interaction.guild, voivodeship_name)
        if role:
            await self.member.add_roles(role, reason="Województwo podane przy rejestracji")

        guild = interaction.guild
        channel = interaction.channel

        # Odblokowujemy kanały (usuwamy indywidualne permisy)
        await restore_channels_for_member(guild, self.member)

        await interaction.response.edit_message(
            content=(
                f"✅ Zapisano województwo: **{voivodeship_name}**.\n\n"
                f"Twoja rejestracja została zakończona, {self.member.mention}! 🎉\n"
                f"Za chwilę ten kanał zostanie usunięty."
            ),
            view=None
        )

        # Usuwamy kanał rejestracyjny
        try:
            await channel.delete(reason=f"Zakończono rejestrację dla {self.member}")
        except discord.Forbidden:
            print("[BŁĄD] Bot nie ma uprawnień do usuwania kanału.")
        except Exception as e:
            print(f"[BŁĄD] Nie udało się usunąć kanału rejestracyjnego: {e}")


class VoivodeshipView(discord.ui.View):
    """Widok z selectem województw."""

    def __init__(self, member: discord.Member):
        super().__init__(timeout=300)
        self.add_item(VoivodeshipSelect(member))


# === NOWI UŻYTKOWNICY ===

@bot.event
async def on_member_join(member: discord.Member):
    """
    Flow dla NOWEJ osoby:
    1. Tworzymy prywatny kanał w kategorii Rejestracja
    2. Ukrywamy inne kanały
    3. Pytania 1–3
    4. Nadajemy role
    5. Odblokowujemy kanały, usuwamy kanał rejestracyjny
    """
    print(f"[INFO] Nowy użytkownik: {member} dołączył na {member.guild.name}")
    await start_registration_for_member(member)


# === START BOTA ===

if __name__ == "__main__":
    bot.run(TOKEN)
