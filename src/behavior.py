"""Havok behavior XML (hktagfile) model and the three duplicate operations.

Everything here works on an in-memory lxml tree. Nothing touches the disk
except ``Behavior.load`` and ``Behavior.save``, so a failed operation never
leaves a half-edited file behind.
"""

import copy
import os
import re
from collections import defaultdict

from lxml import etree

NULL = "object0"

STATE_INFO = "hkbStateMachine::StateInfo"
STATE_MACHINE = "hkbStateMachine"
CMSG = "CustomManualSelectorGenerator"
CLIP = "hkbClipGenerator"
SELECTOR = "hkbManualSelectorGenerator"
LAYER_GENERATOR = "hkbLayerGenerator"

# Containers whose children are alternatives (only one plays at a time).
# When a new state is copied, these are trimmed down to the copied branch.
# Any other container (layers, blenders, ...) plays its children together,
# so its other children are kept and shared with the original.
SELECTOR_TYPES = {SELECTOR, CMSG}

ANIMATION_NAME_RE = re.compile(r"^(a\d+)_(\d+)$")


class BehaviorError(Exception):
    """A problem the user can fix (bad input, unsupported structure, ...)."""


class Chain:
    """Objects on the path from a StateInfo down to a clip, top to bottom."""

    def __init__(self, behavior, ids):
        self.behavior = behavior
        self.ids = ids

    @property
    def state_info(self):
        return self.ids[0]

    @property
    def clip(self):
        return self.ids[-1]

    @property
    def cmsg(self):
        """The CMSG directly above the clip, or None."""
        if len(self.ids) >= 2 and self.behavior.type_of(self.ids[-2]) == CMSG:
            return self.ids[-2]
        return None

    @property
    def branch_selector(self):
        """The selector directly above the CMSG, or None.

        This is where a new branch (e.g. HangMoveB next to HangMoveL/R) goes.
        """
        if self.cmsg and len(self.ids) >= 3 and self.behavior.type_of(self.ids[-3]) == SELECTOR:
            return self.ids[-3]
        return None

    def describe(self, types=True):
        b = self.behavior
        if not types:
            return " → ".join(b.name_of(i) or f"({b.type_of(i)})" for i in self.ids)
        return " → ".join(f"{b.name_of(i) or '(unnamed)'} [{b.type_of(i)}]" for i in self.ids)


