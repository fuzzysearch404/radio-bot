

async def get_fetch_member(guild, user_id):
    member = guild.get_member(user_id)
    if not member:
        member = await guild.fetch_member(user_id)

    return member

async def get_fetch_guild(bot, guild_id):
    guild = bot.get_guild(guild_id)
    if not guild:
        guild = await bot.fetch_guild(guild_id)

    return guild