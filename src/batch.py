"""Batch jobs: one-click runs built on the single duplicate operations.

Each job is a small dataclass with ``validate()``, ``describe()`` and
``run(behavior)`` returning (log, names, changed); names is
{"states": [...], "events": [...]} for the .txt files.
"""

import re
from dataclasses import dataclass

import copy

from behavior import ANIMATION_NAME_RE, CLIP, CMSG, NULL, STATE_INFO, STATE_MACHINE, BehaviorError, Chain

CLIP_NAME_RE = re.compile(r"^(a\d+)_(\d+)(.*)$")
OFFSET_RE = re.compile(r"^a\d+$")


def offset_of(b, clip):
    m = ANIMATION_NAME_RE.match(b.get_value(clip, "animationName") or "")
    return m.group(1) if m else None


def clips_by_offset(b, cmsg):
    """{offset: first clip with that offset} for a CMSG, in the CMSG's order."""
    found = {}
    for clip in b.pointer_list(cmsg, "generators"):
        if clip in b.objects and b.type_of(clip) == CLIP:
            found.setdefault(offset_of(b, clip), clip)
    return found


def clip_names(b, source_clip, offset, number):
    """Clip name and animationName for ``number``, following the source clip's naming (e.g. _hkx_AutoSet_01)."""
    anim = ANIMATION_NAME_RE.match(b.get_value(source_clip, "animationName") or "")
    anim_width = len(anim.group(2)) if anim else 6
    m = CLIP_NAME_RE.match(b.name_of(source_clip))
    width, suffix = (len(m.group(2)), m.group(3)) if m else (anim_width, "")
    return f"{offset}_{number:0{width}d}{suffix}", f"{offset}_{number:0{anim_width}d}"


def simple_cmsg(b, state, label):
    cmsg = b.get_value(state, "generator")
    if b.type_of(cmsg) != CMSG:
        raise BehaviorError(f"{label} isn't laid out as StateInfo → CMSG → clips, so it can't be copied.")
    if not clips_by_offset(b, cmsg):
        raise BehaviorError(f"{label} has no clips to copy.")
    return cmsg


