"""Batch jobs: one-click runs built on the single duplicate operations.

Each job is a small dataclass with ``validate()``, ``describe()`` and
``run(behavior)`` returning (log, new_states, changed); new_states are
(state name, event name) pairs that still need .txt entries.
"""

import re
from dataclasses import dataclass

from behavior import ANIMATION_NAME_RE, CLIP, CMSG, STATE_INFO, BehaviorError, Chain

CLIP_NAME_RE = re.compile(r"^(a\d+)_(\d+)(.*)$")
OFFSET_RE = re.compile(r"^a\d+$")


@dataclass
class AttackRange:
    """Attack3000-Attack3109 for NPCs, one clip per offset (a000, a100, ...)."""

    prefix: str = "Attack"
    source: int = 3000
    start: int = 3000
    end: int = 3109
    offsets: tuple = ("a000", "a100")

    def validate(self):
        problems = []
        if not re.match(r"^[A-Za-z_]+$", self.prefix):
            problems.append(f"State prefix '{self.prefix}' should only use letters and _.")
        if self.start > self.end:
            problems.append(f"The range {self.start}-{self.end} is backwards.")
        if self.end - self.start > 999:
            problems.append("That range is too large (more than 1000 states).")
        if not self.offsets:
            problems.append("Give at least one offset, e.g. a000.")
        bad = [o for o in self.offsets if not OFFSET_RE.match(o)]
        if bad:
            problems.append(f"Offsets should look like a000 or a100, not: {', '.join(bad)}")
        if len(set(self.offsets)) != len(self.offsets):
            problems.append("An offset is listed twice.")
        return problems

    def describe(self):
        return f"{self.prefix}{self.start}-{self.prefix}{self.end} ({', '.join(self.offsets)})"

    def run(self, behavior):
        return add_attack_range(behavior, self)


def add_attack_range(b, spec):
    """Make sure every ``<prefix><N>`` in the range exists with a clip per offset.

    Missing states are copied from the source state (Attack3000 is on
    practically every enemy), reusing their event if it's already
    registered. Existing states only get the offsets they're missing, so
    running this twice changes nothing the second time.

    Returns (log, new_states, changed) where new_states is a list of
    (state name, event name) for the .txt files.
    """
    source_name = f"{spec.prefix}{spec.source}"
    found = b.find_by_name(source_name, STATE_INFO)
    if not found:
        raise BehaviorError(f"This XML has no {source_name} state to copy from.")
    src_state = found[0]
    src_cmsg = b.get_value(src_state, "generator")
    if b.type_of(src_cmsg) != CMSG:
        raise BehaviorError(f"{source_name} isn't laid out as StateInfo → CMSG → clips, so it can't be batch-copied.")
    src_clips = [c for c in b.pointer_list(src_cmsg, "generators") if c in b.objects and b.type_of(c) == CLIP]
    if not src_clips:
        raise BehaviorError(f"{source_name}_CMSG has no clips to copy.")

    # Copy each offset from the source clip with the same offset when there is one.
    by_offset = {}
    for clip in src_clips:
        m = ANIMATION_NAME_RE.match(b.get_value(clip, "animationName") or "")
        if m:
            by_offset.setdefault(m.group(1), clip)
    fallback = by_offset.get(spec.offsets[0], src_clips[0])

    def source_clip(offset):
        return by_offset.get(offset, fallback)

    def names(offset, number):
        """Clip name and animationName, following the source clip's naming (e.g. _hkx_AutoSet_01)."""
        src = source_clip(offset)
        anim = ANIMATION_NAME_RE.match(b.get_value(src, "animationName") or "")
        anim_width = len(anim.group(2)) if anim else 6
        m = CLIP_NAME_RE.match(b.name_of(src))
        width, suffix = (len(m.group(2)), m.group(3)) if m else (anim_width, "")
        return f"{offset}_{number:0{width}d}{suffix}", f"{offset}_{number:0{anim_width}d}"

    def offset_of(clip):
        m = ANIMATION_NAME_RE.match(b.get_value(clip, "animationName") or "")
        return m.group(1) if m else None

    created, extended, complete, skipped = [], [], [], []
    detail, new_states = [], []

    for number in range(spec.start, spec.end + 1):
        name = f"{spec.prefix}{number}"
        states = b.find_by_name(name, STATE_INFO)

        if states:
            state = states[0]
            cmsg = b.get_value(state, "generator")
            if b.type_of(cmsg) != CMSG:
                skipped.append(name)
                detail.append(f"{name}: skipped, it isn't laid out as StateInfo → CMSG → clips.")
                continue
            have = {offset_of(c) for c in b.pointer_list(cmsg, "generators") if c in b.objects}
            missing = [o for o in spec.offsets if o not in have]
            if not missing:
                complete.append(name)
                continue
            clashes = [n for o in missing for n in [names(o, number)[0]] if b.find_by_name(n, CLIP)]
            if clashes:
                skipped.append(name)
                detail.append(f"{name}: skipped, clip(s) already used elsewhere: {', '.join(clashes)}.")
                continue
            for offset in missing:
                clip_name, anim = names(offset, number)
                b.add_variation(Chain(b, [state, cmsg, source_clip(offset)]), clip_name, anim)
            extended.append(name)
            detail.append(f"{name}: added {', '.join(missing)} to the existing state.")
            continue

        clip_names = [names(o, number)[0] for o in spec.offsets]
        taken = [n for n in clip_names + [f"{name}_CMSG"] if b.find_by_name(n)]
        if taken:
            skipped.append(name)
            detail.append(f"{name}: skipped, name(s) already used: {', '.join(taken)}.")
            continue
        first = spec.offsets[0]
        clip_name, anim = names(first, number)
        result = b.add_state(Chain(b, [src_state, src_cmsg, source_clip(first)]), name, clip_name, anim)
        new_cmsg = b.get_value(result["state"], "generator")
        for offset in spec.offsets[1:]:
            clip_name, anim = names(offset, number)
            b.add_variation(Chain(b, [result["state"], new_cmsg, source_clip(offset)]), clip_name, anim)
        created.append(name)
        new_states.append((name, result["event_name"]))
        event = "reused event" if result["event_reused"] else "new event"
        detail.append(
            f"{name}: new state (stateId {result['state_id']}, {event} {result['event_name']} "
            f"#{result['event_index']}) with {', '.join(spec.offsets)}."
        )
        detail += [f"  {line}" for line in result["log"] if "WARNING" in line]

    log = [
        f"Batch {spec.describe()} from {source_name}:",
        f"  {len(created)} new states, {len(extended)} existing states got missing offsets, "
        f"{len(complete)} already complete, {len(skipped)} skipped.",
    ] + detail
    return log, new_states, bool(created or extended)


