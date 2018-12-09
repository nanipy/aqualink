import websockets
import aiohttp
import ujson
import asyncio
import time

try:
    import discord
    from discord.ext import commands
except ImportError:
    try:
        import discordjspy as discord
        from discordjspy.ext import commands
    except ImportError:
        raise ImportError("You don't have discord.py or discord.jspy installed!")

from typing import Union, Optional, List
from .exceptions import Disconnected
from .player import Player
from .track import Track


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

    async def _handler(self, data):
        if not self.connected:
            return

        if not data:
            return
        if data["op"] != 0:
            return

        if data["t"] == "VOICE_SERVER_UPDATE":
            player = self.get_player(int(data["d"]["guild_id"]))
            if not player._connecting:
                return
            else:
                player._connecting = False

            payload = {
                "op": "voiceUpdate",
                "guildId": data["d"]["guild_id"],
                "sessionId": self.bot.get_guild(
                    int(data["d"]["guild_id"])
                ).me.voice.session_id,
                "event": data["d"],
            }
            await self._send(**payload)

    async def connect(self, password: str, ws_url: str, rest_url: str) -> None:
        await self.bot.wait_until_ready()
        if not hasattr(self, "session"):
            self.session = aiohttp.ClientSession(loop=self._loop)
        headers = {
            "Authorization": password,
            "Num-Shards": self._shard_count,
            "User-Id": self.bot.user.id,
        }
        self._password = password
        self._rest_url = rest_url
        self._ws_url = ws_url
        self._socket = await websockets.connect(ws_url, extra_headers=headers)
        self._loop.create_task(self.event_processor())
        self._loop.create_task(self._discord_connection_state_loop())

    async def _discord_connection_state_loop(self) -> None:
        while self.connected:
            shard_guilds = {}
            for guild, player in self._players.items():
                if not player.connected:
                    continue

                shard_id = (guild >> 22) % self._shard_count

                try:
                    shard_guilds[shard_id].append(player)
                except KeyError:
                    shard_guilds[shard_id] = [player]

            for shard, players in shard_guilds.items():
                ws = self._get_discord_ws(shard)
                if not ws or not ws.open:
                    # the shard is down
                    self._down[shard] = True
                    continue

                if shard in self._down:
                    # the shard is online again
                    self._down.pop(shard)
                    self._loop.create_task(self._discord_reconnect_task(players))

            await asyncio.sleep(0.1)

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

    async def event_processor(self) -> None:
        await self.wait_until_ready()
        while self.connected:
            try:
                json = ujson.loads(await self._socket.recv())
            except websockets.ConnectionClosed:
                raise Disconnected("The lavalink server closed the connection.")

            op = json.get("op")

            if op == "stats":
                json.pop("op")
                self.stats = json
            elif op == "playerUpdate" and "position" in json["state"]:
                player = self.get_player(int(json["guildId"]))

                lag = time.time() - json["state"]["time"] / 1000
                player._position = json["state"]["position"] / 1000 + lag
            elif op == "event":
                player = self.get_player(int(json["guildId"]))
                self._loop.create_task(player._process_event(json))

    async def _send(self, **data) -> None:
        if not self.connected:
            raise Disconnected()

        try:
            data["guildId"] = str(data["guildId"])
            data["channelId"] = str(data["channelId"])
        except KeyError:
            pass
        await self._socket.send(ujson.dumps(data))

    async def _discord_disconnect(self, guild_id: int) -> None:
        shard_id = (guild_id >> 22) % self._shard_count
        await self._get_discord_ws(shard_id).send(
            ujson.dumps(
                {
                    "op": 4,
                    "d": {
                        "self_deaf": False,
                        "guild_id": str(guild_id),
                        "channel_id": None,
                        "self_mute": False,
                    },
                }
            )
        )

    async def _discord_connect(self, guild_id: int, channel_id: int) -> None:
        shard_id = (guild_id >> 22) % self._shard_count
        await self._get_discord_ws(shard_id).send(
            ujson.dumps(
                {
                    "op": 4,
                    "d": {
                        "self_deaf": False,
                        "guild_id": str(guild_id),
                        "channel_id": str(channel_id),
                        "self_mute": False,
                    },
                }
            )
        )

    async def _play(
        self,
        guild_id: int,
        track: str,
        end_time: Optional[float],
        start_time: float = 0.0,
    ) -> None:
        if end_time is not None:
            await self._send(
                op="play",
                guildId=guild_id,
                track=track,
                startTime=int(start_time * 1000),
                endTime=int(end_time * 1000),
            )
        else:
            await self._send(
                op="play",
                guildId=guild_id,
                track=track,
                startTime=int(start_time * 1000),
            )

    async def _pause_resume(self, guild_id: int, paused: bool) -> None:
        await self._send(op="pause", guildId=guild_id, pause=paused)

    async def _stop(self, guild_id: int) -> None:
        await self._send(op="stop", guildId=guild_id)

    async def _volume(self, guild_id: int, level: int) -> int:
        level = max(min(level, 150), 0)  # no earrapes
        await self._send(op="volume", guildId=guild_id, volume=level)
        return level

    async def _seek(self, guild_id: int, position: float) -> None:
        position = int(position * 1000)
        await self._send(op="seek", guildId=guild_id, position=position)

    def get_player(self, guild_id: int) -> Player:
        """
        Gets a Player class that abstracts away connection handling, among other things.
        You shouldn't be holding onto these for too long, rather you should be requesting them as necessary using this
        method.
        :param guild_id: The guild ID to get the player for.
        :return: A Player instance for that guild.
        """
        if not isinstance(guild_id, int):
            raise TypeError(f"Expected guild ID integer, got {type(guild_id).__name__}")
        try:
            player = self._players[guild_id]
        except KeyError:
            player = Player(self, guild_id)
            self._players[guild_id] = player
        return player

    async def query(self, query: str, *, retry_count=0, retry_delay=0) -> List[Track]:
        """
        Queries Lavalink. Returns a list of Track objects (dictionaries).
        :param query: The search query to make.
        :param retry_count: How often to retry the query should it fail. 0 disables, -1 will try forever (dangerous).
        :param retry_delay: How long to sleep for between retries.
        """
        headers = {"Authorization": self._password, "Accept": "application/json"}
        params = {"identifier": query}
        while True:
            async with self.session.get(
                f"{self._rest_url}/loadtracks", params=params, headers=headers
            ) as resp:
                out = await resp.json()

            # -1 is not recommended unless you run it as a task which you cancel after a specific time, but
            # you do you devs
            if not out and (
                retry_count > 0 or retry_count < 0
            ):  # edge case where lavalink just returns nothing
                retry_count -= 1
                if retry_delay:
                    await asyncio.sleep(retry_delay)
            else:
                break
        return [Track(**data) for data in out["tracks"]]