def add_missing_offsets(b, state, number, offsets, source_for):
    """Add a clip for each offset the state's CMSG doesn't have yet.

    Returns the offsets added, or raises BehaviorError (nothing changed) if a
    needed clip name is already taken somewhere else.
    """
    cmsg = b.get_value(state, "generator")
    if b.type_of(cmsg) != CMSG:
        raise BehaviorError("it isn't laid out as StateInfo → CMSG → clips")
    missing = [o for o in offsets if o not in clips_by_offset(b, cmsg)]
    planned = [(o, *clip_names(b, source_for(o), o, number)) for o in missing]
    clashes = [name for _, name, _ in planned if b.find_by_name(name, CLIP)]
    if clashes:
        raise BehaviorError(f"clip(s) already used elsewhere: {', '.join(clashes)}")
    for offset, name, anim in planned:
        b.add_variation(Chain(b, [state, cmsg, source_for(offset)]), name, anim)
    return missing


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
    """
    source_name = f"{spec.prefix}{spec.source}"
    found = b.find_by_name(source_name, STATE_INFO)
    if not found:
        raise BehaviorError(f"This XML has no {source_name} state to copy from.")
    src_state = found[0]
    src_cmsg = simple_cmsg(b, src_state, source_name)
    by_offset = clips_by_offset(b, src_cmsg)
    fallback = by_offset.get(spec.offsets[0], next(iter(by_offset.values())))

    def source_clip(offset):
        return by_offset.get(offset, fallback)

    created, extended, complete, skipped = [], [], [], []
    detail, names = [], {"states": [], "events": []}

    for number in range(spec.start, spec.end + 1):
        name = f"{spec.prefix}{number}"
        states = b.find_by_name(name, STATE_INFO)

        if states:
            try:
                added = add_missing_offsets(b, states[0], number, spec.offsets, source_clip)
            except BehaviorError as e:
                skipped.append(name)
                detail.append(f"{name}: skipped, {e}.")
                continue
            if added:
                extended.append(name)
                detail.append(f"{name}: added {', '.join(added)} to the existing state.")
            else:
                complete.append(name)
            continue

        planned = [clip_names(b, source_clip(o), o, number) for o in spec.offsets]
        taken = [n for n in [c for c, _ in planned] + [f"{name}_CMSG"] if b.find_by_name(n)]
        if taken:
            skipped.append(name)
            detail.append(f"{name}: skipped, name(s) already used: {', '.join(taken)}.")
            continue
        first = spec.offsets[0]
        result = b.add_state(Chain(b, [src_state, src_cmsg, source_clip(first)]), name, *planned[0])
        new_cmsg = b.get_value(result["state"], "generator")
        for offset, (clip_name, anim) in zip(spec.offsets[1:], planned[1:]):
            b.add_variation(Chain(b, [result["state"], new_cmsg, source_clip(offset)]), clip_name, anim)
        created.append(name)
        names["states"].append(name)
        names["events"].append(result["event_name"])
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
    return log, names, bool(created or extended)


# --------------------------------------------------------------- jump attacks
# A jump attack is three linked states: 32X0 start (its own transition
# "JumpAttack32X0_to_JumpAttack32X1" leads to the loop), 32X1 loop and
# 32X2 landing. Groups start at every ten: 3200, 3210, ... 3290.

SET_SIZE = 3


def state_set(b, prefix, base):
    """The three states of the set starting at ``base``, or None for any that are missing."""
    return [next(iter(b.find_by_name(f"{prefix}{base + k}", STATE_INFO)), None) for k in range(SET_SIZE)]


def set_base(state_name, prefix="JumpAttack"):
    """3260 for 'JumpAttack3261'; None if the name isn't part of a jump set."""
    m = re.match(rf"^{re.escape(prefix)}(\d+)$", state_name or "")
    if not m or int(m.group(1)) % 10 >= SET_SIZE:
        return None
    return int(m.group(1)) // 10 * 10


def is_jump_set(b, state):
    """True if ``state`` is part of a complete start/loop/landing set whose start leads to its loop."""
    base = set_base(b.name_of(state))
    if base is None:
        return False
    prefix = re.match(r"^(\D+)", b.name_of(state)).group(1)
    states = state_set(b, prefix, base)
    if None in states:
        return False
    own = b.get_value(states[0], "transitions")
    if own in (None, "object0"):
        return False
    loop_id = b.get_value(states[1], "stateId")
    targets = [int(r.find("field[@name='toStateId']/integer").get("value"))
               for r in b.array_items(b.array(own, "transitions"))]
    return loop_id in targets


