"""In-memory editor for c0000_cmsg.hks."""

import re

HKB_CONST_RE = re.compile(r"^(HKB_STATE_\w+)\s*=\s*(-?\d+)[ \t]*$", re.M)
FUNCTION_KINDS = ("onUpdate", "onActivate", "onDeactivate")


class HksError(Exception):
    pass


def to_hkb_state(state_name):
    """GroundAttackCombo5 -> HKB_STATE_GROUND_ATTACK_COMBO_5 (FromSoftware's convention)."""
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", state_name)
    s = re.sub(r"(\D)(\d)", r"\1_\2", s)
    return "HKB_STATE_" + s.upper()


class HksScript:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            raw = f.read()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.text = text.replace("\r\n", "\n")

    def to_bytes(self):
        data = self.text.replace("\n", self.newline).encode("utf-8")
        return (b"\xef\xbb\xbf" + data) if self.bom else data

    # ---------------------------------------------------------------- queries

    def constants(self):
        return {m.group(1): int(m.group(2)) for m in HKB_CONST_RE.finditer(self.text)}

    def _table_span(self):
        """(start, end) of the ``g_paramHkbState = { ... }`` table; end is the closing brace."""
        m = re.search(r"^g_paramHkbState\s*=\s*\{", self.text, re.M)
        if not m:
            raise HksError("Couldn't find the g_paramHkbState table in the HKS file.")
        depth = 0
        for i in range(m.end() - 1, len(self.text)):
            c = self.text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return m.start(), i
        raise HksError("The g_paramHkbState table has unbalanced braces.")

    def table_entry(self, const):
        start, end = self._table_span()
        m = re.search(r"\[\s*" + re.escape(const) + r"\s*\]\s*=\s*\{[^{}]*\}", self.text[start:end])
        return m.group(0) if m else None

    def _function(self, state_name, kind):
        m = re.search(
            rf"^function {re.escape(state_name)}_{kind}\(\)\n.*?^end[ \t]*$",
            self.text, re.M | re.S,
        )
        return m.group(0) if m else None

    # ---------------------------------------------------------------- editing

    def add_state(self, new_state, source_state):
        """Register ``new_state`` as a copy of ``source_state``. Returns log lines."""
        new_const = to_hkb_state(new_state)
        source_const = to_hkb_state(source_state)
        constants = self.constants()
        if new_const in constants:
            raise HksError(f"{new_const} already exists in the HKS file.")
        if not constants:
            raise HksError("No HKB_STATE_ constants found in the HKS file.")
        log = []

        # 1. Constant, right after the last existing one.
        value = max(constants.values()) + 1
        last = list(HKB_CONST_RE.finditer(self.text))[-1]
        self.text = self.text[:last.end()] + f"\n{new_const} = {value}" + self.text[last.end():]
        log.append(f"HKS: added {new_const} = {value}.")

        # 2. g_paramHkbState entry, copied from the source state.
        entry = self.table_entry(source_const)
        if entry is None:
            log.append(
                f"HKS WARNING: {source_const} has no g_paramHkbState entry to copy; "
                f"add one for {new_const} manually."
            )
        else:
            new_entry = re.sub(r"^\[\s*" + re.escape(source_const) + r"\s*\]", f"[{new_const}]", entry)
            start, end = self._table_span()
            body = self.text[start:end]
            stripped = body.rstrip()
            needs_comma = not stripped.endswith((",", "{"))
            insert_at = start + len(stripped)
            if "\n" in body.strip():
                # Multi-line table: match the indentation of the last entry.
                last_line = stripped[stripped.rfind("\n") + 1:]
                indent = last_line[: len(last_line) - len(last_line.lstrip())]
                addition = ("," if needs_comma else "") + f"\n{indent}{new_entry}"
            else:
                addition = ("," if needs_comma else "") + f" {new_entry}"
            self.text = self.text[:insert_at] + addition + self.text[insert_at:]
            log.append(f"HKS: added g_paramHkbState entry {new_entry}.")

        # 3. Functions, copied from the source state (or a blank template).
        blocks = []
        copied = 0
        for kind in FUNCTION_KINDS:
            source = self._function(source_state, kind)
            if source is not None:
                copied += 1
                block = source.replace(f"function {source_state}_{kind}()", f"function {new_state}_{kind}()", 1)
                block = re.sub(r"\b" + re.escape(source_const) + r"\b", new_const, block)
            elif kind == "onUpdate":
                block = f"function {new_state}_{kind}()\n    UpdateState({new_const})\n    \nend"
            else:
                block = f"function {new_state}_{kind}()\n    return\n    \nend"
            blocks.append(block)
        self.text = self.text.rstrip("\n") + "\n\n" + "\n\n".join(blocks) + "\n"
        if copied == len(FUNCTION_KINDS):
            log.append(f"HKS: added {new_state}_onUpdate/onActivate/onDeactivate (copied from {source_state}).")
        else:
            log.append(f"HKS: added {new_state}_onUpdate/onActivate/onDeactivate.")
        return log
