from inspect import isawaitable, signature
from typing import Optional, Callable
from .track import Track

try:
    from discord import VoiceChannel, Guild
except ImportError:
    try:
        from discordjspy import VoiceChannel, Guild
    except ImportError:
        raise ImportError("You don't have discord.py or discord.jspy installed!")


class Player:
    __slots__ = (
        "connection",
        "track",
        "_guild",
        "_channel",
        "_paused",
        "_playing",
        "_position",
        "_volume",
        "_track_callback",
        "_connecting",
    )

    def __init__(self, connection, guild_id: int) -> None:
        self.connection = connection
        self.track = None
        self._guild = guild_id
        self._connecting = False
        self._channel = None
        self._paused = False
        self._playing = False
        self._position = None
        self._volume = 100
        self._track_callback = None

    @property
    def channel(self) -> Optional[VoiceChannel]:
        """Returns the channel the player is connected to."""
        if self._channel is None:
            return
        return self.connection.bot.get_channel(self._channel)

    @property
    def guild(self) -> Guild:
        """Returns the player's guild."""
        return self.connection.bot.get_guild(self._guild)

    @property
    def connected(self) -> bool:
        """Returns the player's connected state."""
        return bool(self._channel)

    @property
    def position(self) -> Optional[float]:
        """Returns the player's current position in seconds."""
        return self._position

    @property
    def paused(self) -> bool:
        """Returns the player's paused state."""
        return self._paused

    @property
    def playing(self) -> bool:
        """Returns the player's playing state."""
        if self.paused:
            return False
        return self._playing

    @property
    def stopped(self) -> bool:
        """Returns the player's stopped (neither playing nor paused) state."""
        return not self.playing and not self.paused

    @property
    def volume(self) -> int:
        """Returns the player's volume."""
        return self._volume

    @property
    def track_callback(self) -> Optional[Callable]:
        """Accesses the track callback.
        This is the callable that will be called with the current player's instance as its first argument.
        It may be awaitable. If it is None, it will be ignored.
        """
        return self._track_callback

    @track_callback.setter
    def track_callback(self, c: Optional[Callable]) -> None:
        self._track_callback = c

    async def connect(self, channel_id: int) -> None:
        """Connects the player to a Discord channel."""
        self._connecting = True
        await self.connection._discord_connect(self._guild, channel_id)
        self._channel = channel_id

    async def disconnect(self):
        """Disconnects the player from Discord."""
        await self.connection._discord_disconnect(self._guild)
        self._channel = None

    async def query(self, *args, **kwargs):
        """Shortcut method for :meth:`Connection.query`."""
        return await self.connection.query(*args, **kwargs)

    async def play(self, track: Track, start_time: float = 0.0, end_time: float = None):
        """
        Plays a track. If already playing, replaces the current track.
        :param track: A base64 track ID returned by the :meth:`Connection.query` method.
        :param start_time: (optional) How far into the track to start playing (defaults to 0).
        :param end_time: (optional) At what point in the track to stop playing (defaults to track length).
        """
        await self.connection._play(self._guild, track.track, start_time, end_time)
        self._playing = True
        self.track = track

    async def set_pause(self, paused: bool):
        """Sets the pause state."""
        if paused == self._paused:
            return
        await self.connection._pause(self._guild, paused)
        self._paused = paused

    async def set_volume(self, volume: int):
        """
        Sets the player's volume.
        :param volume: An integer between (and including) 0 and 150.
        """
        self._volume = await self.connection._volume(self._guild, volume)

    async def stop(self):
        """Stops the player."""
        await self.connection._stop(self._guild)
        self._playing = False

    async def seek(self, position: float):
        """Seeks to a specific position in a track."""
        await self.connection._seek(self._guild, position)

    async def set_gain(self, band: int, gain: float = 0.0):
        """Sets the equalizer gain."""
        await self.set_gains((band, gain))

    async def set_gains(self, *gain_list):
        """Modifies the player's equalizer settings."""
        update_package = []
        for value in gain_list:
            if not isinstance(value, tuple):
                raise TypeError("gain_list must be a list of tuples")

            band = value[0]
            gain = value[1]

            if -1 > value[0] > 15:
                continue

            gain = max(min(float(gain), 1.0), -0.25)
            update_package.append({"band": band, "gain": gain})
            self.equalizer[band] = gain

        await self.connection._send(
            op="equalizer", guildId=self._guild, bands=update_package
        )

    async def reset_equalizer(self):
        """Resets equalizer to default values."""
        await self.set_gains(*[(x, 0.0) for x in range(15)])

    async def _process_event(self, data):
        if data["op"] != "event":
            return

        if data["type"] != "TrackEndEvent":
            return

        self._playing = False
        self._position = None
        self.track = None

        if not self.track_callback:
            return

        kwargs = {}
        sig = signature(self.track_callback)
        if sig:
            if "player" in sig.parameters:
                kwargs["player"] = self
            if "reason" in sig.parameters:
                kwargs["reason"] = data.get("reason")

        out = self.track_callback(**kwargs)
        if isawaitable(out):
            await out