def copy_state_set(b, prefix, source_base, new_base, offsets=None):
    """Copy the start/loop/landing set at ``source_base`` to ``new_base``.

    Clips are renamed by number (a000_003200_hkx_AutoSet_00 → a000_003260_…).
    With ``offsets`` each new state gets exactly those offsets; without, it
    gets the same offsets its source state has. Returns (log, names).
    """
    sources = state_set(b, prefix, source_base)
    if None in sources:
        missing = [f"{prefix}{source_base + k}" for k, s in enumerate(sources) if s is None]
        raise BehaviorError(f"Can't copy the {prefix}{source_base} set: missing {', '.join(missing)}.")
    cmsgs = [simple_cmsg(b, s, b.name_of(s)) for s in sources]
    by_offset = [clips_by_offset(b, c) for c in cmsgs]
    wanted = [list(offsets) if offsets else list(o) for o in by_offset]

    def source_for(k):
        fallback = by_offset[k].get(wanted[k][0], next(iter(by_offset[k].values())))
        return lambda offset: by_offset[k].get(offset, fallback)

    new_names = [f"{prefix}{new_base + k}" for k in range(SET_SIZE)]
    planned = [[clip_names(b, source_for(k)(o), o, new_base + k) for o in wanted[k]] for k in range(SET_SIZE)]
    taken = [n for k in range(SET_SIZE) for n in [new_names[k], f"{new_names[k]}_CMSG"] + [c for c, _ in planned[k]]
             if b.find_by_name(n)]
    if taken:
        raise BehaviorError(f"name(s) already used: {', '.join(taken)}")

    chains = [Chain(b, [sources[k], cmsgs[k], source_for(k)(wanted[k][0])]) for k in range(SET_SIZE)]
    group = b.add_state_group(chains, new_names, [p[0][0] for p in planned], [p[0][1] for p in planned])
    log = []
    for k, result in enumerate(group["results"]):
        new_cmsg = b.get_value(result["state"], "generator")
        for offset, (clip_name, anim) in zip(wanted[k][1:], planned[k][1:]):
            b.add_variation(Chain(b, [result["state"], new_cmsg, source_for(k)(offset)]), clip_name, anim)
        event = "reused event" if result["event_reused"] else "new event"
        log.append(f"{new_names[k]}: new state (stateId {result['state_id']}, {event} {result['event_name']} "
                   f"#{result['event_index']}) with {', '.join(c for c, _ in planned[k])}.")
        log += [f"  {line}" for line in result["log"] if "WARNING" in line]
    log += group["log"]
    names = {"states": new_names, "events": [r["event_name"] for r in group["results"]] + group["events"]}
    return log, names


# What a jump state differs in from a plain attack (from a hand-made c9997):
START_ANIME_END_EVENT = 0   # start CMSG; attacks use 3
LOOP_CLIP_MODE = 1          # loop clips play looping; attacks play once (0)


def _parent_state(b, machine):
    return next((p for p in b.parents.get(machine, []) if b.type_of(p) == STATE_INFO), None)


