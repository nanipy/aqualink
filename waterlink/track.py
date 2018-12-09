class Track:

    __slots__ = (
        "track",
        "_info",
        "identifier",
        "seekable",
        "author",
        "length",
        "stream",
        "position",
        "title",
        "url",
    )

    def __init__(self, **kwargs):
        self.track = kwargs["track"]
        self._info = kwargs["info"]
        self.identifier = self._info.get("identifier")
        self.seekable = self._info.get("isSeekable")
        self.author = self._info.get("author")
        self.length = self._info.get("length")
        self.stream = self._info.get("isStream")
        self.position = self._info.get("position")
        self.title = self._info.get("title")
        self.url = self._info.get("uri")
        self.thumbnail = f"https://img.youtube.com/vi/{self.identifier}/default.jpg" if 'youtube' in self.url else ""

    def __repr__(self):
        return (
            f"<Track title={self.title} length={self.length}>"
            if self.title and self.length
            else f"<Track track={self.track}>"
        )
