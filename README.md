# Discord Radio Bot
This is a proof of concept bot for **simulating** a real world radio station, in Discord voice channels. 📻  
Built with [discord.py](https://github.com/Rapptz/discord.py) and [Lavalink](https://github.com/Frederikam/Lavalink). 🔥

## Features:  
* Quite dynamic, easily customazible  
* Scheduled radio programmes in different week days/hours  
* Regular auto queue when no radio programmes are playing  
* Jingles for auto queue and personalizable per radio programme  
* Default queue with 3 priority type playlist lists  
* User song requests  
* Auto reconnect/fix handling, when possible and detected  
* Admin controls for managing the radio  
* Supports Stage channels  
* User participation activity stats  
* Slash commands
## Requires:  
* Intents for guilds, members and voice states.  
* Lavalink set up and running  
* Lavalink.py (https://github.com/Devoxin/Lavalink.py/)  
* PostgreSQL database running with `schema.sql` set up for stats  
* asyncpg (`pip install -U asyncpg`)  
* discord_slash (temp., while discord.py does not support them) `(pip install -U discord-py-slash-command) ` 
* `./jingles` directory with jingle sound files  
* `./jingles/` subdirectories for jingles per programmes  
* `./playlists` directory with playlist lists text files  
* Configuration in `Music` cog  

### Extra notes:
1) This bot is **NOT** recommended and **NOT** optimized for large, public hosting.  
2) The bot is not in English language, because I use it in production for my own usage.  
3) The setup/implementation would differ in your use case. (I also excluded some stuff from the repo)  
4) This is **NOT** an actual radio station, but just a regular music bot for Discord.  
