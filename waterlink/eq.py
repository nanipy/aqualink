class Equalizer:
    def __init__(self, **options):
        for k, v in options.items():
            setattr(self, k, v)

    @classmethod
    def bassboost(cls):
        return cls(
            **{
                "off": [(0, 0), (1, 0)],
                "low": [(0, 0.25), (1, 0.15)],
                "medium": [(0, 0.50), (1, 0.25)],
                "high": [(0, 0.75), (1, 0.50)],
                "insane": [(0, 1), (1, 0.75)],
                "ultra": [(0, 1), (1, 2.0)],
            }
        )
