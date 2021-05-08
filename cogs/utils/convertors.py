from discord.errors import HTTPException
from contextlib import suppress


async def get_fetch_member(guild, user_id):
    member = guild.get_member(user_id)
    if not member:
        with suppress(HTTPException):
            member = await guild.fetch_member(user_id)

    return member


async def get_fetch_guild(bot, guild_id):
    guild = bot.get_guild(guild_id)
    if not guild:
        with suppress(HTTPException):
            guild = await bot.fetch_guild(guild_id)

    return guild