class Behavior:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self._source = f.read()
        parser = etree.XMLParser(remove_blank_text=False, huge_tree=True)
        self.root = etree.fromstring(self._source, parser)

        self.type_names = {
            t.get("id"): t.find("name").get("value") for t in self.root.findall("type")
        }
        self.objects = {o.get("id"): o for o in self.root.findall("object")}
        self._next_object_number = max(
            (int(i[len("object"):]) for i in self.objects if i[len("object"):].isdigit()),
            default=0,
        ) + 1
        self._build_parent_index()
        self._learn_formatting()

        self.string_data = self._find_single_object_with_field("eventNames")
        self.graph_data = self._find_single_object_with_field("eventInfos")

    # ------------------------------------------------------------------ basics

    def _build_parent_index(self):
        self.parents = defaultdict(list)
        for oid, obj in self.objects.items():
            for ptr in obj.iter("pointer"):
                target = ptr.get("id")
                if target != NULL and oid not in self.parents[target]:
                    self.parents[target].append(oid)

    def _find_single_object_with_field(self, field_name):
        for oid, obj in self.objects.items():
            if obj.find(f"record/field[@name='{field_name}']") is not None:
                return oid
        raise BehaviorError(f"This XML has no '{field_name}' list. Is it a behavior file (c0000/c9997)?")

    def type_of(self, oid):
        return self.type_names.get(self.objects[oid].get("typeid"), "?")

    def field(self, oid, name):
        """Top-level field element of an object (never a nested one)."""
        return self.objects[oid].find(f"record/field[@name='{name}']")

    def get_value(self, oid, name):
        f = self.field(oid, name)
        if f is None or len(f) == 0:
            return None
        el = f[0]
        if el.tag == "pointer":
            return el.get("id")
        if el.tag == "integer":
            return int(el.get("value"))
        return el.get("value")

    def set_value(self, oid, name, value):
        f = self.field(oid, name)
        if f is None:
            raise BehaviorError(f"{self.name_of(oid)} has no '{name}' field.")
        el = f[0]
        el.set("id" if el.tag == "pointer" else "value", str(value))

    def name_of(self, oid):
        name = self.get_value(oid, "name")
        return name if isinstance(name, str) else ""

    def array(self, oid, name):
        f = self.field(oid, name)
        return f.find("array") if f is not None else None

    @staticmethod
    def array_items(array):
        return [c for c in array if isinstance(c.tag, str)]

    def pointer_list(self, oid, name):
        return [p.get("id") for p in self.array_items(self.array(oid, name))]

    def objects_of_type(self, type_name):
        return [oid for oid in self.objects if self.type_of(oid) == type_name]

    def find_by_name(self, name, type_name=None):
        return [
            oid for oid in self.objects
            if self.name_of(oid) == name and (type_name is None or self.type_of(oid) == type_name)
        ]

    def clip_names(self):
        return sorted(self.name_of(oid) for oid in self.objects_of_type(CLIP))

    # ------------------------------------------------------------- tree editing

    def _new_object_id(self):
        oid = f"object{self._next_object_number}"
        self._next_object_number += 1
        return oid

    def _append_object(self, obj):
        last = self.root[-1]
        obj.tail = last.tail
        last.tail = "\n  "
        self.root.append(obj)
        oid = obj.get("id")
        self.objects[oid] = obj
        for ptr in obj.iter("pointer"):
            target = ptr.get("id")
            if target != NULL and oid not in self.parents[target]:
                self.parents[target].append(oid)

    def _clone_object(self, oid):
        new = copy.deepcopy(self.objects[oid])
        new.set("id", self._new_object_id())
        return new

    @staticmethod
    def _array_append(array, element):
        """Append to an <array>, keep its count right and match indentation."""
        items = Behavior.array_items(array)
        if items:
            last = items[-1]
            # The node before the last item may be a comment (e.g. "<!-- ArrayOf ... -->").
            before = last.getprevious()
            prev_tail = before.tail if before is not None else array.text
            element.tail = last.tail
            last.tail = prev_tail
        else:
            # Empty array looks like "<array ...> \n        </array>".
            text = array.text or ""
            closing_indent = text[text.rfind("\n"):] if "\n" in text else "\n"
            array.text = closing_indent + "  "
            element.tail = closing_indent
        array.append(element)
        array.set("count", str(len(Behavior.array_items(array))))
        return len(Behavior.array_items(array)) - 1

    def _append_pointer(self, owner_oid, field_name, target_oid):
        ptr = etree.Element("pointer", id=target_oid)
        index = self._array_append(self.array(owner_oid, field_name), ptr)
        if owner_oid not in self.parents[target_oid]:
            self.parents[target_oid].append(owner_oid)
        return index

    @staticmethod
    def _set_pointer_array(array, target_ids):
        """Replace an array of pointers with exactly ``target_ids``."""
        items = Behavior.array_items(array)
        if not items:
            for t in target_ids:
                Behavior._array_append(array, etree.Element("pointer", id=t))
            return
        before = items[0].getprevious()
        lead = before.tail if before is not None else array.text
        end_tail = items[-1].tail
        for el in items:
            array.remove(el)
        if before is not None:
            before.tail = lead
        else:
            array.text = lead
        new = [etree.SubElement(array, "pointer", id=t) for t in target_ids]
        for el in new:
            el.tail = lead
        if new:
            new[-1].tail = end_tail
        array.set("count", str(len(new)))

    # ---------------------------------------------------------------- analysis

    def find_chains(self, clip_name):
        """All StateInfo → ... → clip paths for a clip.

        A clip is usually used once, but some are shared by several CMSGs,
        so more than one chain can come back.
        """
        clips = self.find_by_name(clip_name, CLIP)
        if not clips:
            raise BehaviorError(f"No ClipGenerator named '{clip_name}' in this XML.")
        chains = []

        def walk(oid, path):
            if self.type_of(oid) == STATE_INFO:
                chains.append(Chain(self, list(reversed(path))))
                return
            for parent in self.parents.get(oid, []):
                if parent not in path:
                    walk(parent, path + [parent])

        walk(clips[0], [clips[0]])
        if not chains:
            raise BehaviorError(f"'{clip_name}' isn't inside any state, so it can't be duplicated.")
        return chains

    def state_machine_of(self, state_info):
        for parent in self.parents.get(state_info, []):
            if self.type_of(parent) == STATE_MACHINE and state_info in self.pointer_list(parent, "states"):
                return parent
        raise BehaviorError(f"Couldn't find the state machine that owns state '{self.name_of(state_info)}'.")

    def _pointer_slot(self, parent, child):
        """Where ``parent`` points at ``child``: (field name, array index or None)."""
        for f in self.objects[parent].find("record"):
            arr = f.find("array")
            if arr is not None:
                for i, el in enumerate(self.array_items(arr)):
                    if el.tag == "pointer" and el.get("id") == child:
                        return f.get("name"), i
            ptr = f.find("pointer")
            if ptr is not None and ptr.get("id") == child:
                return f.get("name"), None
        return None

    def _follow_slot(self, parent, slot):
        name, index = slot
        f = self.field(parent, name)
        if f is None:
            return None
        if index is None:
            ptr = f.find("pointer")
            return ptr.get("id") if ptr is not None else None
        arr = f.find("array")
        items = self.array_items(arr) if arr is not None else []
        if index >= len(items) or items[index].tag != "pointer":
            return None
        return items[index].get("id")

    def layer_twins(self, chain):
        """The matching paths in the other layers of a layered state.

        States like GroundSpecialAttackHoldMove play a _Motion and an _Anime
        layer together, each with its own selector driven by the same
        variable, so whatever is added to one layer must be added to the
        others at the same position. A layer only counts as a twin if it has
        the same shape (same types, same number of branches at each level).
        """
        ids = chain.ids
        layer_gens = [i for i, oid in enumerate(ids[:-1]) if self.type_of(oid) == LAYER_GENERATOR]
        if not layer_gens:
            return []
        k = layer_gens[-1]
        own = self._pointer_slot(ids[k], ids[k + 1])
        if own is None or own[1] is None:
            return []
        slots = [self._pointer_slot(ids[i], ids[i + 1]) for i in range(k + 1, len(ids) - 1)]
        if None in slots:
            return []
        twins = []
        for i, layer in enumerate(self.pointer_list(ids[k], own[0])):
            if i == own[1] or layer not in self.objects or self.type_of(layer) != self.type_of(ids[k + 1]):
                continue
            path = [layer]
            for step, slot in enumerate(slots):
                ours_parent, ours_child = ids[k + 1 + step], ids[k + 2 + step]
                child = self._follow_slot(path[-1], slot)
                if child is None or child not in self.objects or self.type_of(child) != self.type_of(ours_child):
                    break
                if slot[1] is not None and (
                    len(self.pointer_list(path[-1], slot[0])) != len(self.pointer_list(ours_parent, slot[0]))
                ):
                    break
                path.append(child)
            else:
                twins.append(Chain(self, ids[:k + 1] + path))
        return twins

    def parallel_chains(self, chain):
        """[(chain, clip namer, CMSG namer)] for the chain and each twin layer.

        A namer turns a name for the picked layer into the twin's name, e.g.
        a106_316511_Motion -> a106_316511_Anime.
        """
        same = lambda name: name  # noqa: E731
        result = [(chain, same, same)]
        for twin in self.layer_twins(chain):
            clip_namer = _name_mapper(self.name_of(chain.clip), self.name_of(twin.clip))
            cmsg_namer = same
            if chain.cmsg and twin.cmsg:
                cmsg_namer = _name_mapper(self.name_of(chain.cmsg), self.name_of(twin.cmsg))
            result.append((twin, clip_namer, cmsg_namer))
        return result

    def animation_paths(self):
        return [s.get("value") for s in self.array_items(self.array(self.string_data, "animationNames"))]

    def event_names(self):
        return [s.get("value") for s in self.array_items(self.array(self.string_data, "eventNames"))]

    def _max_int_field(self, *field_names):
        best = -1
        for name in field_names:
            for el in self.root.iterfind(f".//field[@name='{name}']/integer"):
                best = max(best, int(el.get("value")))
        return best

    # ------------------------------------------------------------ shared steps

    def _register_animation(self, source_clip, animation_name):
        """Add the .hkx path for ``animation_name`` and return its index.

        The path is built from the source clip's own path, so the character
        folder (c0000, c9997, ...) is always right. An already-listed path is
        reused instead of being added twice.
        """
        match = ANIMATION_NAME_RE.match(animation_name)
        if not match:
            raise BehaviorError(
                f"Animation name '{animation_name}' should look like a000_013810 (aXXX_number)."
            )
        offset = match.group(1)
        paths = self.animation_paths()
        source_path = paths[self.get_value(source_clip, "animationInternalId")]
        head, sep, _ = source_path.rpartition("\\hkx\\")
        if not sep:
            raise BehaviorError(f"Unexpected animation path format: {source_path}")
        new_path = f"{head}\\hkx\\{offset}\\{animation_name}.hkx"
        if new_path in paths:
            return paths.index(new_path), new_path, False
        el = etree.Element("string", value=new_path)
        index = self._array_append(self.array(self.string_data, "animationNames"), el)
        return index, new_path, True

    def _make_clip(self, source_clip, clip_name, animation_name):
        if self.find_by_name(clip_name, CLIP):
            raise BehaviorError(f"A ClipGenerator named '{clip_name}' already exists.")
        index, path, added = self._register_animation(source_clip, animation_name)
        clip = self._clone_object(source_clip)
        new_id = clip.get("id")
        self.objects[new_id] = clip  # so field helpers work before it's appended
        self.set_value(new_id, "name", clip_name)
        self.set_value(new_id, "animationName", animation_name)
        self.set_value(new_id, "animationInternalId", index)
        self._append_object(clip)
        return new_id, index, path, added

    @staticmethod
    def _anim_number(animation_name):
        m = ANIMATION_NAME_RE.match(animation_name or "")
        return int(m.group(2)) if m else None

    def _new_cmsg(self, source_cmsg, source_clip, new_clip, cmsg_name, user_data):
        if self.find_by_name(cmsg_name):
            raise BehaviorError(f"An object named '{cmsg_name}' already exists.")
        cmsg = self._clone_object(source_cmsg)
        new_id = cmsg.get("id")
        self.objects[new_id] = cmsg
        self.set_value(new_id, "name", cmsg_name)
        self.set_value(new_id, "userData", user_data)
        self._set_pointer_array(self.array(new_id, "generators"), [new_clip])
        # animId normally matches the clip's animation number; keep anything else as is.
        source_number = self._anim_number(self.get_value(source_clip, "animationName"))
        if self.get_value(new_id, "animId") == source_number:
            self.set_value(new_id, "animId", self._anim_number(self.get_value(new_clip, "animationName")))
        self._append_object(cmsg)
        return new_id

    # -------------------------------------------------------------- operations

    def _check_new_names(self, names):
        if len(set(names)) != len(names):
            raise BehaviorError("Two of the new objects would get the same name: " + ", ".join(names))
        for name in names:
            if self.find_by_name(name):
                raise BehaviorError(f"An object named '{name}' already exists.")

    def add_variation(self, chain, clip_name, animation_name):
        """Mode 1: add a clip to the source clip's existing CMSG (in every twin layer)."""
        if chain.cmsg is None:
            raise BehaviorError("The source clip isn't directly inside a CMSG, so it can't get a variation.")
        plan = [(c, clip_namer(clip_name)) for c, clip_namer, _ in self.parallel_chains(chain)]
        self._check_new_names([name for _, name in plan])
        for c, _ in plan:
            if c.cmsg is None:
                raise BehaviorError(f"The {self.name_of(c.clip)} layer has no CMSG to add a variation to.")
            for sibling in self.pointer_list(c.cmsg, "generators"):
                if sibling in self.objects and self.get_value(sibling, "animationName") == animation_name:
                    raise BehaviorError(
                        f"{self.name_of(c.cmsg)} already plays {animation_name}. "
                        "Variations need a different aXXX offset (e.g. a000 → a106)."
                    )
        log = []
        for c, name in plan:
            clip, anim_index, anim_path, added = self._make_clip(c.clip, name, animation_name)
            self._append_pointer(c.cmsg, "generators", clip)
            log.append(f"Added clip {name} ({clip}) to {self.name_of(c.cmsg)}.")
            if added or c is chain:
                log.append(_anim_log(anim_path, anim_index, added))
        return {"log": log}

    def add_branch(self, chain, cmsg_name, clip_name, animation_name):
        """Mode 2: add a new CMSG + clip next to the existing ones in a selector (in every twin layer)."""
        if chain.branch_selector is None:
            raise BehaviorError("There's no selector above this clip's CMSG, so a new branch can't be added.")
        plan = [
            (c, cmsg_namer(cmsg_name), clip_namer(clip_name))
            for c, clip_namer, cmsg_namer in self.parallel_chains(chain)
        ]
        self._check_new_names([n for _, cm, cl in plan for n in (cm, cl)])
        for c, _, _ in plan:
            if c.branch_selector is None:
                raise BehaviorError(f"The {self.name_of(c.clip)} layer has no selector to add a branch to.")
        log, indices = [], []
        for c, new_cmsg_name, new_clip_name in plan:
            clip, anim_index, anim_path, added = self._make_clip(c.clip, new_clip_name, animation_name)
            # CMSGs belonging to the same state share its userData.
            user_data = self.get_value(c.cmsg, "userData")
            cmsg = self._new_cmsg(c.cmsg, c.clip, clip, new_cmsg_name, user_data)
            index = self._append_pointer(c.branch_selector, "generators", cmsg)
            indices.append(index)
            log.append(
                f"Added {new_cmsg_name} ({cmsg}) with clip {new_clip_name} ({clip}) to "
                f"{self.name_of(c.branch_selector)} as generator index {index}."
            )
            if added or c is chain:
                log.append(_anim_log(anim_path, anim_index, added))
        if len(set(indices)) > 1:
            log.append(
                "WARNING: the new branch got different indices in each layer "
                f"({', '.join(map(str, indices))}); the layers' selectors no longer line up."
            )
        return {"log": log, "branch_index": indices[0]}

    def _copy_path(self, ids, source_clip, new_clip, renamed, user_data, replacements, state_name=None):
        """Copy ``ids`` (top → clip) bottom-up onto ``new_clip``; return (new top id, created, stateId).

        Selectors keep only the copied branch. Other containers keep their
        other children, except those listed in ``replacements`` (old id → copy).
        """
        below_old, below_new = source_clip, new_clip
        created, new_state_id = [], None
        cmsg = ids[-2] if len(ids) >= 2 and self.type_of(ids[-2]) == CMSG else None
        for oid in reversed(ids[:-1]):
            if oid == cmsg:
                new = self._new_cmsg(oid, source_clip, new_clip, renamed(oid), user_data)
            else:
                obj = self._clone_object(oid)
                new = obj.get("id")
                self.objects[new] = obj
                is_state = self.type_of(oid) == STATE_INFO
                if is_state:
                    self.set_value(new, "name", state_name)
                elif self.field(new, "name") is not None:
                    self.set_value(new, "name", renamed(oid))
                if self.type_of(oid) in SELECTOR_TYPES and self.array(new, "generators") is not None:
                    self._set_pointer_array(self.array(new, "generators"), [below_new])
                    if self.field(new, "selectedGeneratorIndex") is not None:
                        self.set_value(new, "selectedGeneratorIndex", 0)
                else:
                    swap = dict(replacements, **{below_old: below_new})
                    for ptr in obj.iter("pointer"):
                        if ptr.get("id") in swap:
                            ptr.set("id", swap[ptr.get("id")])
                if is_state:
                    new_state_id = self._max_int_field("stateId", "toStateId") + 1
                    self.set_value(new, "stateId", new_state_id)
                self._append_object(obj)
            created.append((new, self.name_of(new)))
            below_old, below_new = oid, new
        return below_new, created, new_state_id

    def add_state(self, chain, state_name, clip_name, animation_name):
        """Mode 3: copy the whole path into a brand-new state.

        Selectors on the path keep only the copied branch. In a layered state
        the matching path in every twin layer is copied too; layers without a
        twin are shared with the original. Variable binding sets, transition
        effects and other referenced objects are shared, not copied.
        """
        old_state = chain.state_info
        old_state_name = self.name_of(old_state)
        event_name = f"W_{state_name}"
        if self.find_by_name(state_name, STATE_INFO):
            raise BehaviorError(
                f"A state named '{state_name}' already exists. "
                "Use 'Add variation' or 'Add branch' to add to it instead."
            )
        if event_name in self.event_names():
            raise BehaviorError(f"The event '{event_name}' already exists in this XML.")
        state_machine = self.state_machine_of(old_state)

        def renamed(oid):
            name = self.name_of(oid)
            if old_state_name and old_state_name in name:
                return name.replace(old_state_name, state_name, 1)
            return f"{state_name} {name}".strip()

        targets = self.parallel_chains(chain)
        # Twins share the path down to the layer generator; only their own part is copied.
        split = {}
        for c, _, _ in targets[1:]:
            split[c] = next(i for i, (a, b) in enumerate(zip(chain.ids, c.ids)) if a != b)
        own_objects = list(chain.ids[1:-1]) + [oid for c, i in split.items() for oid in c.ids[i:-1]]
        new_names = [clip_namer(clip_name) for _, clip_namer, _ in targets]
        new_names += [renamed(oid) for oid in own_objects if self.field(oid, "name") is not None]
        self._check_new_names(new_names)

        log = []
        new_user_data = self._max_int_field("userData") + 1
        created, replacements = [], {}
        main_clip = None
        for c, clip_namer, _ in targets:
            clip, anim_index, anim_path, added = self._make_clip(c.clip, clip_namer(clip_name), animation_name)
            if c is chain:
                main_clip = clip
                log.append(_anim_log(anim_path, anim_index, added))
                continue
            i = split[c]
            top, made, _ = self._copy_path(c.ids[i:], c.clip, clip, renamed, new_user_data, {})
            replacements[c.ids[i]] = top
            created += [(clip, self.name_of(clip))] + made
        new_state, made, new_state_id = self._copy_path(
            chain.ids, chain.clip, main_clip, renamed, new_user_data, replacements, state_name,
        )
        created = [(main_clip, clip_name)] + made + created

        self._append_pointer(state_machine, "states", new_state)

        # Event: name + info, same index in both lists.
        event_index = self._array_append(
            self.array(self.string_data, "eventNames"), etree.Element("string", value=event_name)
        )
        event_infos = self.array(self.graph_data, "eventInfos")
        info = copy.deepcopy(self.array_items(event_infos)[-1])
        info.find("field[@name='flags']/integer").set("value", "0")
        info_index = self._array_append(event_infos, info)
        if info_index != event_index:
            raise BehaviorError(
                f"eventNames ({event_index}) and eventInfos ({info_index}) are out of sync in this XML."
            )

        log.append(f"Created state {state_name} (stateId {new_state_id}) in {self.name_of(state_machine)}.")
        log.extend(f"  new object {oid}: {name or '(' + self.type_of(oid) + ')'}" for oid, name in created)
        log.append(f"Added event {event_name} (index {event_index}).")
        log.append(self._add_wildcard_transition(state_machine, old_state, event_index, new_state_id))

        return {
            "log": log,
            "event_name": event_name,
            "source_state_name": old_state_name,
        }

    def _add_wildcard_transition(self, state_machine, old_state, event_index, new_state_id):
        """Let ``event_index`` jump to the new state from anywhere in the state machine.

        Copies the source state's wildcard transition (same blend, flags and
        intervals) and points it at the new event/state. Falls back to the
        standard record the original tool generated if the source state has
        no wildcard transition of its own.
        """
        wildcard = self.get_value(state_machine, "wildcardTransitions")
        if wildcard in (None, NULL):
            return (
                f"WARNING: {self.name_of(state_machine)} has no wildcard transitions, so nothing "
                f"fires the new state yet. Add a transition to it manually."
            )
        transitions = self.array(wildcard, "transitions")
        records = self.array_items(transitions)
        old_state_id = self.get_value(old_state, "stateId")

        def rec_int(rec, name):
            return int(rec.find(f"field[@name='{name}']/integer").get("value"))

        source = next((r for r in records if rec_int(r, "toStateId") == old_state_id), None)
        if source is not None:
            record = copy.deepcopy(source)
            note = f"copied from {self.name_of(old_state)}'s transition"
        else:
            if not records:
                return "WARNING: the wildcard transition list is empty; add a transition manually."
            effects = [r.find("field[@name='transition']/pointer").get("id") for r in records]
            effect = max(set(effects), key=effects.count)
            record = _default_transition_record(records[0], effect)
            note = f"standard settings; source state had no wildcard transition, used effect {effect}"
        record.find("field[@name='eventId']/integer").set("value", str(event_index))
        record.find("field[@name='toStateId']/integer").set("value", str(new_state_id))
        self._array_append(transitions, record)
        return f"Added wildcard transition: event {event_index} → stateId {new_state_id} ({note})."

    # -------------------------------------------------------------------- save

    def _serialize(self):
        return etree.tostring(self.root, encoding="utf-8").split(b"\n")

    def _learn_formatting(self):
        """Map lxml's spelling of a line back to how the source file spelled it.

        The converter's output mixes ``" />"`` / ``"/>"`` and CRLF / LF, which
        lxml normalizes. Lines are only remembered when the unmodified round
        trip lines up exactly, so this can never move content around.
        """
        source = self._source.split(b"\n")
        decl = source[0] if source[0].startswith(b"<?xml") else None
        source_body = source[1:] if decl is not None else source
        serialized = self._serialize()
        fixups = {}
        if len(serialized) <= len(source_body):
            for ours, theirs in zip(serialized, source_body):
                if ours != theirs:
                    fixups.setdefault(ours, theirs)
        self._formatting = (decl, fixups, source_body[len(serialized):])

    def to_bytes(self):
        decl, fixups, trailing = self._formatting
        lines = [fixups.get(line, line) for line in self._serialize()]
        if decl is not None:
            lines.insert(0, decl)
        return b"\n".join(lines + trailing)


