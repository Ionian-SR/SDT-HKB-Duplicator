"""Projects, previews, backups and the all-or-nothing apply step."""

import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

from batch import AttackRange, add_attack_range
from behavior import Behavior, BehaviorError
from hks_parser import HksError, HksScript
from id_maps import IdMap

VARIATION = "variation"
BRANCH = "branch"
STATE = "state"

FILE_KEYS = ("behavior_xml", "cmsg_script", "event_id_map", "state_id_map")
NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


class ProjectError(Exception):
    pass


@dataclass
class Request:
    mode: str
    source_clip: str
    clip_name: str
    animation_name: str
    chain_index: int = 0
    new_name: str = ""          # branch name (mode 2) or state name (mode 3)
    edit_hks: bool = False


@dataclass
class Result:
    log: list = field(default_factory=list)
    written: list = field(default_factory=list)
    backup: str = ""


class Project:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.name = data.get("project_name") or os.path.splitext(os.path.basename(path))[0]
        files = data.get("files", {})
        base = os.path.dirname(self.path)
        self.files = {}
        for key in FILE_KEYS:
            p = files.get(key) or ""
            self.files[key] = os.path.normpath(os.path.join(base, p)) if p else ""
        if not self.files["behavior_xml"]:
            raise ProjectError("The project has no behavior XML file.")
        self._behavior = None

    @staticmethod
    def create(path, name, behavior_xml, cmsg_script="", event_id_map="", state_id_map=""):
        data = {
            "project_name": name,
            "files": {
                "behavior_xml": behavior_xml,
                "cmsg_script": cmsg_script,
                "event_id_map": event_id_map,
                "state_id_map": state_id_map,
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return Project(path)

    @property
    def backup_dir(self):
        return os.path.join(os.path.dirname(self.path), "backups")

    def missing_files(self):
        return [k for k, p in self.files.items() if p and not os.path.isfile(p)]

    def behavior(self):
        """Read-only copy of the XML for browsing (clip list, chains)."""
        if self._behavior is None:
            self._behavior = Behavior(self.files["behavior_xml"])
        return self._behavior

    def character(self):
        """c0000, c9997, ... taken from the animation paths."""
        for path in self.behavior().animation_paths():
            m = re.search(r"\\chr\\(c\d{4})\\", path)
            if m:
                return m.group(1)
        return None

    # ------------------------------------------------------------- operations

    def _validate(self, req):
        problems = []
        for label, value in (("New clip name", req.clip_name), ("Animation name", req.animation_name)):
            if not value:
                problems.append(f"{label} is empty.")
            elif not NAME_RE.match(value):
                problems.append(f"{label} '{value}' should only use letters, numbers and _.")
        if req.mode in (BRANCH, STATE):
            label = "Branch name" if req.mode == BRANCH else "State name"
            if not req.new_name:
                problems.append(f"{label} is empty.")
            elif not NAME_RE.match(req.new_name):
                problems.append(f"{label} '{req.new_name}' should only use letters, numbers and _.")
        if req.mode == STATE and req.edit_hks and not self.files["cmsg_script"]:
            problems.append("Updating the HKS file was requested, but the project has no cmsg .hks file.")
        missing = self.missing_files()
        if missing:
            problems.append("Missing project files: " + ", ".join(self.files[k] for k in missing))
        if problems:
            raise ProjectError("\n".join(problems))

    def _register_names(self, states, log, outputs):
        """Add (state name, event name) pairs to statenameid/eventnameid where missing."""
        for key, index in (("event_id_map", 1), ("state_id_map", 0)):
            path = self.files[key]
            if not path:
                log.append(f"Skipped {key}: not set in the project.")
                continue
            id_map = IdMap(path)
            added, present = [], []
            for pair in states:
                name = pair[index]
                if name in id_map:
                    present.append(name)
                else:
                    added.append(f'{id_map.append(name)} = "{name}"')
            base = os.path.basename(path)
            if added:
                outputs[path] = id_map.to_bytes()
                log.append(f"{base}: added {', '.join(added)}.")
            if present:
                listed = ", ".join(present) if len(present) <= 3 else f"{len(present)} of them"
                log.append(f"{base} already has {listed}.")

    def _build_batch(self, spec):
        problems = spec.validate() + [
            "Missing project file: " + self.files[k] for k in self.missing_files()
        ]
        if problems:
            raise ProjectError("\n".join(problems))
        behavior = Behavior(self.files["behavior_xml"])
        log, new_states, changed = add_attack_range(behavior, spec)
        outputs = {}
        if new_states:
            self._register_names(new_states, log, outputs)
        if changed:
            outputs[self.files["behavior_xml"]] = behavior.to_bytes()
        return log, outputs

    def _build(self, req):
        """Run the request on fresh in-memory copies. Returns (log, {path: bytes})."""
        if isinstance(req, AttackRange):
            return self._build_batch(req)
        self._validate(req)
        behavior = Behavior(self.files["behavior_xml"])
        chains = behavior.find_chains(req.source_clip)
        if not 0 <= req.chain_index < len(chains):
            raise ProjectError("Pick which state the clip should be copied from.")
        chain = chains[req.chain_index]
        log = [f"Source: {chain.describe()}"]
        outputs = {}

        if req.mode == VARIATION:
            result = behavior.add_variation(chain, req.clip_name, req.animation_name)
        elif req.mode == BRANCH:
            result = behavior.add_branch(chain, req.new_name, req.clip_name, req.animation_name)
        elif req.mode == STATE:
            result = behavior.add_state(chain, req.new_name, req.clip_name, req.animation_name)
        else:
            raise ProjectError(f"Unknown mode {req.mode}")
        log += result["log"]
        if "branch_index" in result:
            log.append(
                f"NOTE: the selector picks branches by index; make your HKS set it to "
                f"{result['branch_index']} to play {req.new_name}."
            )

        if req.mode == STATE:
            self._register_names([(req.new_name, result["event_name"])], log, outputs)
            if req.edit_hks:
                hks = HksScript(self.files["cmsg_script"])
                log += hks.add_state(req.new_name, result["source_state_name"])
                outputs[self.files["cmsg_script"]] = hks.to_bytes()
            else:
                log.append("HKS file not changed (update HKS was off).")

        outputs[self.files["behavior_xml"]] = behavior.to_bytes()
        return log, outputs

    def preview(self, req):
        log, outputs = self._build(req)
        files = ", ".join(os.path.basename(p) for p in outputs)
        return log + [f"Will write: {files}" if outputs else "Nothing to change."]

    def apply(self, req):
        log, outputs = self._build(req)
        if not outputs:
            return Result(log=log + ["Nothing to change; no files written."])
        backup = self.backup(list(outputs))
        for path, data in outputs.items():
            _atomic_write(path, data)
        self._behavior = None
        return Result(log=log, written=list(outputs), backup=backup)

    # ---------------------------------------------------------------- backups

    def backup(self, paths=None):
        paths = [p for p in (paths or self.files.values()) if p and os.path.isfile(p)]
        os.makedirs(self.backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", self.name)
        zip_path = os.path.join(self.backup_dir, f"{safe}_backup_{stamp}.zip")
        n = 1
        while os.path.exists(zip_path):
            n += 1
            zip_path = os.path.join(self.backup_dir, f"{safe}_backup_{stamp}_{n}.zip")
        manifest = {}
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for i, p in enumerate(paths):
                arcname = f"{i}_{os.path.basename(p)}"
                z.write(p, arcname=arcname)
                manifest[arcname] = p
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
        return zip_path

    def backups(self):
        if not os.path.isdir(self.backup_dir):
            return []
        zips = [os.path.join(self.backup_dir, f) for f in os.listdir(self.backup_dir) if f.endswith(".zip")]
        return sorted(zips, key=os.path.getmtime, reverse=True)

    def restore(self, zip_path):
        with zipfile.ZipFile(zip_path) as z:
            if "manifest.json" not in z.namelist():
                raise ProjectError("This backup was made by an older version and has no file list; unzip it manually.")
            manifest = json.loads(z.read("manifest.json"))
            for arcname, target in manifest.items():
                _atomic_write(target, z.read(arcname))
        self._behavior = None
        return list(manifest.values())


def _atomic_write(path, data):
    """Write to a temp file next to ``path`` then swap it in, so a crash never leaves half a file."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=os.path.basename(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def friendly_error(exc):
    if isinstance(exc, (BehaviorError, HksError, ProjectError)):
        return str(exc)
    return f"Unexpected error ({type(exc).__name__}): {exc}"