def build_jump_attacks(b, prefix, base, attack_source, offsets):
    """Give an enemy without jump attacks its first set, built from a plain attack.

    Adds a ``<prefix>`` state (copied from the attack's parent, e.g.
    DefualtAttack) holding a new ``<prefix>_SM``, then the start/loop/landing
    states copied from ``attack_source`` with the few jump-specific settings,
    and the start state's own transition into the loop. Jump wildcard
    transitions are global, so nothing else in the graph needs wiring.
    Returns (log, names).
    """
    found = b.find_by_name(attack_source, STATE_INFO)
    if not found:
        raise BehaviorError(f"This XML has no jump attacks and no {attack_source} to build them from.")
    attack = found[0]
    attack_cmsg = simple_cmsg(b, attack, attack_source)
    attack_machine = b.state_machine_of(attack)
    log = []

    existing = b.find_by_name(prefix, STATE_INFO)
    if existing:
        machine = b.get_value(existing[0], "generator")
        if b.type_of(machine) != STATE_MACHINE:
            raise BehaviorError(f"{prefix} exists but doesn't hold a state machine.")
        created_machine = False
    else:
        template_state = _parent_state(b, attack_machine)
        if template_state is None:
            raise BehaviorError(f"Couldn't find the state that holds {b.name_of(attack_machine)}.")
        parent_machine = b.state_machine_of(template_state)
        if b.find_by_name(f"{prefix}_SM"):
            raise BehaviorError(f"{prefix}_SM already exists without a {prefix} state; fix it by hand.")

        # The state machine: a copy of the attack machine with no states and no wildcard entries.
        wildcard_src = b.get_value(attack_machine, "wildcardTransitions")
        wildcard = b._clone_object(wildcard_src)
        b.objects[wildcard.get("id")] = wildcard
        b._clear_array(b.array(wildcard.get("id"), "transitions"))
        b._append_object(wildcard)
        sm = b._clone_object(attack_machine)
        machine = sm.get("id")
        b.objects[machine] = sm
        b.set_value(machine, "name", f"{prefix}_SM")
        b._clear_array(b.array(machine, "states"))
        b.set_value(machine, "wildcardTransitions", wildcard.get("id"))
        b._append_object(sm)

        # The state that holds it, next to the attack machine's own state (e.g. DefualtAttack).
        holder = b._clone_object(template_state)
        holder_id = holder.get("id")
        b.objects[holder_id] = holder
        b.set_value(holder_id, "name", prefix)
        b.set_value(holder_id, "generator", machine)
        siblings = [b.get_value(s, "stateId") for s in b.pointer_list(parent_machine, "states")]
        b.set_value(holder_id, "stateId", max(siblings) + 1)
        b._append_object(holder)
        b._append_pointer(parent_machine, "states", holder_id)
        b.parents[machine].append(holder_id)
        created_machine = True
        log.append(f"Added state {prefix} (stateId {max(siblings) + 1}) to {b.name_of(parent_machine)}, "
                   f"holding the new {prefix}_SM.")

    by_offset = clips_by_offset(b, attack_cmsg)
    fallback = by_offset.get(offsets[0], next(iter(by_offset.values())))

    def source_clip(offset):
        return by_offset.get(offset, fallback)

    states, names = [], {"states": [], "events": []}
    for k in range(SET_SIZE):
        number = base + k
        name = f"{prefix}{number}"
        planned = [clip_names(b, source_clip(o), o, number) for o in offsets]
        result = b.add_state(Chain(b, [attack, attack_cmsg, source_clip(offsets[0])]), name, *planned[0],
                             machine=machine)
        cmsg = b.get_value(result["state"], "generator")
        for offset, (clip_name, anim) in zip(offsets[1:], planned[1:]):
            b.add_variation(Chain(b, [result["state"], cmsg, source_clip(offset)]), clip_name, anim)
        states.append(result)
        names["states"].append(name)
        names["events"].append(result["event_name"])
        log.append(f"{name}: new state (stateId {result['state_id']}) copied from {attack_source} "
                   f"with {', '.join(c for c, _ in planned)}.")

    start, loop = states[0], states[1]
    b.set_value(b.get_value(start["state"], "generator"), "animeEndEventType", START_ANIME_END_EVENT)
    for clip in b.pointer_list(b.get_value(loop["state"], "generator"), "generators"):
        b.set_value(clip, "mode", LOOP_CLIP_MODE)
    if created_machine:
        b.set_value(machine, "startStateId", start["state_id"])

    # The start state's own transition: its wildcard entry, aimed at the loop, as a normal transition.
    wildcard = b.get_value(machine, "wildcardTransitions")
    entry = next(r for r in b.array_items(b.array(wildcard, "transitions"))
                 if r.find("field[@name='toStateId']/integer").get("value") == str(start["state_id"]))
    own = b._clone_object(wildcard)
    own_id = own.get("id")
    b.objects[own_id] = own
    records = b.array(own_id, "transitions")
    b._clear_array(records)
    record = copy.deepcopy(entry)
    event_name = f"{prefix}{base}_to_{prefix}{base + 1}"
    event_index, reused = b._ensure_event(event_name)
    record.find("field[@name='eventId']/integer").set("value", str(event_index))
    record.find("field[@name='toStateId']/integer").set("value", str(loop["state_id"]))
    record.find("field[@name='flags']/integer").set("value", "0")
    b._array_append(records, record)
    b._append_object(own)
    b.set_value(start["state"], "transitions", own_id)
    b.parents[own_id].append(start["state"])
    names["events"].append(event_name)
    log.append(f"{prefix}{base}: own transition {event_name} (#{event_index}, "
               f"{'reused' if reused else 'new'} event) → {prefix}{base + 1}; start CMSG ends with event type "
               f"{START_ANIME_END_EVENT}, {prefix}{base + 1} clips loop.")
    return log, names


