"""
server/anima_server/core/sentinel.py — Pipeline sentinels.
"""


class _Sentinel:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"<Sentinel: {self.name}>"


END_OF_RESPONSE = _Sentinel("END_OF_RESPONSE")
END_OF_SPEECH = _Sentinel("END_OF_SPEECH")
