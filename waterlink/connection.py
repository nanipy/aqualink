import websockets
import aiohttp
import ujson
import asyncio

try:
    import discord
    from discord.ext import commands
except ImportError:
    try:
        import discordjspy as discord
        from discordjspy.ext import commands
    except ImportError:
        raise ImportError("You don't have discord.py or discord.jspy installed!")

from typing import Union
from .exceptions import Disconnected


class Connection:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._loop = bot.loop
        self._sharded = isinstance(bot, commands.AutoShardedBot)
        self._shard_count = bot.shard_count if bot.shard_count is not None else 1
        self._socket = None
        self._down = {}
        self._players = {}
        bot.waterlink = self

    async def connect(self, password: str, ws_url: str, rest_url: str) -> None:
        if not hasattr(self, "session"):
            self.session = aiohttp.ClientSession(loop=self._loop)
        headers = {
            "Authorization": password,
            "Num-Shards": self._shard_count,
            "User-Id": self.bot.user.id,
        }
        self._socket = await websockets.connect(ws_url, extra_headers=headers)
        self._loop.create_task(self.event_processor())
        self._loop.create_task(self._discord_connection_state_loop())

    async def _discord_connection_state_loop(self) -> None:
        while self.connected:
            shard_guilds = {}
            for player in self._players:
                if not player.connected:
                    continue

                shard_id = player.guild.shard_id

                try:
                    shard_guilds[shard_id].append(player)
                except KeyError:
                    shard_guilds[shard_id].append(player)

            for shard, players in shard_guild_map.items():
                ws = self._get_discord_ws(shard)
                if not ws or not ws.open:
                    # the shard is down
                    self._down[shard] = True
                    continue

                if shard in self.down:
                    # the shard is online again
                    self._down.pop(shard)
                    self._loop.create_task(self._discord_reconnect_task(players))

            await asyncio.sleep(0.1)

    async def event_processor(self) -> None:
        await self.wait_until_ready()
        while self.connected:
            try:
                json = ujson.loads(await self._socket.recv())
            except websockets.ConnectionClosed:
                raise Disconnected("The lavalink server closed the connection.")

            print(json)

    async def _discord_reconnect_task(self, players) -> None:
        await asyncio.sleep(10)  # fixed wait for READY / RESUMED
        for player in players:
            await self._players[player].connect(self._players[player]._channel)
            await asyncio.sleep(1)  # 1 connection / second (gateway ratelimits = bad)

    def _get_discord_ws(
        self, shard_id
    ) -> Union[discord.gateway.DiscordWebSocket, None]:
        if self._sharded:
            return self.bot.shards[shard_id].ws
        if self.bot.shard_id is None or self.bot.shard_id == shard_id:
            # only return if the shard actually matches the current shard, useful for ignoring events not meant for us
            return self.bot.ws

    @property
    def connected(self) -> bool:
        if self._socket is None:
            return False
        else:
            return self._socket.open

    async def wait_until_ready(self) -> None:
        """Waits indefinitely until the Lavalink connection has been established."""
        while not self.connected:
            await asyncio.sleep(0.01)
