# aqualink
A better Python lavalink library made for use in discord.py rewrite or discord.jspy bots.

It has an easy to use and very fast interface that is very dynamic.

# Installation
`pip3 install aqualink`

# Basic Usage
```py
import aqualink

aqualink.Connection(bot)
await bot.aqualink.connect(password="youshallnotpass", ws_url="ws://localhost:2333", rest_url="http://localhost:2333")

# later
p = bot.aqualink.get_player(ctx.guild.id) # get the player object
await p.connect(ctx.author.voice.channel.id) # connect to the author's VC 
tracks = await p.query("ytsearch: hello Adele") # get a list of Track objects
await p.play(tracks[0]) # play the first match
await p.set_eq(aqualink.Equalizer.bassboost().ultra) # equalizer support! Ultimate bassboost preset
print(p.track.title, p.track.thumbnail) # print the currently playing track title and thumbnail
# and so on
```
