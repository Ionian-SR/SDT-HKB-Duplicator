"""In-memory editor for eventnameid.txt / statenameid.txt.

The files are Shift-JIS (cp932) with a Japanese comment on the first line, a
``Num = <count>`` header and one ``<id> = "<name>"`` line per entry.
"""

import re

ENTRY_RE = re.compile(r'^\s*(\d+)\s*=\s*"(.*)"\s*$')
NUM_RE = re.compile(r"^(Num\s*=\s*)(\d+)(.*)$")


class IdMap:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-8-sig")
            self.encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
        except UnicodeDecodeError:
            text = raw.decode("cp932")
            self.encoding = "cp932"
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.trailing_newline = text.endswith(("\n", "\r"))
        self.lines = text.replace("\r\n", "\n").split("\n")
        if self.trailing_newline:
            self.lines.pop()

    def entries(self):
        return [(int(m.group(1)), m.group(2)) for m in map(ENTRY_RE.match, self.lines) if m]

    def __contains__(self, name):
        return any(n == name for _, n in self.entries())

    def append(self, name):
        """Add ``name`` with the next free ID and update the Num header. Returns the ID."""
        entries = self.entries()
        new_id = max((i for i, _ in entries), default=0) + 1
        self.lines.append(f'{new_id:<4} = "{name}"')
        for i, line in enumerate(self.lines):
            m = NUM_RE.match(line)
            if m:
                self.lines[i] = f"{m.group(1)}{len(entries) + 1}{m.group(3)}"
                break
        return new_id

    def to_bytes(self):
        text = self.newline.join(self.lines) + (self.newline if self.trailing_newline else "")
        return text.encode(self.encoding)
