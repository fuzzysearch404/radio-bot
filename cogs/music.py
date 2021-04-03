"""
Requires intents for members and voice states.

Jingles:
Regular jingles have to be stored in directory: ./jingles
Radio programme jingle directories under ./jingles
For example: .jingles/programme

Playlists:
Playlists have to be stored in text files under ./playlists
directory.
You can use comments in the playlist files if the line starts
with a "#" symbol.
"""
import re
import os
import discord
import lavalink
import asyncio
import random
import math
import time
import typing
from os.path import isfile
from os.path import join as path_join
from dataclasses import dataclass
from discord.ext import commands
from discord.ext import tasks
from discord_slash import cog_ext
from discord_slash import SlashContext

from .utils import convertors

URL_REGX = re.compile(r'https?://(?:www\.)?.+')

USER_QUEUE_REQUESTS_LIMIT = 6
SONG_REQUEST_MAX_LENGHT_MILIS = 600000
SONG_PLAYER_MAX_LENGHT_MILIS = 600000

RADIO_JINGLES_DIR_PATH = './jingles'
JINGLES_MIN_INTERVAL = 2
JINGLES_MAX_INTERVAL = 3

PLAYLISTS_DIR_PATH = './playlists'
# Default playlists
PLAYLIST_FILE_NAME_HIGH_PRIORITY = 'high-priority.txt'
PLAYLIST_FILE_NAME_MEDIUM_PRIORITY = 'medium-priority.txt'
PLAYLIST_FILE_NAME_LOW_PRIORITY = 'low-priority.txt'


class ProgrammePlayTime:

    __slots__ = ('start_time', 'end_time')

    def __init__(self, start_time, end_time) -> None:
        self.start_time = time.strptime(start_time, "%A %H:%M")
        self.end_time = time.strptime(end_time, "%A %H:%M")

    def convert_time(self, tm):
        # Converts this to easily comparable tuple
        return tm.tm_wday, tm.tm_min + tm.tm_hour * 60

    def is_now(self) -> bool:
        start_time = self.convert_time(self.start_time)
        end_time = self.convert_time(self.end_time)
        now = self.convert_time(time.localtime())

        if start_time < end_time:
            if start_time <= now < end_time:
                return True
        elif start_time > end_time:
            if now >= start_time or now < end_time:
                return True
        elif start_time == now == end_time:
            return True

        return False

    def occurs_next(self) -> int:
        start_time = self.convert_time(self.start_time)
        now = self.convert_time(time.localtime())

        if start_time > now:
            day_mins = (start_time[0] - now[0]) * 1440 # 1440 minutes per day
            
            return  day_mins + (start_time[1] - now[1])
        elif start_time < now:
            # Shift start day by 7 days
            day_mins = (start_time[0] + 7 - now[0]) * 1440 # 1440 minutes per day

            return  day_mins + (start_time[1] - now[1])
        else:
            return 0


@dataclass
class RadioProgramme:
    play_times: list
    title: str
    description: str
    playlists_file_name: str
    jingles_diretory: str

    def should_be_active(self) -> typing.Union[bool, ProgrammePlayTime]:
        for play_time in self.play_times:
            if play_time.is_now():
                return play_time

        return False