def _name_mapper(source, twin):
    """Return a function that renames like ``source`` → ``twin`` does.

    The differing part is kept to whole ``_``-separated words, e.g.
    a104_316511_Motion → a104_316511_Anime maps a106_316511_Motion to
    a106_316511_Anime, and a000_005200_Motion → a000_005200 maps
    a000_005210_Motion to a000_005210.
    """
    def sep_before(text, i, start=0):
        return i == start or text[i - 1] == "_"

    def sep_at(text, i):
        return i == len(text) or text[i] == "_"

    p = len(os.path.commonprefix([source, twin]))
    if not (sep_before(source, p) or (sep_at(source, p) and sep_at(twin, p))):
        p = source.rfind("_", 0, p) + 1
    s = len(os.path.commonprefix([source[p:][::-1], twin[p:][::-1]]))
    ls, lt = len(source) - s, len(twin) - s
    if s and not (source[ls] == "_" or (sep_before(source, ls, p) and sep_before(twin, lt, p))):
        tail = source[ls:]
        s = len(tail) - tail.find("_") if "_" in tail else 0
        ls, lt = len(source) - s, len(twin) - s
    old, new, tail = source[p:ls], twin[p:lt], source[ls:]

    def mapped(name):
        if old:
            i = name.rfind(old)
        else:
            i = len(name) - len(tail) if name.endswith(tail) else -1
        if i < 0:
            raise BehaviorError(
                f"This state has a matching layer ({twin}) that needs the same change, but its name "
                f"can't be worked out from '{name}'. Keep the same naming pattern as {source}."
            )
        return name[:i] + new + name[i + len(old):]

    return mapped


def _anim_log(path, index, added):
    if added:
        return f"Added animation path {path} (animationInternalId {index})."
    return f"Reused existing animation path {path} (animationInternalId {index})."


def _default_transition_record(layout, effect_id):
    """The wildcard record values the original tool generated.

    ``layout`` is any existing record, copied only for its formatting.
    """
    record = copy.deepcopy(layout)
    for interval in ("triggerInterval", "initiateInterval"):
        for name, value in (("enterEventId", "-1"), ("exitEventId", "-1")):
            record.find(f"field[@name='{interval}']/record/field[@name='{name}']/integer").set("value", value)
        for name in ("enterTime", "exitTime"):
            real = record.find(f"field[@name='{interval}']/record/field[@name='{name}']/real")
            real.set("dec", "0")
            real.set("hex", "#0")
    record.find("field[@name='transition']/pointer").set("id", effect_id)
    record.find("field[@name='condition']/pointer").set("id", NULL)
    for name, value in (("fromNestedStateId", "0"), ("toNestedStateId", "0"), ("priority", "0"), ("flags", "3584")):
        record.find(f"field[@name='{name}']/integer").set("value", value)
    return record
