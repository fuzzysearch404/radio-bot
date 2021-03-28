import traceback
import discord
from discord.ext import commands
from cogs.utils.config import Config
from discord_slash import SlashCommand

import secrets


INTENTS = discord.Intents.none()
INTENTS.members = True
INTENTS.voice_states = True
INTENTS.guilds = True
INTENTS.guild_messages = True
INTENTS.guild_reactions = True

INITIAL_COGS = (
    'cogs.admin',
    'cogs.music',
    'cogs.status'
)


class BotClient(commands.Bot):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            intents=INTENTS,
            command_prefix=commands.when_mentioned_or('radio '),
            **kwargs
        )
        self.blacklist = Config('blacklist.json')

        self.slash = SlashCommand(
            self,
            sync_commands=True,
            sync_on_cog_reload=True,
            override_type=True
        )

        for cog in INITIAL_COGS:
            try:
                self.load_extension(cog)
                print(f"Cog \"{cog}\" loaded.")
            except Exception:
                traceback.print_exc()

    async def on_ready(self):
        print(f"Woohoo, we are live!. User: {self.user}")

    async def on_message(self, message):
        if message.author.bot:
            return

        if message.author.id in self.blacklist:
            return

        try:
            await self.process_commands(message)
        except Exception:
            traceback.print_exc()

    async def add_to_blacklist(self, object_id):
        await self.blacklist.put(object_id, True)

    async def remove_from_blacklist(self, object_id):
        try:
            await self.blacklist.remove(object_id)
        except KeyError:
            pass

    def run(self):
        super().run(secrets.BOT_AUTH_TOKEN, reconnect=True)


if __name__ == "__main__":
    bot = BotClient()
    bot.run()
