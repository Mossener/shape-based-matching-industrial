"""Independent pinned numeric-byte reader; no image/native process access."""
def members(encoded, expected):
    return {}


class Reader:
    def __init__(self, root):
        self.root = root

    def check(self, pin):
        return b''