class Music(commands.Cog):
    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot
        # If we are currently loading some auto queue tracks
        self.loading_tracks = False
        self.bot.loop.create_task(self.attach_lavalink())
        
        self.all_programmes = (
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Monday 12:00", "Monday 14:00"),
                    ProgrammePlayTime("Tuesday 12:00", "Tuesday 14:00"),
                    ProgrammePlayTime("Wednesday 12:00", "Wednesday 14:00"),
                    ProgrammePlayTime("Thursday 12:00", "Thursday 14:00"),
                    ProgrammePlayTime("Friday 12:00", "Friday 14:00"),
                    ProgrammePlayTime("Saturday 12:00", "Saturday 14:00"),
                    ProgrammePlayTime("Sunday 12:00", "Sunday 14:00")
                ],
                title="Tikai hiti",
                description="Klausies tikai un vienīgi pašlaik vispopulārāko mūziku \ud83d\udd1d",
                playlists_file_name="hits.txt",
                jingles_diretory="hits"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Monday 23:00", "Tuesday 4:00"),
                    ProgrammePlayTime("Tuesday 23:00", "Wednesday 4:00"),
                    ProgrammePlayTime("Wednesday 23:00", "Thursday 4:00"),
                    ProgrammePlayTime("Thursday 23:00", "Friday 4:00"),
                    ProgrammePlayTime("Sunday 23:00", "Monday 4:00")
                ],
                title="Chillout bītu vakars",
                description="Atpūties. Nomierinoša mūzika tavam darba dienas vakaram \ud83d\ude34",
                playlists_file_name="chill.txt",
                jingles_diretory="chill"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Monday 9:30", "Monday 10:30"),
                    ProgrammePlayTime("Wednesday 9:30", "Wednesday 10:30"),
                    ProgrammePlayTime("Friday 9:30", "Friday 10:30"),
                    ProgrammePlayTime("Sunday 16:00", "Sunday 18:00")
                ],
                title="Throwback / Nostalģija",
                description="Mūzika, kura nekad nenovecos, nu, vismaz pagaidām nē \ud83d\udc74",
                playlists_file_name="throwback.txt",
                jingles_diretory="throwback"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Tuesday 9:30", "Tuesday 10:30"),
                    ProgrammePlayTime("Thursday 9:30", "Thursday 10:30"),
                    ProgrammePlayTime("Saturday 16:00", "Saturday 18:00")
                ],
                title="Disko mašīna",
                description="Mūzika no 70., 80., 90. gadiem - deju grīda ir tava \ud83d\udd7a",
                playlists_file_name="disco.txt",
                jingles_diretory="disco"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Monday 19:00", "Monday 20:30"),
                    ProgrammePlayTime("Thursday 19:00", "Thursday 20:30")
                ],
                title="General special: slowed+reverb",
                description="General īpašā programma: slowed+reverb edition \ud83d\udd25",
                playlists_file_name="slowed.txt",
                jingles_diretory="special"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Tuesday 19:00", "Tuesday 20:30"),
                    ProgrammePlayTime("Friday 19:00", "Friday 20:30")
                ],
                title="General special: Phonk",
                description="General īpašā programma: Phonk edition \ud83d\udd25",
                playlists_file_name="phonk.txt",
                jingles_diretory="special"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Friday 22:00", "Saturday 6:00"),
                    ProgrammePlayTime("Saturday 22:00", "Sunday 6:00")
                ],
                title="Party Mix",
                description="Tava nedēļas nogales ballīte ir šeit \ud83e\udd73",
                playlists_file_name="party.txt",
                jingles_diretory="party"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Saturday 8:00", "Saturday 10:30"),
                    ProgrammePlayTime("Sunday 8:00", "Sunday 10:30")
                ],
                title="Celies augšā!",
                description="Nav ko gulēt brīvdienās - enerģiska mūzika, lai pamostos \ud83e\udd29",
                playlists_file_name="energy.txt",
                jingles_diretory="energy"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Wednesday 19:00", "Wednesday 21:00")
                ],
                title="Latviešu mūzikas trešdienas",
                description="Klausamies vietējo mūziku \ud83c\uddf1\ud83c\uddfb",
                playlists_file_name="latvian.txt",
                jingles_diretory="latvian"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Monday 16:00", "Monday 17:00")
                ],
                title="Dienas skaņa: Indie",
                description="TIkai un vienīgi indie mūzika \ud83c\udfd5\ufe0f",
                playlists_file_name="indie.txt",
                jingles_diretory="genre"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Tuesday 16:00", "Tuesday 17:00")
                ],
                title="Dienas skaņa: Rock/Metal",
                description="TIkai un vienīgi rokmūzika/metāls \ud83c\udfb8",
                playlists_file_name="rock.txt",
                jingles_diretory="genre"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Wednesday 16:00", "Wednesday 17:00")
                ],
                title="Dienas skaņa: Hip Hop",
                description="TIkai un vienīgi hip hops/reps \ud83c\udf99\ufe0f",
                playlists_file_name="hiphop.txt",
                jingles_diretory="genre"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Thursday 16:00", "Thursday 17:00")
                ],
                title="Dienas skaņa: Jazz",
                description="TIkai un vienīgi džezs \ud83c\udfb7",
                playlists_file_name="jazz.txt",
                jingles_diretory="genre"
            ),
            RadioProgramme(
                play_times = [
                    ProgrammePlayTime("Friday 16:00", "Friday 17:00")
                ],
                title="Dienas skaņa: EDM",
                description="TIkai un vienīgi elektroniskā deju mūzika \ud83d\udc6f",
                playlists_file_name="edm.txt",
                jingles_diretory="genre"
            )
        )

        # Current programme and current playtime for programme
        self.programme, self.programme_play_time = None, None
        # Next up
        self.nearest_programme, self.nearest_play_time = None, None
        
        self.tracks_programme = []
        self.tracks_low = []
        self.tracks_medium = []
        self.tracks_high = []

        self.radio_loop.start()
        self.radio_stats_minutes_loop.start()


    def format_programme_playtime_to_string(self, play_time: ProgrammePlayTime) -> str:
        int_to_days = {
            0 : "Pirmdiena",
            1 : "Otrdiena",
            2 : "Trešdiena",
            3 : "Ceturdiena",
            4 : "Piektdiena",
            5 : "Sestdiena",
            6 : "Svētdiena"
        }

        start_time = play_time.start_time
        end_time = play_time.end_time

        start_time_str = f"{start_time.tm_hour}:{start_time.tm_min}"
        if start_time.tm_min == 0:
            start_time_str += '0'
        end_time_str = f"{end_time.tm_hour}:{end_time.tm_min}"
            
        if end_time.tm_min == 0:
            end_time_str += '0'

        start_day_name = int_to_days[start_time.tm_wday]
        if start_time.tm_wday == end_time.tm_wday:

            return f"{start_day_name} {start_time_str} - {end_time_str}\n"
        else:
            end_day_name = int_to_days[end_time.tm_wday]

            return f"{start_day_name} {start_time_str} - {end_day_name} {end_time_str}\n"

    async def attach_lavalink(self) -> None:
        await self.bot.wait_until_ready()

        if not hasattr(self.bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
            self.bot.lavalink = lavalink.Client(self.bot.user.id)
            self.bot.lavalink.add_node('127.0.0.1', 2333, 'youshallnotpass', 'eu', 'default-node')  # Host, Port, Password, Region, Name
            self.bot.add_listener(self.bot.lavalink.voice_update_handler, 'on_socket_response')

            self.bot.lavalink.add_event_hook(self.track_hook)

    async def load_jingle(self, player) -> None:
        if self.programme and self.programme.jingles_diretory:
            file_name = random.choice(os.listdir(path_join(RADIO_JINGLES_DIR_PATH, self.programme.jingles_diretory)))
            path = path_join(RADIO_JINGLES_DIR_PATH, self.programme.jingles_diretory, str(file_name))
        else:
            # The jingle folder has subdirectories for programme jingles
            only_files = [f for f in os.listdir(RADIO_JINGLES_DIR_PATH) if isfile(path_join(RADIO_JINGLES_DIR_PATH, f))]
            file_name = random.choice(only_files)
            path = path_join(RADIO_JINGLES_DIR_PATH, str(file_name))

        result = await player.node.get_tracks(path)
        tracks = result['tracks']
        if tracks:
            player.add(requester=self.bot.user.id, track=tracks[0], index=0)

    async def load_playlist(self, player, query: str, to_list: list) -> None:
        query = query.strip('<>')

        if not URL_REGX.match(query):
            query = f'ytsearch:{query}'

        # Get the results for the query from Lavalink.
        results = await player.node.get_tracks(query)

        tracks = results['tracks']
        to_list.extend(tracks)

    async def load_playlist_from_file(self, player, filename: str, to_list: list) -> None:
        self.loading_tracks = True
        
        with open(PLAYLISTS_DIR_PATH + '/' + filename, 'r') as playl:
            for line in playl.readlines():
                if not line.startswith('#') and line != '\n':
                    await self.load_playlist(player, line.replace('\n', ''), to_list)

                    # Slow load - to lower the chance to get rate limited?
                    await asyncio.sleep(random.randint(2, 4))

        self.loading_tracks = False

    async def load_programme_playlist_from_file(self, player) -> None:
        if not self.programme:
            return

        await self.load_playlist_from_file(player, self.programme.playlists_file_name, self.tracks_programme)

    async def load_all_playlists_from_files(self, player) -> None:
        await self.load_playlist_from_file(player, PLAYLIST_FILE_NAME_HIGH_PRIORITY, self.tracks_high)
        await self.load_playlist_from_file(player, PLAYLIST_FILE_NAME_MEDIUM_PRIORITY, self.tracks_medium)
        await self.load_playlist_from_file(player, PLAYLIST_FILE_NAME_LOW_PRIORITY, self.tracks_low)

    def find_next_programme_and_play_time(self) -> tuple:
        nearest_prog, nearest_play_time = None, None
        for prog in self.all_programmes:
            for play_time in prog.play_times:
                occurs_next = play_time.occurs_next()
                if occurs_next == 0:
                    # Not really next, it is current by now
                    continue

                if not nearest_prog:
                    nearest_prog, nearest_play_time = prog, play_time
                    continue

                if occurs_next < nearest_play_time.occurs_next():
                    nearest_prog, nearest_play_time = prog, play_time

        return nearest_prog, nearest_play_time

    def check_current_programme(self) -> None:
        self.nearest_programme, self.nearest_play_time = self.find_next_programme_and_play_time()

        if self.programme:
            if self.programme.should_be_active():
                return
            else:
                self.bot.log.info(f"Programme {self.programme.title} has ended")
                self.programme, self.programme_play_time = None, None
                self.tracks_programme = []

        for prog in self.all_programmes:
            play_time = prog.should_be_active()
            if play_time:
                self.programme, self.programme_play_time = prog, play_time
                self.bot.log.info(f"Programme {self.programme.title} has started")

    async def stats_give_users_listen_minutes(self, user_ids_minutes: list) -> None:
        query = """
                INSERT INTO radio_stats(userid, listening_minutes)
                VALUES ($1, $2) ON CONFLICT (userid)
                DO UPDATE
                SET listening_minutes = radio_stats.listening_minutes + $2;
                """

        async with self.bot.db.acquire() as connection:
            async with connection.transaction():
                # List of tuples with user ids and minutes
                await self.bot.db.executemany(query, user_ids_minutes)


    async def stats_give_user_song_request(self, user_id: int, requests: int) -> None:
        query = """
                INSERT INTO radio_stats(userid, song_requests)
                VALUES ($1, $2) ON CONFLICT (userid)
                DO UPDATE
                SET song_requests = radio_stats.song_requests + $2;
                """

        async with self.bot.db.acquire() as connection:
            async with connection.transaction():
                await self.bot.db.execute(query, user_id, requests)

    @tasks.loop(minutes=1)
    async def radio_stats_minutes_loop(self) -> None:
        players = self.bot.lavalink.player_manager.find_all()

        db_data_rows = []

        for player in players:
            # Lavalink.py stupidly stores guild_id as a string
            guild = await convertors.get_fetch_guild(self.bot, int(player.guild_id))
            if not guild:
                continue # RIP?

            bot_member = guild.me
            if not bot_member:
                bot_member = await convertors.get_fetch_member(self.bot, guild, self.bot.user.id)
                if not bot_member:
                    continue # RIP?

            bot_voice_state = bot_member.voice
            if not bot_voice_state:
                self.bot.log.error(f"Can't get my voice state for guild {player.guild_id}")
                continue
            
            for member in bot_voice_state.channel.members:
                if member.id in self.bot.blacklist:
                    continue

                if not member.bot:
                    voice_state = member.voice
                    if not voice_state:
                        self.bot.log.error(f"Can't get voice state for member {member.id}")
                        continue
                    
                    if not voice_state.self_deaf and not voice_state.deaf:
                        db_data_rows.append((member.id, 1))

        if db_data_rows:
            await self.stats_give_users_listen_minutes(db_data_rows)

    @tasks.loop(seconds=1)
    async def radio_loop(self) -> None:
        players = self.bot.lavalink.player_manager.find_all()

        self.check_current_programme()

        for player in players:
            if not self.loading_tracks:
                if self.programme:
                    if not self.tracks_programme:
                        await self.load_programme_playlist_from_file(player)
                        break
                else:
                    if not self.tracks_high:
                        await self.load_all_playlists_from_files(player)
                        break
            
            if player.is_connected and len(player.queue) == 0:
                try:
                    if self.programme:
                        track = random.choice(self.tracks_programme)
                    else:
                        if random.randint(1, 10) > 4: # 60% chance to stay
                            track = random.choice(self.tracks_high)
                        elif random.randint(1, 10) > 3: # 70% chance to stay
                            track = random.choice(self.tracks_medium)
                        else:
                            track = random.choice(self.tracks_low)
                except IndexError:
                    # Happens when something is still loading
                    continue

                if track['info']['isStream'] or track['info']['length'] > SONG_PLAYER_MAX_LENGHT_MILIS:
                    # Track too long, redraw another.
                    continue
                
                player.add(requester=self.bot.user.id, track=track)
                self.bot.log.info(f"Added track to auto queue {track['info']['title']}")

            if not player.is_connected:
                self.bot.log.error("Found that player is not connected. Trying to reconnect")
                chan_id = player.fetch(key=f'chan:{player.guild_id}', default=0)
                
                if chan_id:
                    guild = await convertors.get_fetch_guild(self.bot, int(player.guild_id))
                    if not guild:
                        continue
                    
                    chan = guild.get_channel(chan_id)
                    if not chan:
                        chans = await guild.fetch_channels()
                        chan = next(x for x in chans if x.id == chan_id)
                    
                    await guild.change_voice_state(channel=chan)

            if player.is_connected and not player.is_playing and not player.paused:
                self.bot.log.error("Found that player is not playing. Trying to restart playback")
                await player.play()

            if player.is_connected and not player.current:
                self.bot.log.error("Found that player has no current track. Trying to skip")
                await player.skip()

    async def await_lavalink_attached(self) -> None:
        # Don't do anything before lavalink init
        await self.bot.wait_until_ready()
        while not hasattr(self.bot, 'lavalink'):
            await asyncio.sleep(0.1)
            continue

    @radio_loop.before_loop
    async def before_radio_loop(self):
        await self.await_lavalink_attached()

    @radio_stats_minutes_loop.before_loop
    async def before_radio_loop(self):
         await self.await_lavalink_attached()

    def cog_unload(self):
        """ Cog unload handler. This removes any event hooks that were registered. """
        self.bot.lavalink._event_hooks.clear()
        self.radio_loop.stop()
        self.radio_stats_minutes_loop.cancel()

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

        should_connect = ctx.command.name in ('play',)

        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandInvokeError('\u274c Tu neesi nevienā voice channel')

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError('\u274c Neesmu pieslēdzies.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise commands.CommandInvokeError('\u274c Man vajag `CONNECT` un `SPEAK` permissions.')

            player.store('channel', ctx.channel.id)
            await ctx.guild.change_voice_state(channel=ctx.author.voice.channel)

            player.store(key=f'chan:{ctx.guild.id}', value=ctx.author.voice.channel.id)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('\ud83e\udd21 Tev vajag būt manā voice channel.')

    async def ensure_slash_voice(self, ctx) -> bool:
        """ This check ensures that the bot and command author are in the same voicechannel. """
        if not ctx.guild:
            await ctx.send("\u274c Komandas var izmantot tikai serverī")
            return False

        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
        should_connect = ctx.name in ('play',)

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send('\u274c Tu neesi nevienā voice channel.', hidden=True)
            return False

        if not player.is_connected:
            if not should_connect:
                await ctx.send('\u274c Neesmu pieslēdzies.', hidden=True)
                return False

            permissions = ctx.author.voice.channel.permissions_for(ctx.guild.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                await ctx.send('\u274c Man vajag `CONNECT` un `SPEAK` permissions.', hidden=True)
                return False

            player.store('channel', ctx.channel.id)
            await ctx.guild.change_voice_state(channel=ctx.author.voice.channel)

            player.store(key=f'chan:{ctx.guild.id}', value=ctx.author.voice.channel.id)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                await ctx.send('\ud83e\udd21 Tev vajag būt manā voice channel.', hidden=True)
                return False

        return True

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.TrackEndEvent):
            # Remove skip votes
            event.player.delete(key='skips')
            # Handle jingles
            jingle_counter = event.player.fetch(key='jingle', default=-1)
            if jingle_counter <= 1:
                await self.load_jingle(event.player)
                self.bot.log.info("Loaded jingle to queue")
                event.player.store(key='jingle', value=random.randint(JINGLES_MIN_INTERVAL, JINGLES_MAX_INTERVAL))
            else:
                event.player.store(key='jingle', value=jingle_counter - 1)
        elif isinstance(event, lavalink.events.QueueEndEvent):
            self.radio_loop.restart()
        elif isinstance(event, lavalink.events.TrackStuckEvent):
            await event.player.skip()
        elif isinstance(event, lavalink.events.TrackExceptionEvent):
            self.bot.log.error(f"Exception occured for track: {event.track.title}")
            self.bot.log.error(event.exception)
        elif isinstance(event, lavalink.events.NodeDisconnectedEvent):
            self.bot.log.critical("Node got disconneceted!")

    async def do_play(self, ctx, query):
        # Get the player for this guild from cache.
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        is_owner = await self.bot.is_owner(ctx.author)

        user_song_count_in_queue = sum(1 for x in player.queue if x.requester == ctx.author.id)
        if not is_owner:
            if user_song_count_in_queue >= USER_QUEUE_REQUESTS_LIMIT:
                return await ctx.send(
                    "\u231b Tu esi sasniedzis maksimālo pasūtīto dziesmu "
                    f"limitu queue (**{USER_QUEUE_REQUESTS_LIMIT}** dziesmas). "
                    "Pagaidi, līdz izskan kāda no tavām dziesmām, lai arī citi "
                    "var pasūtīt savas dziesmas.")

        # Remove leading and trailing <>. <> may be used to suppress embedding links in Discord.
        query = query.strip('<>')

        # Check if the user input might be a URL. If it isn't, we can Lavalink do a YouTube search for it instead.
        # SoundCloud searching is possible by prefixing "scsearch:" instead.
        if not URL_REGX.match(query):
            query = f'ytsearch:{query}'

        results = await player.node.get_tracks(query)

        # Results could be None if Lavalink returns an invalid response (non-JSON/non-200 (OK)).
        # ALternatively, resullts['tracks'] could be an empty array if the query yielded no tracks.
        if not results or not results['tracks']:
            return await ctx.send('\u274c Neko neatradu!')

        embed = discord.Embed(color=1558583)

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
            return await ctx.send("\u274c Nevaru atrast neko vai arī kaut kas nokāries, bruh.")
        
        if not is_owner:
            if track['info']['isStream'] or track['info']['length'] > SONG_REQUEST_MAX_LENGHT_MILIS:
                return await ctx.send("\u23f0 Šī dziesma ir pārāk gara... (10mins max)")

        embed.title = '\u2705 Dziesma pievienota queue!'
        embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'

        player.add(requester=ctx.author.id, track=track)

        await ctx.send(embed=embed)

        # We don't want to call .play() if the player is playing as that will effectively skip
        # the current track.
        if not player.is_playing:
            await player.play()

        await self.stats_give_user_song_request(ctx.author.id, 1)

    @cog_ext.cog_slash(name="play", description="\u25b6\ufe0f Pasūtīt dziesmu radio")
    async def slash_play(self, ctx: SlashContext, dziesma: str):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_play(ctx, dziesma)

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        """ \u25b6\ufe0f Pasūtīt dziesmu radio """
        await self.do_play(ctx, query)

    async def do_skip(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        skip_track = player.current
        if not skip_track:
            await player.skip()
            return await ctx.send('\u23e9')

        if await self.bot.is_owner(ctx.author):
            await player.skip()
        elif player.current.requester == ctx.author.id:
            await player.skip()
        else:
            channel = self.bot.get_channel(int(player.channel_id))
            # The amount of people (not bots) that are actually listening right now
            real_listners = [x for x in channel.members if not x.bot and not x.voice.self_deaf and not x.voice.deaf]
            required_votes = math.ceil(len(real_listners) / 2.5)

            votes = player.fetch(key='skips', default=[])
            if ctx.author.id in votes:
                votes = len(votes)
            else:
                votes.append(ctx.author.id)
                player.store(key='skips', value=votes)
                votes = len(votes)

            if votes >= required_votes:
                await player.skip()
            else:
                return await ctx.send(
                    f"\u23e9\u2753 `{ctx.author}`grib skipot šo dziesmu. "
                    f"Vēl nepieciešamas **{required_votes - votes}** balsis!"
                )

        requester = await convertors.get_fetch_member(self.bot, ctx.guild, skip_track.requester)
        
        await ctx.send(f"\u23e9 Skipojam `{requester}` pasūtīto dziesmu: **{skip_track.title}**!")

    @cog_ext.cog_slash(name="skip", description="\u23e9 Skipot patreizējo dziesmu")
    async def slash_skip(self, ctx: SlashContext):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_skip(ctx)

    @commands.command(aliases=['skipsong'])
    async def skip(self, ctx):
        """ \u23e9 Skipot patreizējo dziesmu """
        await self.do_skip(ctx)

    @commands.is_owner()
    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_connected:
            # We can't disconnect, if we're not connected.
            return await ctx.send('\u274c Not connected.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            # Abuse prevention. Users not in voice channels, or not in the same voice channel as the bot
            # may not disconnect the bot.
            return await ctx.send('\u274c You\'re not in my voicechannel!')

        # Clear the queue to ensure old tracks don't start playing
        # when someone else queues something.
        player.queue.clear()
        # Stop the current track so Lavalink consumes less resources.
        await player.stop()
        # Disconnect from the voice channel.
        await ctx.guild.change_voice_state(channel=None)
        await ctx.send('\u274c | Disconnected.')

    async def do_view_queue(self, ctx, page):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        queue_to_display = []
        for track in player.queue:
            # Don't add local files
            if URL_REGX.match(track.uri):
                queue_to_display.append(track)

        if not queue_to_display:
            return await ctx.send('\ud83d\udcc3 Nākošo dziesmu queue ir tukšs.')

        items_per_page = 10
        pages = math.ceil(len(player.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue_list = ''
        for index, track in enumerate(queue_to_display[start:end], start=start):
            user = ctx.guild.get_member(track.requester)
            queue_list += f'`{index + 1}.` [**{track.title}**]({track.uri}) - {user.mention}\n'

        embed = discord.Embed(colour=789734,
                              description=f'**\ud83d\uddc3\ufe0f {len(queue_to_display)} dziesmas**\n\n{queue_list}')
        embed.set_footer(text=f'Lapa {page}/{pages}')
        await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="queue", description="\ud83d\uddc2\ufe0f Apskati pasūtītās dziesmas")
    async def slash_queue(self, ctx: SlashContext, lapa: int = 1):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_view_queue(ctx, lapa)

    @commands.command(aliases=['q'])
    async def queue(self, ctx, page: int = 1):
        """ \ud83d\uddc2\ufe0f Apskati pasūtītās dziesmas """
        await self.do_view_queue(ctx, page)

    async def do_find_songs(self, ctx, query):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not query.startswith('ytsearch:') and not query.startswith('scsearch:'):
            query = 'ytsearch:' + query

        results = await player.node.get_tracks(query)

        if not results or not results['tracks']:
            return await ctx.send('\u274c Neko neatradu.')

        tracks = results['tracks'][:10]  # First 10 results

        o = ''
        for index, track in enumerate(tracks, start=1):
            track_title = track['info']['title']
            track_uri = track['info']['uri']
            o += f'`{index}.` [{track_title}]({track_uri})\n'

        embed = discord.Embed(color=discord.Color.blurple(), description=o)
        await ctx.send(embed=embed)

    @cog_ext.cog_slash(
        name="find",
        description="\ud83d\udd0d Atrod un parāda 10 meklētās dziesmas rezultātus no Youtube"
    )
    async def slash_find(self, ctx: SlashContext, dziesmas_nosaukums: str):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_find_songs(ctx, dziesmas_nosaukums)

    @commands.command()
    async def find(self, ctx, *, query):
        """ \ud83d\udd0d Atrod un parāda 10 meklētās dziesmas rezultātus no Youtube """
        await self.do_find_songs(ctx, query)

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

    async def do_view_now_playing(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.current:
            return await ctx.send('\u274c Nekas neskan, rip.')

        position = lavalink.utils.format_time(player.position)
        if player.current.stream:
            duration = '\ud83d\udd34 LIVE'
        else:
            duration = lavalink.utils.format_time(player.current.duration)
        
        now_playing_info = (
            f'\ud83c\udfb5 **[{player.current.title}]({player.current.uri})**'
            f'\n\ud83d\udc64 <@{player.current.requester}>'
            f'\n\u23f0 {position}/{duration}'
            '\n\n\ud83d\udd34 Pašlaik radio ēterā: '
        )

        if not self.programme:
            now_playing_info += "**Parastā dziesmu rotācija**\nGalvenais radio playlist. \ud83d\udd04"
        else:
            programme = self.programme
            current_play_time_str = self.format_programme_playtime_to_string(self.programme_play_time)
            now_playing_info += f"**{programme.title}**\n{current_play_time_str}{programme.description}"

        nearest = self.nearest_programme
        if nearest:
            next_play_time_str = self.format_programme_playtime_to_string(self.nearest_play_time)
            now_playing_info += (
                f"\n\n\u23ed\ufe0f Turpinājumā: **{nearest.title}**"
                f"\n{next_play_time_str}{nearest.description}"
            )

        embed = discord.Embed(color=16717068,
                              title='\u25b6\ufe0f Tagad skan', description=now_playing_info)
        embed.set_footer(text="Radio programma: Apskati ar komandu /programma")
        
        await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="now", description="\ud83c\udfb5 Parāda dziesmu, kas pašlaik tiek atskaņota")
    async def slash_now(self, ctx: SlashContext):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_view_now_playing(ctx)

    @commands.command(aliases=['np', 'n', 'playing'])
    async def now(self, ctx):
        """ \ud83c\udfb5 Parāda dziesmu, kas pašlaik tiek atskaņota """
        await self.do_view_now_playing(ctx)

    async def do_delete_last_request(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send("\u274c Queue ir jau pavisam tukšs")

        try:
            to_remove = next(x for x in reversed(player.queue) if x.requester == ctx.author.id)
        except StopIteration:
            return await ctx.send("\u274c Tu nemaz neesi pasūtījis nevienu dziesmu.")
        
        player.queue.remove(to_remove)

        await ctx.send(f"\ud83e\uddf9 Ok, izņēmu tavu pēdējo pasūtīto dziesmu **{to_remove.title}** no queue.")
        
        await self.stats_give_user_song_request(ctx.author.id, -1)

    @cog_ext.cog_slash(
        name="remove",
        description="\u274c Nepareizā dziesma? Šī komanda noņem tavu pēdējo pasūtīto dziesmu no queue"
    )
    async def slash_remove(self, ctx: SlashContext):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_delete_last_request(ctx)
    
    @commands.command()
    async def remove(self, ctx):
        """ \u274c Nepareizā dziesma? Šī komanda noņem tavu pēdējo pasūtīto dziesmu no queue """
        await self.do_delete_last_request(ctx)

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
        """ Reloads all auto queue playlists """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        
        self.tracks_low = []
        self.tracks_medium = []
        self.tracks_high = []
        self.tracks_programme = []
        
        if self.programme:
            await self.load_programme_playlist_from_file(player)
        else:
            await self.load_all_playlists_from_files(player)

        await ctx.message.add_reaction('\u2705')

    @commands.is_owner()
    @commands.command()
    async def clear(self, ctx, index: int = 0):
        """ Clears the whole queue or remove any specific track """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not index:
            player.queue.clear()
        else:
            try:
                del player.queue[index - 1]
            except IndexError:
                pass

        await ctx.message.add_reaction('\u2705')

    def minutes_to_days(self, minutes: int) -> tuple:
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        return days, hours, minutes

    async def do_view_user_stats(self, ctx, user):
        target_member = user or ctx.author

        query = """
                SELECT * FROM radio_stats
                WHERE userid = $1;
                """
        
        user_data = await self.bot.db.fetchrow(query, target_member.id)
        if not user_data:
            return await ctx.send(f"\u274c **{target_member}** nav klausījies/-usies radio. :(")

        embed = discord.Embed(
            color=16137269,
            title=f"\ud83d\udcca {target_member} radio statistika"
        )
        days, hours, minutes = self.minutes_to_days(user_data["listening_minutes"])
        embed.add_field(
            name="\ud83d\udd50 Klausīšanās ilgums",
            value=f"{days} dienas {hours} stundas {minutes} minūtes"
        )
        embed.add_field(name="\ud83c\udfb6 Pasūtītās dziesmas", value=f"{user_data['song_requests']}")

        await ctx.send(embed=embed)

    @cog_ext.cog_slash(
        name="stats",
        description="\ud83d\udcca Apskati savu vai kāda cita radio klausīšanās statistiku"
    )
    async def slash_stats(self, ctx: SlashContext, cits_lietotajs: discord.Member=None):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_view_user_stats(ctx, cits_lietotajs)
    
    @commands.command()
    async def stats(self, ctx, cits_lietotajs: discord.Member=None):
        """ \ud83d\udcca Apskati savu vai kāda cita radio klausīšanās statistiku """
        await self.do_view_user_stats(ctx, cits_lietotajs)

    async def do_view_top_users(self, ctx):
        query_minutes = """
                SELECT * FROM radio_stats
                ORDER BY listening_minutes DESC
                LIMIT 8;
                """

        query_requests = """
                SELECT * FROM radio_stats
                ORDER BY song_requests DESC
                LIMIT 8;
                """

        top_minutes = await self.bot.db.fetch(query_minutes)
        top_requests = await self.bot.db.fetch(query_requests)

        embed = discord.Embed(
            color=16173112,
            title=f"\ud83c\udfc6 Lojālākie radio klausītāji"
        )

        embed.description = "\ud83d\udd50 **Klausīšanās ilgums:**"
        if top_minutes:
            for top_data in top_minutes:
                user = await convertors.get_fetch_member(self.bot, ctx.guild, top_data['userid'])
                if user:
                    username = user.name + '#' + user.discriminator
                else:
                    username = 'Nezināms klausītājs'
                embed.description += f"\n`{username}` - {top_data['listening_minutes']} minūtes"
        else:
            embed.description += "\nNav datu :\\"
        
        embed.description += "\n\n\ud83c\udfb6 **Pasūtītās dziesmas:**"
        if top_requests:
            for top_data in top_requests:
                user = await convertors.get_fetch_member(self.bot, ctx.guild, top_data['userid'])
                if user:
                    username = user.name + '#' + user.discriminator
                else:
                    username = 'Nezināms klausītājs'
                embed.description += f"\n`{username}` - {top_data['song_requests']} dziesmas"
        else:
            embed.description += "\nNav datu :\\"

        await ctx.send(embed=embed)
    
    @cog_ext.cog_slash(
        name="top",
        description="\ud83c\udfc6 Apskati lojālākos radio klausītājus"
    )
    async def slash_top(self, ctx: SlashContext):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_view_top_users(ctx)
    
    @commands.command()
    async def top(self, ctx):
        """ \ud83c\udfc6 Apskati lojālākos radio klausītājus """
        await self.do_view_top_users(ctx)

    async def do_view_radio_programmes(self, ctx, page):
        if not self.all_programmes:
            return await ctx.send("\u274c Nav radio programmu")

        embed = discord.Embed(
            title="\ud83d\udcf0 Radio programma",
            color=16777200
        )

        programmes_to_display = []
        embed.description = ''

        for prog in self.all_programmes:
            programme_str = f"**{prog.title}** - {prog.description}\n"
            for play_time in prog.play_times:
                programme_str += self.format_programme_playtime_to_string(play_time)
            
            programmes_to_display.append(programme_str)

        items_per_page = 4
        pages = math.ceil(len(programmes_to_display) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        for index, prog in enumerate(programmes_to_display[start:end], start=start):
            embed.description += prog

        embed.set_footer(text=f"Lapa {page}/{pages}")
        await ctx.send(embed=embed)

    @cog_ext.cog_slash(
        name="programma",
        description="\ud83d\udcf0 Apskati radio programmu"
    )
    async def slash_programme(self, ctx: SlashContext, lapa: int = 1):
        if not await self.ensure_slash_voice(ctx):
            return
        
        await self.do_view_radio_programmes(ctx, lapa)
    
    @commands.command()
    async def programma(self, ctx, lapa: int = 1):
        """ \ud83d\udcf0 Apskati radio programmu """
        await self.do_view_radio_programmes(ctx, lapa)


def setup(bot):
    bot.add_cog(Music(bot))