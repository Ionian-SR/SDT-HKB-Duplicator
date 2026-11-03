"""Regression tests against the real template files.

Run from the repo root:  python -m unittest discover tests
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
TEMPLATE = os.path.join(SRC, "template")
FIXTURES = os.path.join(HERE, "fixtures")
sys.path.insert(0, SRC)

from batch import AttackRange, JumpAttackRange, PlaybackSpeedBinding  # noqa: E402
from behavior import Behavior, BehaviorError  # noqa: E402
from hks_parser import HksScript, to_hkb_state  # noqa: E402
from id_maps import IdMap  # noqa: E402
from project import BRANCH, STATE, VARIATION, Project, ProjectError, Request  # noqa: E402


class ProjectCase(unittest.TestCase):
    xml = "c0000.xml"
    hks = "c0000_cmsg.hks"

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for name in os.listdir(TEMPLATE):
            shutil.copy(os.path.join(TEMPLATE, name), self.dir)
        if getattr(self, "fixture", None):
            shutil.copy(os.path.join(FIXTURES, self.fixture), os.path.join(self.dir, self.xml))
        p = lambda n: os.path.join(self.dir, n) if n else ""  # noqa: E731
        self.project = Project.create(
            p("project.json"), "Test", p(self.xml), p(self.hks), p("eventnameid.txt"), p("statenameid.txt")
        )

    def tearDown(self):
        shutil.rmtree(self.dir)

    def path(self, name):
        return os.path.join(self.dir, name)

    def read(self, name):
        with open(self.path(name), "rb") as f:
            return f.read()

    def behavior(self):
        return Behavior(self.path(self.xml))

    def wildcard_records(self, b, state_name):
        state = b.find_by_name(state_name, "hkbStateMachine::StateInfo")[0]
        sm = b.state_machine_of(state)
        array = b.array(b.get_value(sm, "wildcardTransitions"), "transitions")
        return state, sm, b.array_items(array)


class RoundTrip(unittest.TestCase):
    def test_xml_saves_byte_identical_when_unchanged(self):
        for name in ("c0000.xml", "c9997.xml"):
            path = os.path.join(TEMPLATE, name)
            with open(path, "rb") as f:
                self.assertEqual(Behavior(path).to_bytes(), f.read(), name)

    def test_text_files_save_byte_identical_when_unchanged(self):
        for name in ("eventnameid.txt", "statenameid.txt"):
            path = os.path.join(TEMPLATE, name)
            with open(path, "rb") as f:
                self.assertEqual(IdMap(path).to_bytes(), f.read(), name)
        path = os.path.join(TEMPLATE, "c0000_cmsg.hks")
        with open(path, "rb") as f:
            self.assertEqual(HksScript(path).to_bytes(), f.read())

    def test_hkb_state_names(self):
        self.assertEqual(to_hkb_state("GroundAttackCombo5"), "HKB_STATE_GROUND_ATTACK_COMBO_5")
        self.assertEqual(to_hkb_state("HangMove"), "HKB_STATE_HANG_MOVE")


class NewState(ProjectCase):
    def test_simple_state_matches_original_tool(self):
        self.project.apply(Request(
            STATE, "a050_300040", "a050_300050", "a050_300050", new_name="GroundAttackCombo6", edit_hks=True,
        ))
        b = self.behavior()
        old_state, sm, records = self.wildcard_records(b, "GroundAttackCombo5")
        new_state = b.find_by_name("GroundAttackCombo6", "hkbStateMachine::StateInfo")[0]

        # State registered in the same state machine with a fresh stateId.
        self.assertIn(new_state, b.pointer_list(sm, "states"))
        new_state_id = b.get_value(new_state, "stateId")
        self.assertNotEqual(new_state_id, b.get_value(old_state, "stateId"))

        # Event name and info added at the same index.
        events = b.event_names()
        event_index = events.index("W_GroundAttackCombo6")
        self.assertEqual(len(events), len(b.array_items(b.array(b.graph_data, "eventInfos"))))

        # Wildcard transition: copy of the source's, pointed at the new event/state.
        def rec(r, name):
            el = r.find(f"field[@name='{name}']/*")
            return el.get("value") or el.get("id")

        source = next(r for r in records if rec(r, "toStateId") == str(b.get_value(old_state, "stateId")))
        new = [r for r in records if rec(r, "toStateId") == str(new_state_id)]
        self.assertEqual(len(new), 1)
        self.assertEqual(rec(new[0], "eventId"), str(event_index))
        for name in ("transition", "condition", "flags", "priority"):
            self.assertEqual(rec(new[0], name), rec(source, name), name)

        # Chain: StateInfo -> CMSG -> clip, CMSG holds only the new clip.
        chain = b.find_chains("a050_300050")[0]
        self.assertEqual(chain.state_info, new_state)
        self.assertEqual(b.name_of(chain.cmsg), "GroundAttackCombo6_CMSG")
        self.assertEqual(b.pointer_list(chain.cmsg, "generators"), [chain.clip])
        self.assertEqual(b.get_value(chain.cmsg, "animId"), 300050)
        paths = b.animation_paths()
        self.assertTrue(paths[b.get_value(chain.clip, "animationInternalId")].endswith("\\c0000\\hkx\\a050\\a050_300050.hkx"))

        # Text maps: entries added and Num kept in sync.
        for name, entry in (("eventnameid.txt", "W_GroundAttackCombo6"), ("statenameid.txt", "GroundAttackCombo6")):
            m = IdMap(self.path(name))
            self.assertIn(entry, m)
            num = next(line for line in m.lines if line.startswith("Num"))
            self.assertTrue(num.endswith(str(len(m.entries()))), num)

        # HKS: constant, table entry, functions.
        hks = HksScript(self.path(self.hks))
        self.assertIn("HKB_STATE_GROUND_ATTACK_COMBO_6", hks.constants())
        self.assertEqual(
            hks.table_entry("HKB_STATE_GROUND_ATTACK_COMBO_6"),
            "[HKB_STATE_GROUND_ATTACK_COMBO_6] = {1, 1, STYLE_TYPE_STAND, STATE_TYPE_ACTION_ATK}",
        )
        self.assertIn("UpdateState(HKB_STATE_GROUND_ATTACK_COMBO_6)", hks.text)

    def test_deep_chain_copies_path_and_prunes_selector(self):
        self.project.apply(Request(
            STATE, "a000_020202", "a000_020298", "a000_020298", new_name="AltHangMove", edit_hks=True,
        ))
        b = self.behavior()
        chain = b.find_chains("a000_020298")[0]
        names = [b.name_of(i) for i in chain.ids]
        self.assertEqual(names, [
            "AltHangMove", "AltHangMove Docking", "AltHangMove Selector-Dir", "AltHangMoveL_CMSG", "a000_020298",
        ])
        state, docking, selector, cmsg, clip = chain.ids
        # Only the copied branch; HangMoveR isn't brought along.
        self.assertEqual(b.pointer_list(selector, "generators"), [cmsg])
        self.assertEqual(b.get_value(selector, "selectedGeneratorIndex"), 0)
        # Binding sets and transition effect are shared with the original.
        old = b.find_chains("a000_020202")[0].ids
        self.assertEqual(b.get_value(docking, "variableBindingSet"), b.get_value(old[1], "variableBindingSet"))
        self.assertEqual(b.get_value(selector, "variableBindingSet"), b.get_value(old[2], "variableBindingSet"))
        self.assertEqual(
            b.get_value(selector, "generatorChangedTransitionEffect"),
            b.get_value(old[2], "generatorChangedTransitionEffect"),
        )
        # Data the old tool lost: float arrays, nested records, exact hex values.
        self.assertEqual(len(b.array_items(b.array(docking, "rotationOffset"))), 4)
        self.assertIsNotNone(b.field(selector, "sentOnClipEnd").find("record/field[@name='payload']"))
        self.assertEqual(b.field(state, "probability")[0].get("hex"), "#3ff0000000000000")
        # Original untouched.
        self.assertEqual(len(b.pointer_list(old[2], "generators")), 2)
        # New state's CMSG gets its own userData.
        self.assertNotEqual(b.get_value(cmsg, "userData"), b.get_value(old[3], "userData"))
        self.assertEqual(len(self.wildcard_records(b, "AltHangMove")[2]),
                         len(self.wildcard_records(b, "HangMove")[2]))

    def test_existing_state_name_is_rejected_and_nothing_written(self):
        before = {n: self.read(n) for n in os.listdir(self.dir) if n != "project.json"}
        with self.assertRaises(BehaviorError):
            self.project.apply(Request(STATE, "a050_300040", "a050_300050", "a050_300050", new_name="HangMove"))
        after = {n: self.read(n) for n in before}
        self.assertEqual(before, after)
        self.assertFalse(os.path.isdir(self.project.backup_dir))


class Branch(ProjectCase):
    def test_branch_joins_existing_selector(self):
        self.project.apply(Request(BRANCH, "a000_020202", "a000_020297", "a000_020297", new_name="HangMoveB"))
        b = self.behavior()
        selector = b.find_by_name("HangMove Selector-Dir")[0]
        gens = b.pointer_list(selector, "generators")
        self.assertEqual(len(gens), 3)
        new_cmsg = gens[-1]
        self.assertEqual(b.name_of(new_cmsg), "HangMoveB_CMSG")
        # Same state, so same userData as its siblings.
        self.assertEqual(b.get_value(new_cmsg, "userData"), b.get_value(gens[0], "userData"))
        self.assertEqual([b.name_of(g) for g in b.pointer_list(new_cmsg, "generators")], ["a000_020297"])
        # No new state or event.
        self.assertNotIn("W_HangMoveB", b.event_names())

    def test_branch_needs_a_selector(self):
        with self.assertRaises(BehaviorError):
            self.project.apply(Request(BRANCH, "a050_300040", "a050_300099", "a050_300099", new_name="X"))


class Variation(ProjectCase):
    def test_variation_appends_to_own_cmsg(self):
        self.project.apply(Request(VARIATION, "a050_300040", "a106_300040", "a106_300040"))
        b = self.behavior()
        cmsg = b.find_by_name("GroundAttackCombo5_CMSG")[0]
        self.assertEqual([b.name_of(g) for g in b.pointer_list(cmsg, "generators")], ["a050_300040", "a106_300040"])
        self.assertEqual(IdMap(self.path("eventnameid.txt")).to_bytes(), IdMap(os.path.join(TEMPLATE, "eventnameid.txt")).to_bytes())

    def test_same_animation_twice_is_rejected(self):
        with self.assertRaises(BehaviorError):
            self.project.apply(Request(VARIATION, "a050_300040", "a050_300040_b", "a050_300040"))

    def test_existing_animation_path_is_reused(self):
        b = Behavior(self.path(self.xml))
        before = len(b.animation_paths())
        self.project.apply(Request(VARIATION, "a050_300040", "a050_300040_copy", "a000_020202"))
        self.assertEqual(len(self.behavior().animation_paths()), before)


class Npc(ProjectCase):
    xml = "c9997.xml"
    hks = ""

    def test_npc_state_without_hks(self):
        self.project.apply(Request(
            STATE, "a000_013800_hkx_AutoSet_00", "a000_013810_hkx_AutoSet_00", "a000_013810", new_name="ThrowDef13810",
        ))
        b = self.behavior()
        chain = b.find_chains("a000_013810_hkx_AutoSet_00")[0]
        self.assertEqual(b.name_of(chain.state_info), "ThrowDef13810")
        self.assertTrue(b.animation_paths()[-1].endswith("\\c9997\\hkx\\a000\\a000_013810.hkx"))
        self.assertIn("W_ThrowDef13810", b.event_names())

    def test_hks_requested_without_hks_file(self):
        with self.assertRaises(ProjectError):
            self.project.apply(Request(STATE, "a000_013800_hkx_AutoSet_00", "x1", "a000_000001", new_name="Y", edit_hks=True))


class BatchAttacks(ProjectCase):
    xml = "c9997.xml"
    hks = ""

    def clips_of(self, b, state_name):
        state = b.find_by_name(state_name, "hkbStateMachine::StateInfo")[0]
        return sorted(b.name_of(c) for c in b.pointer_list(b.get_value(state, "generator"), "generators"))

    def test_fills_range_reuses_events_and_is_repeatable(self):
        before = self.behavior()
        events_before = before.event_names()
        _, sm, records_before = self.wildcard_records(before, "Attack3000")

        result = self.project.apply(AttackRange())
        self.assertTrue(result.written)
        b = self.behavior()
        for n in range(3000, 3110):
            self.assertTrue(b.find_by_name(f"Attack{n}", "hkbStateMachine::StateInfo"), n)
        # Missing state: copied from Attack3000 with both offsets, using the existing event.
        self.assertEqual(self.clips_of(b, "Attack3018"),
                         ["a000_003018_hkx_AutoSet_01", "a100_003018_hkx_AutoSet_01"])
        self.assertEqual(b.event_names(), events_before)
        _, _, records = self.wildcard_records(b, "Attack3018")
        self.assertEqual(len(records), len(records_before) + 64)
        # Existing state that only had a100 gets a000 too; its own clip is kept.
        self.assertIn("a100_003050_hkx_AutoSet_00", self.clips_of(b, "Attack3050"))
        self.assertIn("a000_003050_hkx_AutoSet_01", self.clips_of(b, "Attack3050"))
        # Windows line endings kept for every line.
        data = self.read(self.xml)
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))

        again = self.project.apply(AttackRange())
        self.assertEqual(again.written, [])

    def test_custom_offsets_and_range(self):
        self.project.apply(AttackRange(start=3018, end=3019, offsets=("a000", "a100", "a101")))
        b = self.behavior()
        self.assertEqual(self.clips_of(b, "Attack3019"), [
            "a000_003019_hkx_AutoSet_01", "a100_003019_hkx_AutoSet_01", "a101_003019_hkx_AutoSet_01",
        ])
        self.assertFalse(b.find_by_name("Attack3021", "hkbStateMachine::StateInfo"))

    def test_missing_source_state(self):
        with self.assertRaises(BehaviorError):
            self.project.apply(AttackRange(source=2999))

    def test_bad_offsets_are_rejected(self):
        with self.assertRaises(ProjectError):
            self.project.apply(AttackRange(offsets=("a000", "b100")))


class BindPlaybackSpeed(ProjectCase):
    xml = "c9997.xml"
    hks = ""

    def test_adds_variable_and_binds_every_attack_clip(self):
        before = self.behavior()
        self.assertNotIn("AnimationPlaybackSpeed", before.variable_names())
        result = self.project.apply(PlaybackSpeedBinding())
        self.assertTrue(result.written)
        b = self.behavior()
        index = b.variable_names().index("AnimationPlaybackSpeed")
        value_set = b.get_value(b.graph_data, "variableInitialValues")
        # Same four entries as the hand-made example: float, 0-999, starts at 1.0.
        self.assertEqual(len(b.array_items(b.array(b.graph_data, "variableInfos"))), index + 1)
        info = b.array_items(b.array(b.graph_data, "variableInfos"))[index]
        self.assertEqual(info.find("field[@name='type']/integer").get("value"), "4")
        bounds = b.array_items(b.array(b.graph_data, "variableBounds"))[index]
        self.assertEqual(bounds.find("field[@name='max']/record/field[@name='value']/integer").get("value"), "999")
        word = b.array_items(b.array(value_set, "wordVariableValues"))[index]
        self.assertEqual(word.find("field[@name='value']/integer").get("value"), "1065353216")

        bindings = set()
        for n in range(3000, 3110):
            for state in b.find_by_name(f"Attack{n}", "hkbStateMachine::StateInfo"):
                bindings |= {b.get_value(c, "variableBindingSet") for c in b.clips_under(state)}
        self.assertEqual(len(bindings), 1)
        (binding,) = bindings
        record = b.array_items(b.array(binding, "bindings"))[0]
        self.assertEqual(record.find("field[@name='memberPath']/string").get("value"), "playbackSpeed")
        self.assertEqual(record.find("field[@name='variableIndex']/integer").get("value"), str(index))
        # Clips outside the range are untouched.
        other = b.find_by_name("a000_013800_hkx_AutoSet_00")[0]
        self.assertEqual(b.get_value(other, "variableBindingSet"), "object0")

        self.assertEqual(self.project.apply(PlaybackSpeedBinding()).written, [])

    def test_attacks_added_later_inherit_the_binding(self):
        self.project.apply(PlaybackSpeedBinding())
        self.project.apply(AttackRange())
        self.assertEqual(self.project.apply(PlaybackSpeedBinding()).written, [])

    def test_clip_with_other_binding_is_left_alone(self):
        b = self.behavior()
        clip = b.find_by_name("a000_003001_hkx_AutoSet_01")[0]
        other = b.objects_of_type("hkbVariableBindingSet")[0]
        b.set_value(clip, "variableBindingSet", other)
        with open(self.path(self.xml), "wb") as f:
            f.write(b.to_bytes())
        result = self.project.apply(PlaybackSpeedBinding())
        self.assertTrue(any("WARNING" in line and "a000_003001_hkx_AutoSet_01" in line for line in result.log))
        self.assertEqual(self.behavior().get_value(clip, "variableBindingSet"), other)


class JumpHelpers:
    xml = "c9997.xml"
    hks = ""

    def state(self, b, n):
        found = b.find_by_name(f"JumpAttack{n}", "hkbStateMachine::StateInfo")
        return found[0] if found else None

    def own_transitions(self, b, n):
        own = b.get_value(self.state(b, n), "transitions")
        if own == "object0":
            return own, []
        events = b.event_names()
        return own, [(events[int(r.find("field[@name='eventId']/integer").get("value"))],
                      int(r.find("field[@name='toStateId']/integer").get("value")))
                     for r in b.array_items(b.array(own, "transitions"))]

    def clips(self, b, n):
        cmsg = b.get_value(self.state(b, n), "generator")
        return [(b.name_of(c), b.get_value(c, "mode")) for c in b.pointer_list(cmsg, "generators")]

    def assert_set_linked(self, b, base):
        own, records = self.own_transitions(b, base)
        loop_id = b.get_value(self.state(b, base + 1), "stateId")
        self.assertEqual(records, [(f"JumpAttack{base}_to_JumpAttack{base + 1}", loop_id)])
        return own


class JumpAttacks(JumpHelpers, ProjectCase):
    """3200-3292: 32X0 start → (own transition) → 32X1 loop, 32X2 landing; the fixture lacks 3260-3282."""

    fixture = "c9997_jump.xml"

    def test_single_duplicate_copies_whole_set(self):
        before = self.behavior()
        original_own = self.assert_set_linked(before, 3200)
        result = self.project.apply(Request(
            STATE, "a000_003200_hkx_AutoSet_00", "", "", new_name="JumpAttack3260", group=True,
        ))
        self.assertTrue(result.written)
        b = self.behavior()
        new_own = self.assert_set_linked(b, 3260)
        self.assertNotEqual(new_own, original_own, "the copy needs its own transition list")
        self.assertEqual(self.assert_set_linked(b, 3200), original_own)
        self.assertEqual(self.clips(b, 3261), [("a000_003261_hkx_AutoSet_00", 1)])  # still looping
        self.assertEqual(self.clips(b, 3262), [("a000_003262_hkx_AutoSet_00", 0)])
        machine = b.state_machine_of(self.state(b, 3200))
        for n in (3260, 3261, 3262):
            self.assertIn(self.state(b, n), b.pointer_list(machine, "states"))
        # Registered-but-unused events are reused, nothing is added.
        self.assertEqual(b.event_names(), before.event_names())

    def test_set_name_must_be_the_start_state(self):
        with self.assertRaises(ProjectError):
            self.project.apply(Request(STATE, "a000_003200_hkx_AutoSet_00", "", "", new_name="JumpAttack3261", group=True))

    def test_group_needs_a_jump_set(self):
        with self.assertRaises(ProjectError):
            self.project.apply(Request(STATE, "a000_003000_hkx_AutoSet_01", "", "", new_name="Attack3999", group=True))

    def test_batch_fills_missing_sets_and_offsets(self):
        result = self.project.apply(JumpAttackRange())
        self.assertTrue(result.written)
        b = self.behavior()
        for base in range(3200, 3300, 10):
            self.assert_set_linked(b, base)
            for k in range(3):
                offsets = sorted(name[:4] for name, _ in self.clips(b, base + k))
                self.assertEqual(offsets, ["a000", "a100"], base + k)
        self.assertEqual({mode for _, mode in self.clips(b, 3271)}, {1})
        self.assertIsNone(self.state(b, 3300))
        self.assertEqual(self.project.apply(JumpAttackRange()).written, [])

    def test_batch_needs_a_source_set(self):
        with self.assertRaises(BehaviorError):
            self.project.apply(JumpAttackRange(source=3260))


class JumpAttacksFromScratch(JumpHelpers, ProjectCase):
    """The stock c9997 has no jump attacks; the batch builds them from Attack3000."""

    def test_builds_jump_machine_and_all_sets(self):
        before = self.behavior()
        self.assertIsNone(self.state(before, 3200))
        result = self.project.apply(JumpAttackRange())
        self.assertTrue(result.written)
        b = self.behavior()
        holder = b.find_by_name("JumpAttack", "hkbStateMachine::StateInfo")[0]
        machine = b.get_value(holder, "generator")
        self.assertEqual(b.name_of(machine), "JumpAttack_SM")
        self.assertIn(holder, b.pointer_list(b.state_machine_of(holder), "states"))
        self.assertEqual(b.get_value(machine, "startStateId"), b.get_value(self.state(b, 3200), "stateId"))
        for base in range(3200, 3300, 10):
            self.assert_set_linked(b, base)
            for k in range(3):
                self.assertEqual(b.state_machine_of(self.state(b, base + k)), machine)
        # Jump-specific settings: start ends like the hand-made one, loop clips loop.
        start_cmsg = b.get_value(self.state(b, 3200), "generator")
        self.assertEqual(b.get_value(start_cmsg, "animeEndEventType"), 0)
        self.assertEqual({mode for _, mode in self.clips(b, 3201)}, {1})
        self.assertEqual({mode for _, mode in self.clips(b, 3202)}, {0})
        # Wildcard entries are global so the jump can start from outside JumpAttack_SM.
        wildcard = b.get_value(machine, "wildcardTransitions")
        flags = {r.find("field[@name='flags']/integer").get("value")
                 for r in b.array_items(b.array(wildcard, "transitions"))}
        self.assertEqual(flags, {"3584"})
        # The attacks it was built from are untouched.
        def attack_states(beh):
            attack = beh.find_by_name("Attack3000", "hkbStateMachine::StateInfo")[0]
            return len(beh.pointer_list(beh.state_machine_of(attack), "states"))
        self.assertEqual(attack_states(b), attack_states(before))
        self.assertEqual(self.project.apply(JumpAttackRange()).written, [])

    def test_built_set_can_be_duplicated(self):
        self.project.apply(JumpAttackRange(end=3202))
        self.project.apply(Request(STATE, "a000_003201_hkx_AutoSet_01", "", "", new_name="JumpAttack3290", group=True))
        self.assert_set_linked(self.behavior(), 3290)

    def test_needs_an_attack_to_build_from(self):
        with self.assertRaises(BehaviorError):
            self.project.apply(JumpAttackRange(attack_source="Attack9999"))


class Backups(ProjectCase):
    def test_restore_brings_files_back(self):
        original = self.read(self.xml)
        result = self.project.apply(Request(VARIATION, "a050_300040", "a106_300040", "a106_300040"))
        self.assertNotEqual(self.read(self.xml), original)
        self.project.restore(result.backup)
        self.assertEqual(self.read(self.xml), original)


if __name__ == "__main__":
    unittest.main()
