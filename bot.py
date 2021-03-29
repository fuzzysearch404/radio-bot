import discord
import asyncpg
import logging
import traceback
from logging.handlers import RotatingFileHandler
from discord.ext import commands
from discord_slash import SlashCommand

import bot_config
from cogs.utils.config import Config


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
        self.config = bot_config
        
        super().__init__(
            intents=INTENTS,
            command_prefix=commands.when_mentioned_or('radio '),
            case_insensitive=True,
            **kwargs
        )

        log = logging.getLogger("radiobot")
        log.setLevel(logging.DEBUG)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s"))
        rotating_handler = RotatingFileHandler(
                f'radiobot.log',
                encoding='utf-8',
                mode='a',
                maxBytes=25 * 1024 * 1024
        )
        rotating_handler.setFormatter(logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s"))
        log.handlers = [stream_handler, rotating_handler]
        self.log = log

        self.loop.create_task(self.connect_postgres())

        self.blacklist = Config('blacklist.json')

        self.slash = SlashCommand(
            self,
            sync_commands=True,
            sync_on_cog_reload=True,
            override_type=True
        )

        self.load_initial_cogs()

    async def connect_postgres(self):
        self.db = await asyncpg.create_pool(
            **self.config.DATABASE_CREDENTIALS, command_timeout=60.0
        )
        if self.db:
            self.log.info("Database connected successfully.")
        else:
            self.log.critical("Database not connected!")

    def load_initial_cogs(self):
        for cog in INITIAL_COGS:
            try:
                self.load_extension(cog)
                self.log.info(f"Cog \"{cog}\" loaded.")
            except Exception:
                self.log.critical(traceback.format_exc())

    async def on_ready(self):
        self.log.info(f"Woohoo, we are live!. User: {self.user}")

    async def on_message(self, message):
        if message.author.bot:
            return

        if message.author.id in self.blacklist:
            return

        try:
            await self.process_commands(message)
        except Exception:
            self.log.error(traceback.format_exc())

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.errors.CommandNotFound):
            return
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            return await ctx.send(f"\u274c Komandai trūkst obligāts arguments: `{error.param}`")
        elif isinstance(error, commands.errors.BadArgument):
            return await ctx.send("\u274c Nederīgs komandas arguments")
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if not isinstance(original, discord.HTTPException):
                self.log.critical(f'In {ctx.command.qualified_name}:')
                self.log.critical(str(original))
                self.log.critical(traceback.format_tb(original.__traceback__))
        elif isinstance(error, commands.ArgumentParsingError):
            return await ctx.send(error)
        else:
            self.log.critical(''.join(traceback.format_exception(type(error), error, error.__traceback__)))

    def on_error(self, event_method, *args, **kwargs):
        self.log.critical(traceback.format_exc())

    async def add_to_blacklist(self, object_id):
        await self.blacklist.put(object_id, True)

    async def remove_from_blacklist(self, object_id):
        try:
            await self.blacklist.remove(object_id)
        except KeyError:
            pass

    def run(self):
        super().run(self.config.BOT_AUTH_TOKEN, reconnect=True)


if __name__ == "__main__":
    bot = BotClient()
    bot.run()