# Float variable, 0-999, starting at 1.0 (0x3F800000), as in the hand-made example.
VARIABLE_TYPE_REAL = 4
ONE_AS_WORD = 1065353216


@dataclass
class PlaybackSpeedBinding:
    """Bind every attack clip's playbackSpeed to the AnimationPlaybackSpeed variable."""

    prefix: str = "Attack"
    start: int = 3000
    end: int = 3109
    variable: str = "AnimationPlaybackSpeed"
    member: str = "playbackSpeed"

    def validate(self):
        problems = []
        if not re.match(r"^[A-Za-z_]+$", self.prefix):
            problems.append(f"State prefix '{self.prefix}' should only use letters and _.")
        if self.start > self.end:
            problems.append(f"The range {self.start}-{self.end} is backwards.")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", self.variable):
            problems.append(f"Variable name '{self.variable}' should only use letters, numbers and _.")
        return problems

    def describe(self):
        return f"{self.member} → {self.variable} on {self.prefix}{self.start}-{self.prefix}{self.end}"

    def run(self, behavior):
        return bind_playback_speed(behavior, self)


def bind_playback_speed(b, spec):
    """Point each clip in the range at one shared binding set for the speed variable.

    Creates the variable and the binding set if this file doesn't have them.
    Clips that already use a different binding set are left alone and listed,
    since replacing it would drop whatever that set binds.
    """
    states = []
    for number in range(spec.start, spec.end + 1):
        found = b.find_by_name(f"{spec.prefix}{number}", STATE_INFO)
        if found:
            states.append(found[0])
    if not states:
        return [f"No {spec.prefix}{spec.start}-{spec.end} states in this XML; nothing to bind."], [], False

    log = [f"Batch: bind {spec.describe()}:"]
    index, created_var = b.ensure_variable(spec.variable, VARIABLE_TYPE_REAL, 0, 999, ONE_AS_WORD)
    if created_var:
        log.append(f"  Added variable {spec.variable} (#{index}): float, 0-999, starts at 1.0.")
    binding, created_set = b.binding_set_for(spec.member, index)

    bound, already, conflicts = [], [], []
    for state in states:
        for clip in b.clips_under(state):
            current = b.get_value(clip, "variableBindingSet")
            if current == binding:
                already.append(clip)
            elif current in (None, "object0"):
                b.set_value(clip, "variableBindingSet", binding)
                bound.append(clip)
            else:
                conflicts.append(f"{b.name_of(clip)} (uses {current})")
    bound_names = sorted({b.name_of(c) for c in bound})
    if created_set:
        log.append(f"  Added binding set {binding}: {spec.member} → variable #{index}.")
    elif bound:
        log.append(f"  Using existing binding set {binding}.")
    log.append(
        f"  {len(set(bound))} clips bound, {len(set(already))} already bound, "
        f"{len(conflicts)} skipped, across {len(states)} states."
    )
    if conflicts:
        log.append("  WARNING: these clips already have a different binding set and were left alone: "
                   + ", ".join(conflicts))
    if bound_names:
        log.append("  Bound: " + ", ".join(bound_names))
    return log, [], bool(bound or created_var or created_set)
