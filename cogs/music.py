import re
import os
import discord
import lavalink
import asyncio
import random
import math
from discord.ext import commands
from discord.ext import tasks
from discord_slash import cog_ext
from discord_slash import SlashContext

url_rx = re.compile(r'https?://(?:www\.)?.+')

class Music(commands.Cog):
    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot
        self.bot.loop.create_task(self.attach_lavalink())
        self.radio_loop.start()
        
        if not hasattr(self, 'tracks_high'):
            self.tracks_low = []
            self.tracks_medium = []
            self.tracks_high = []

    async def attach_lavalink(self):
        await self.bot.wait_until_ready()

        if not hasattr(self.bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
            self.bot.lavalink = lavalink.Client(self.bot.user.id)
            self.bot.lavalink.add_node('127.0.0.1', 2333, 'youshallnotpass', 'eu', 'default-node')  # Host, Port, Password, Region, Name
            self.bot.add_listener(self.bot.lavalink.voice_update_handler, 'on_socket_response')

            self.bot.lavalink.add_event_hook(self.track_hook)

    async def load_jingle(self, player):
        path = random.choice(os.listdir('./jingles'))
        path = './jingles/' + str(path)

        result = await player.node.get_tracks(path)
        tracks = result['tracks']
        if tracks:
            lava_track = lavalink.models.AudioTrack(tracks[0], self.bot.user.id, recommended=True)
            player.add(requester=self.bot.user.id, track=lava_track)

    async def load_playlist(self, player, query: str, to_list: list):
        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        # Get the results for the query from Lavalink.
        results = await player.node.get_tracks(query)

        tracks = results['tracks']
        to_list.extend(tracks)

    async def load_playlist_from_file(self, player, filename: str, to_list: list):
        with open(f'./playlists/{filename}', 'r') as playl:
            for line in playl.readlines():
                await self.load_playlist(player, line.replace('\n', ''), to_list)

    async def load_all_playlists_from_files(self, player):
        await self.load_playlist_from_file(player, 'high-priority.txt', self.tracks_high)
        await self.load_playlist_from_file(player, 'medium-priority.txt', self.tracks_medium)
        await self.load_playlist_from_file(player, 'low-priority.txt', self.tracks_low)

    @tasks.loop(seconds=1)
    async def radio_loop(self):
        players = self.bot.lavalink.player_manager.find_all()
        
        for player in players:
            if not self.tracks_high:
                await self.load_all_playlists_from_files(player)
                break
            
            if player.is_connected and len(player.queue) == 0:
                if random.randint(1, 2) != 1:
                    track = random.choice(self.tracks_high)
                elif random.randint(1, 2) != 1:
                    track = random.choice(self.tracks_medium)
                else:
                    track = random.choice(self.tracks_low)
                
                # They still might be being fetched right now
                if not track:
                    continue
                
                lava_track = lavalink.models.AudioTrack(track, self.bot.user.id, recommended=True)
                player.add(requester=self.bot.user.id, track=lava_track)
                print(f"Added track to auto queue {lava_track.title}")

                jingle_counter = player.fetch(key='jingle', default=-1)
                if jingle_counter <= 0:
                    await self.load_jingle(player)
                    print("Loaded jingle to auto queue")
                    player.store(key='jingle', value=random.randint(2, 3))
                else:
                    player.store(key='jingle', value=jingle_counter-1)

            if not player.is_connected:
                print("Found that player is not connected. Trying to reconnect")
                chan_id = player.fetch(key=f'chan:{player.guild_id}', default=0)
                
                if chan_id:
                    guild = self.bot.get_guild(player.guild_id)
                    if not guild:
                        guild = await self.bot.fetch_guild(player.guild_id)
                    
                    chan = guild.get_channel(chan_id)
                    if not chan:
                        chans = await guild.fetch_channels()
                        chan = next(x for x in chans if x.id == chan_id)
                    
                    await guild.change_voice_state(channel=chan)

            if not player.is_playing and not player.paused:
                print("Found that player is not playing. Trying to restart playback")
                await player.play()

            if not player.current:
                print("Found that player has no current track. Trying to skip")
                await player.skip()

    @radio_loop.before_loop
    async def before_radio_loop(self):
        # Don't do anything before lavalink init
        await self.bot.wait_until_ready()
        while not hasattr(self.bot, 'lavalink'):
            await asyncio.sleep(0.05)
            continue

    def cog_unload(self):
        """ Cog unload handler. This removes any event hooks that were registered. """
        self.bot.lavalink._event_hooks.clear()
        self.radio_loop.stop()

    async def cog_before_invoke(self, ctx):
        """ Command before-invoke handler. """
        guild_check = ctx.guild is not None
        #  This is essentially the same as `@commands.guild_only()`
        #  except it saves us repeating ourselves (and also a few lines).

        if guild_check:
            await self.ensure_voice(ctx)
            #  Ensure that the bot and command author share a mutual voicechannel.

        return guild_check

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(error.original)

    async def ensure_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
        # Create returns a player if one exists, otherwise creates.
        # This line is important because it ensures that a player always exists for a guild.

        # Most people might consider this a waste of resources for guilds that aren't playing, but this is
        # the easiest and simplest way of ensuring players are created.

        # These are commands that require the bot to join a voicechannel (i.e. initiating playback).
        # Commands such as volume/skip etc don't require the bot to be in a voicechannel so don't need listing here.
        should_connect = ctx.command.name in ('play',)

        if not ctx.author.voice or not ctx.author.voice.channel:
            # Our cog_command_error handler catches this and sends it to the voicechannel.
            # Exceptions allow us to "short-circuit" command invocation via checks so the
            # execution state of the command goes no further.
            raise commands.CommandInvokeError('Tu neesi nevienā voice channel')

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError('Neesmu pieslēdzies.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise commands.CommandInvokeError('Man vajag `CONNECT` un `SPEAK` permissions.')

            player.store('channel', ctx.channel.id)
            await ctx.guild.change_voice_state(channel=ctx.author.voice.channel)

            player.store(key=f'chan:{ctx.guild.id}', value=ctx.author.voice.channel.id)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('Tev vajag būt manā voice channel.')

    async def ensure_slash_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        if not ctx.guild:
            await ctx.send("Komandas var izmantot tikai serverī")
            return False

        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
        should_connect = ctx.name in ('play',)

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send('Tu neesi nevienā voice channel.', hidden=True)
            return False

        if not player.is_connected:
            if not should_connect:
                await ctx.send('Neesmu pieslēdzies.', hidden=True)
                return False

            permissions = ctx.author.voice.channel.permissions_for(ctx.guild.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                await ctx.send('Man vajag `CONNECT` un `SPEAK` permissions.', hidden=True)
                return False

            player.store('channel', ctx.channel.id)
            await ctx.guild.change_voice_state(channel=ctx.author.voice.channel)

            player.store(key=f'chan:{ctx.guild.id}', value=ctx.author.voice.channel.id)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                await ctx.send('Tev vajag būt manā voice channel.', hidden=True)
                return False

        return True

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.TrackEndEvent):
            event.player.delete(key='skips')
        elif isinstance(event, lavalink.events.QueueEndEvent):
            self.radio_loop.restart()
        elif isinstance(event, lavalink.events.TrackStuckEvent):
            await event.player.skip()
        elif isinstance(event, lavalink.events.NodeDisconnectedEvent):
            print("Node got disconneceted!")

    async def do_play(self, ctx, query):
        # Get the player for this guild from cache.
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        # Remove leading and trailing <>. <> may be used to suppress embedding links in Discord.
        query = query.strip('<>')

        # Check if the user input might be a URL. If it isn't, we can Lavalink do a YouTube search for it instead.
        # SoundCloud searching is possible by prefixing "scsearch:" instead.
        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        # Get the results for the query from Lavalink.
        results = await player.node.get_tracks(query)

        # Results could be None if Lavalink returns an invalid response (non-JSON/non-200 (OK)).
        # ALternatively, resullts['tracks'] could be an empty array if the query yielded no tracks.
        if not results or not results['tracks']:
            return await ctx.send('Neko neatradu!')

        embed = discord.Embed(color=discord.Color.blurple())

        # Valid loadTypes are:
        #   TRACK_LOADED    - single video/direct URL)
        #   PLAYLIST_LOADED - direct URL to playlist)
        #   SEARCH_RESULT   - query prefixed with either ytsearch: or scsearch:.
        #   NO_MATCHES      - query yielded no results
        #   LOAD_FAILED     - most likely, the video encountered an exception during loading.
        if results['loadType'] == 'PLAYLIST_LOADED' or results['loadType'] == 'TRACK_LOADED':
            track = results['tracks'][0]
        elif results['loadType'] == 'SEARCH_RESULT':
            track = results['tracks'][0]
        else:
            return await ctx.send("Nevaru atrast neko vai arī kaut kas nokāries, bruh.")
        
        if not await self.bot.is_owner(ctx.author):
            if track['info']['length'] > 600000:
                return await ctx.send("Šī dziesma ir pārāk gara... (10mins max)")

        embed.title = 'Dziesma pievienota queue!'
        embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'

        player.add(requester=ctx.author.id, track=track)

        await ctx.send(embed=embed)

        # We don't want to call .play() if the player is playing as that will effectively skip
        # the current track.
        if not player.is_playing:
            await player.play()

        jingle_counter = player.fetch(key='jingle', default=-1)
        if jingle_counter <= 0:
            await self.load_jingle(player)
            print('Loaded jingle to queue')
            player.store(key='jingle', value=random.randint(2, 3))
        else:
            player.store(key='jingle', value=jingle_counter-1)

    @cog_ext.cog_slash(name="play", description="Pasūtīt dziesmu radio")
    async def slash_play(self, ctx: SlashContext, dziesma: str):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_play(ctx, dziesma)

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        """ Meklē dziesmu un pieliek to atskaņošanas queue. """
        await self.do_play(ctx, query)

    async def do_skip(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_connected:
            # We can't disconnect, if we're not connected.
            return await ctx.send('Neesmu pieslēdzies.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            # Abuse prevention. Users not in voice channels, or not in the same voice channel as the bot
            # may not disconnect the bot.
            return await ctx.send('Tev vajag būt manā voice channel!')

        song_name = player.current.title
        if await self.bot.is_owner(ctx.author):
            await player.skip()
        elif player.current.requester == ctx.author.id:
            await player.skip()
        else:
            channel = self.bot.get_channel(int(player.channel_id))
            required = math.ceil((len(channel.members) - 1) / 2.5)

            votes = player.fetch(key='skips', default=[])
            if ctx.author.id in votes:
                votes = len(votes)
            else:
                votes.append(ctx.author.id)
                player.store(key='skips', value=votes)
                votes = len(votes)

            if votes >= required:
                await player.skip()
            else:
                return await ctx.send(f"`{ctx.author}`grib skipot šo dziesmu. Vēl nepieciešamas **{required - votes}** balsis!")

        await ctx.send(f"Skipojam **{song_name}**!")

    @cog_ext.cog_slash(name="skip", description="Skipot patreizējo dziesmu")
    async def slash_skip(self, ctx: SlashContext):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_skip(ctx)

    @commands.command(aliases=['skipsong'])
    async def skip(self, ctx):
        """ Skipot patreizējo dziesmu. """
        await self.do_skip(ctx)

    @commands.is_owner()
    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_connected:
            # We can't disconnect, if we're not connected.
            return await ctx.send('Not connected.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            # Abuse prevention. Users not in voice channels, or not in the same voice channel as the bot
            # may not disconnect the bot.
            return await ctx.send('You\'re not in my voicechannel!')

        # Clear the queue to ensure old tracks don't start playing
        # when someone else queues something.
        player.queue.clear()
        # Stop the current track so Lavalink consumes less resources.
        await player.stop()
        # Disconnect from the voice channel.
        await ctx.guild.change_voice_state(channel=None)
        await ctx.send('*⃣ | Disconnected.')

    async def view_queue(self, ctx, page):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        queue_to_display = []
        for track in player.queue:
            if track.title != "Unknown title":
                queue_to_display.append(track)

        if not queue_to_display:
            return await ctx.send('Nākošo dziesmu queue ir tukšs.')

        items_per_page = 10
        pages = math.ceil(len(player.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue_list = ''
        for index, track in enumerate(queue_to_display[start:end], start=start):
            user = ctx.guild.get_member(track.requester)
            queue_list += f'`{index + 1}.` [**{track.title}**]({track.uri}) - {user.mention}\n'

        embed = discord.Embed(colour=discord.Color.blurple(),
                              description=f'**{len(queue_to_display)} dziesmas**\n\n{queue_list}')
        embed.set_footer(text=f'Lapa {page}/{pages}')
        await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="queue", description="Apskati pasūtītās dziesmas")
    async def slash_queue(self, ctx: SlashContext, lapa: int = 1):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.view_queue(ctx, lapa)

    @commands.command(aliases=['q'])
    async def queue(self, ctx, page: int = 1):
        """ Apskatīt nākošo dziesmu queue. """
        await self.view_queue(ctx, page)

    async def find_songs(self, ctx, query):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not query.startswith('ytsearch:') and not query.startswith('scsearch:'):
            query = 'ytsearch:' + query

        results = await player.node.get_tracks(query)

        if not results or not results['tracks']:
            return await ctx.send('Neko neatradu.')

        tracks = results['tracks'][:10]  # First 10 results

        o = ''
        for index, track in enumerate(tracks, start=1):
            track_title = track['info']['title']
            track_uri = track['info']['uri']
            o += f'`{index}.` [{track_title}]({track_uri})\n'

        embed = discord.Embed(color=discord.Color.blurple(), description=o)
        await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="find", description="Atrodi dziesmas Youtubā")
    async def slash_find(self, ctx: SlashContext, dziesmas_nosaukums: str):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.find_songs(ctx, dziesmas_nosaukums)

    @commands.command()
    async def find(self, ctx, *, query):
        """ Atrod un parāda 10 meklētās dziesmas rezultātus. """
        await self.find_songs(ctx, query)

    @commands.is_owner()
    @commands.command(aliases=['vol'])
    async def volume(self, ctx, volume):
        """ Changes the player's volume (0-1000). """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        try:
            volume = int(volume)
        except:
            volume = int(volume[:-1])

        if not volume:
            return await ctx.send(f'🔈 | {player.volume}%')

        await player.set_volume(volume)
        await ctx.send(f'🔈 | Set to {player.volume}%')

    async def view_now_playing(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.current:
            return await ctx.send('Nekas neskan, rip.')

        position = lavalink.utils.format_time(player.position)
        if player.current.stream:
            duration = '\ud83d\udd34 LIVE'
        else:
            duration = lavalink.utils.format_time(player.current.duration)
        song = f'**[{player.current.title}]({player.current.uri})**\n({position}/{duration})'

        embed = discord.Embed(color=discord.Color.blurple(),
                              title='Tagad skan', description=song)
        await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="now", description="Apskatīties kāda dziesma tagad skan")
    async def slash_now(self, ctx: SlashContext):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.view_now_playing(ctx)

    @commands.command(aliases=['np', 'n', 'playing'])
    async def now(self, ctx):
        """ Parāda tagad skanošo dziesmu. """
        await self.view_now_playing(ctx)

    @commands.is_owner()
    @commands.command()
    async def seek(self, ctx, *, seconds: int):
        """ Seeks to a given position in a track. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        track_time = player.position + (seconds * 1000)
        await player.seek(track_time)

        await ctx.send(f'Moved track to **{lavalink.utils.format_time(track_time)}**')

    @commands.is_owner()
    @commands.command()
    async def reloadplaylists(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        
        self.tracks_low = []
        self.tracks_medium = []
        self.tracks_high = []

        await self.load_all_playlists_from_files(player)

        await ctx.message.add_reaction('\u2705')

    @commands.is_owner()
    @commands.command()
    async def clear(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.queue.clear()

        await ctx.message.add_reaction('\u2705')

def setup(bot):
    bot.add_cog(Music(bot))