@dataclass
class JumpAttackRange:
    """JumpAttack3200-3292: start/loop/landing sets at every ten, one clip per offset."""

    prefix: str = "JumpAttack"
    source: int = 3200
    start: int = 3200
    end: int = 3292
    offsets: tuple = ("a000", "a100")
    attack_source: str = "Attack3000"   # used only when the enemy has no jump attacks at all

    def bases(self):
        return list(range(self.start // 10 * 10, self.end // 10 * 10 + 1, 10))

    def validate(self):
        problems = AttackRange(self.prefix, self.source, self.start, self.end, self.offsets).validate()
        if self.source % 10:
            problems.append(f"The source set should start at a round number like 3200, not {self.source}.")
        return problems

    def describe(self):
        return f"{self.prefix}{self.start}-{self.prefix}{self.end} jump sets ({', '.join(self.offsets)})"

    def run(self, behavior):
        return add_jump_range(behavior, self)


def add_jump_range(b, spec):
    """Make sure every jump set in the range exists with a clip per offset in each of its three states."""
    source_name = f"{spec.prefix}{spec.source}"
    sources = state_set(b, spec.prefix, spec.source)
    built, names = [], {"states": [], "events": []}
    if None in sources:
        if any(sources):
            raise BehaviorError(f"The {source_name} set is incomplete; fix it before copying from it.")
        others = [base for base in spec.bases() if None not in state_set(b, spec.prefix, base)]
        if others:
            raise BehaviorError(f"This XML has no {source_name} set; copy from {spec.prefix}{others[0]} instead.")
        built, names = build_jump_attacks(b, spec.prefix, spec.source, spec.attack_source, spec.offsets)
        sources = state_set(b, spec.prefix, spec.source)
    by_offset = [clips_by_offset(b, simple_cmsg(b, s, b.name_of(s))) for s in sources]

    def source_for(k):
        fallback = by_offset[k].get(spec.offsets[0], next(iter(by_offset[k].values())))
        return lambda offset: by_offset[k].get(offset, fallback)

    created, extended, complete, skipped = [], [], [], []
    detail = []
    if built:
        created.append(f"{source_name}-{spec.source + SET_SIZE - 1}")
        detail += [f"This enemy had no jump attacks; built the first set from {spec.attack_source}:"]
        detail += [f"  {line}" for line in built]
    for base in spec.bases():
        label = f"{spec.prefix}{base}-{base + SET_SIZE - 1}"
        states = state_set(b, spec.prefix, base)
        if None not in states:
            if built and base == spec.source:
                continue
            added = []
            try:
                for k, state in enumerate(states):
                    for offset in add_missing_offsets(b, state, base + k, spec.offsets, source_for(k)):
                        added.append(f"{offset} to {spec.prefix}{base + k}")
            except BehaviorError as e:
                skipped.append(label)
                detail.append(f"{label}: stopped, {e}.")
                if added:
                    extended.append(label)
                continue
            if added:
                extended.append(label)
                detail.append(f"{label}: added {', '.join(added)}.")
            else:
                complete.append(label)
            continue
        if any(states):
            have = [f"{spec.prefix}{base + k}" for k, s in enumerate(states) if s]
            skipped.append(label)
            detail.append(f"{label}: skipped, only part of the set exists ({', '.join(have)}).")
            continue
        try:
            lines, new = copy_state_set(b, spec.prefix, spec.source, base, spec.offsets)
        except BehaviorError as e:
            skipped.append(label)
            detail.append(f"{label}: skipped, {e}.")
            continue
        created.append(label)
        detail += lines
        names["states"] += new["states"]
        names["events"] += new["events"]

    log = [
        f"Batch {spec.describe()} from {source_name}:",
        f"  {len(created)} new sets, {len(extended)} existing sets got missing offsets, "
        f"{len(complete)} already complete, {len(skipped)} skipped.",
    ] + detail
    return log, names, bool(created or extended)


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
        return [f"No {spec.prefix}{spec.start}-{spec.end} states in this XML; nothing to bind."], {}, False

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
    return log, {}, bool(bound or created_var or created_set)
