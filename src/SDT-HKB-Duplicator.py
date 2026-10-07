"""SDT HKB Duplicator - desktop UI."""

import json
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from batch import AttackRange
from project import BRANCH, STATE, VARIATION, Project, Request, friendly_error

APP_TITLE = "SDT HKB Duplicator"
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".sdt_hkb_duplicator.json")

MODES = {
    VARIATION: (
        "Add a variation",
        "Adds the new clip to the same CMSG, next to the original. Use a different aXXX offset "
        "(e.g. a105_316020 → a106_316020) so the game can tell them apart.",
    ),
    BRANCH: (
        "Add a branch to the selector",
        "Adds a new CMSG + clip next to the existing ones in the selector above it "
        "(e.g. HangMoveB next to HangMoveL/HangMoveR). No new state or event.",
    ),
    STATE: (
        "Create a new state",
        "Copies the whole state into a brand-new one with its own event (W_<name>), "
        "wildcard transition and HKS entries. Other selector branches aren't copied.",
    ),
}


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


class NewProjectDialog(tk.Toplevel):
    FIELDS = (
        ("behavior_xml", "Behavior XML (c0000.xml or c9997.xml)", [("XML files", "*.xml")], True),
        ("cmsg_script", "c0000_cmsg.hks (player projects only)", [("HKS/Lua files", "*.hks *.lua")], False),
        ("event_id_map", "eventnameid.txt", [("Text files", "*.txt")], False),
        ("state_id_map", "statenameid.txt", [("Text files", "*.txt")], False),
    )

    def __init__(self, parent):
        super().__init__(parent)
        self.title("New Project")
        self.transient(parent)
        self.resizable(True, False)
        self.result = None
        self.vars = {key: tk.StringVar() for key, *_ in self.FIELDS}
        self.name_var = tk.StringVar()

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Project name").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(frame, textvariable=self.name_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=3)
        for row, (key, label, types, _) in enumerate(self.FIELDS, start=1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
            ttk.Entry(frame, textvariable=self.vars[key], width=50).grid(row=row, column=1, sticky="ew", pady=3)
            ttk.Button(frame, text="Browse…", command=lambda k=key, t=types: self.browse(k, t)).grid(
                row=row, column=2, padx=(6, 0)
            )
        ttk.Label(
            frame, foreground="gray", wraplength=520, justify="left",
            text="Use a separate project per character. The .hks and .txt files are in the action folder "
                 "and are usually the same for every project. NPC (c9997) projects don't need the .hks.",
        ).grid(row=len(self.FIELDS) + 1, column=0, columnspan=3, sticky="w", pady=(8, 4))
        buttons = ttk.Frame(frame)
        buttons.grid(row=len(self.FIELDS) + 2, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Save project…", command=self.save).pack(side="right", padx=6)
        self.grab_set()

    def browse(self, key, types):
        path = filedialog.askopenfilename(parent=self, filetypes=types + [("All files", "*.*")])
        if path:
            self.vars[key].set(path)
            if key == "behavior_xml" and not self.name_var.get():
                self.name_var.set(os.path.splitext(os.path.basename(path))[0])

    def save(self):
        files = {k: v.get().strip() for k, v in self.vars.items()}
        if not files["behavior_xml"]:
            messagebox.showerror("Missing file", "Pick the behavior XML file.", parent=self)
            return
        missing = [p for p in files.values() if p and not os.path.isfile(p)]
        if missing:
            messagebox.showerror("File not found", "\n".join(missing), parent=self)
            return
        name = self.name_var.get().strip() or "SDT-BEH-Project"
        path = filedialog.asksaveasfilename(
            parent=self, title="Save project file", defaultextension=".json",
            filetypes=[("Project files", "*.json")], initialfile=f"{name}.json",
        )
        if not path:
            return
        try:
            self.result = Project.create(path, name, **files)
        except Exception as e:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Couldn't create project", friendly_error(e), parent=self)
            return
        self.destroy()


class BatchDialog(tk.Toplevel):
    """NPC attacks: copy Attack3000 into every missing Attack3000-3109, with each offset."""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Batch: NPC Attacks")
        self.transient(app.root)
        self.resizable(False, False)
        defaults = AttackRange()
        self.source_var = tk.StringVar(value=f"{defaults.prefix}{defaults.source}")
        self.start_var = tk.StringVar(value=str(defaults.start))
        self.end_var = tk.StringVar(value=str(defaults.end))
        self.offsets_var = tk.StringVar(value=", ".join(defaults.offsets))

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame, wraplength=440, justify="left",
            text="Adds every missing attack state in the range by copying the source state, and adds any "
                 "missing offsets to the ones that already exist. Safe to run again: anything already "
                 "there is left alone. Events and .txt entries are reused when they already exist.",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        ttk.Label(frame, text="Copy from state").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(frame, textvariable=self.source_var, width=16).grid(row=1, column=1, columnspan=3, sticky="w")
        ttk.Label(frame, text="Numbers").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(frame, textvariable=self.start_var, width=7).grid(row=2, column=1, sticky="w")
        ttk.Label(frame, text="to").grid(row=2, column=2, padx=4)
        ttk.Entry(frame, textvariable=self.end_var, width=7).grid(row=2, column=3, sticky="w")
        ttk.Label(frame, text="Offsets").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(frame, textvariable=self.offsets_var, width=24).grid(row=3, column=1, columnspan=3, sticky="w")
        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=4, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Run", command=lambda: self.app.run_batch(self.spec(), apply=True)).pack(
            side="right", padx=6
        )
        ttk.Button(buttons, text="Preview", command=lambda: self.app.run_batch(self.spec(), apply=False)).pack(
            side="right"
        )

    def spec(self):
        m = re.match(r"^\s*([A-Za-z_]+)(\d+)\s*$", self.source_var.get())
        try:
            start, end = int(self.start_var.get()), int(self.end_var.get())
        except ValueError:
            start = end = None
        if not m or start is None:
            messagebox.showerror("Batch", "Use a state like Attack3000 and whole numbers for the range.", parent=self)
            return None
        offsets = tuple(o for o in re.split(r"[\s,]+", self.offsets_var.get().strip()) if o)
        return AttackRange(prefix=m.group(1), source=int(m.group(2)), start=start, end=end, offsets=offsets)


class App:
    def __init__(self, root):
        self.root = root
        self.project = None
        self.chains = []
        self.settings = load_settings()
        self._anim_edited = False
        self._last_source = ""
        self._chains_for = None

        root.title(APP_TITLE)
        root.geometry("820x800")
        root.minsize(700, 600)
        try:
            root.iconbitmap(resource_path("favicon.ico"))
        except tk.TclError:
            pass

        outer = ttk.Frame(root, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)

        # ---- project bar
        bar = ttk.Frame(outer)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self.project_label = ttk.Label(bar, text="No project open", font=("TkDefaultFont", 10, "bold"))
        self.project_label.grid(row=0, column=0, sticky="w")
        ttk.Button(bar, text="New Project…", command=self.new_project).grid(row=0, column=1, padx=3)
        ttk.Button(bar, text="Open Project…", command=self.open_project_dialog).grid(row=0, column=2, padx=3)
        ttk.Button(bar, text="Batch: NPC Attacks…", command=self.open_batch).grid(row=0, column=3, padx=3)
        ttk.Button(bar, text="Restore Backup…", command=self.restore_backup).grid(row=0, column=4, padx=3)

        # ---- step 1: source
        step1 = ttk.LabelFrame(outer, text=" 1. Pick the clip to copy ", padding=8)
        step1.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        step1.columnconfigure(1, weight=1)
        ttk.Label(step1, text="ClipGen name").grid(row=0, column=0, sticky="w")
        self.source_var = tk.StringVar()
        self.source_box = ttk.Combobox(step1, textvariable=self.source_var)
        self.source_box.grid(row=0, column=1, sticky="ew", padx=6)
        self.source_box.bind("<KeyRelease>", self.filter_sources)
        self.source_box.bind("<<ComboboxSelected>>", lambda e: self.source_changed())
        self.source_box.bind("<Return>", lambda e: self.source_changed())
        self.source_box.bind("<FocusOut>", lambda e: self.source_changed())
        self.chain_label = ttk.Label(step1, text="Used in")
        self.chain_label.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.chain_var = tk.StringVar()
        self.chain_box = ttk.Combobox(step1, textvariable=self.chain_var, state="readonly")
        self.chain_box.grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        self.chain_box.bind("<<ComboboxSelected>>", lambda e: self.chain_changed())
        self.source_hint = ttk.Label(
            step1, foreground="gray", wraplength=740, justify="left",
            text="Type part of a name (e.g. a050_300040 or a000_013800) to search. "
                 "This is usually the animation ID from DS Anim Studio.",
        )
        self.source_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.show_chain_picker(False)

        # ---- step 2: mode
        step2 = ttk.LabelFrame(outer, text=" 2. What do you want to add? ", padding=8)
        step2.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        step2.columnconfigure(0, weight=1)
        self.mode_var = tk.StringVar(value=STATE)
        self.mode_buttons = {}
        self.mode_notes = {}
        for i, (mode, (title, desc)) in enumerate(MODES.items()):
            rb = ttk.Radiobutton(step2, text=title, value=mode, variable=self.mode_var, command=self.mode_changed)
            rb.grid(row=i * 2, column=0, sticky="w", pady=(4 if i else 0, 0))
            note = ttk.Label(step2, text=desc, foreground="gray", wraplength=740, justify="left")
            note.grid(row=i * 2 + 1, column=0, sticky="w", padx=(22, 0))
            self.mode_buttons[mode] = rb
            self.mode_notes[mode] = (note, desc)

        # ---- step 3: names
        step3 = ttk.LabelFrame(outer, text=" 3. Name the new pieces ", padding=8)
        step3.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        step3.columnconfigure(1, weight=1)
        self.new_name_label = ttk.Label(step3, text="New state name")
        self.new_name_label.grid(row=0, column=0, sticky="w", pady=2)
        self.new_name_var = tk.StringVar()
        self.new_name_entry = ttk.Entry(step3, textvariable=self.new_name_var)
        self.new_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        ttk.Label(step3, text="New ClipGen name").grid(row=1, column=0, sticky="w", pady=2)
        self.clip_var = tk.StringVar()
        self.clip_var.trace_add("write", lambda *a: self.clip_name_changed())
        ttk.Entry(step3, textvariable=self.clip_var).grid(row=1, column=1, sticky="ew", padx=6, pady=2)
        ttk.Label(step3, text="New animationName").grid(row=2, column=0, sticky="w", pady=2)
        self.anim_var = tk.StringVar()
        anim_entry = ttk.Entry(step3, textvariable=self.anim_var)
        anim_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=2)
        anim_entry.bind("<Key>", lambda e: setattr(self, "_anim_edited", True))
        self.hks_var = tk.BooleanVar(value=True)
        self.hks_check = ttk.Checkbutton(step3, text="Also update c0000_cmsg.hks (player only)", variable=self.hks_var)
        self.hks_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.names_hint = ttk.Label(step3, foreground="gray", wraplength=740, justify="left")
        self.names_hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # ---- actions
        actions = ttk.Frame(outer)
        actions.grid(row=4, column=0, sticky="ew", pady=10)
        self.apply_button = ttk.Button(actions, text="Apply", command=self.apply)
        self.apply_button.pack(side="right")
        ttk.Button(actions, text="Preview", command=self.preview).pack(side="right", padx=6)

        # ---- log
        log_frame = ttk.LabelFrame(outer, text=" Log ", padding=4)
        log_frame.grid(row=5, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)
        self.log.tag_configure("error", foreground="#c0392b")
        self.log.tag_configure("warn", foreground="#b9770e")
        self.log.tag_configure("ok", foreground="#1e8449")
        self.log.tag_configure("head", font=("TkDefaultFont", 9, "bold"))

        self.all_clips = []
        self.mode_changed()
        last = self.settings.get("last_project")
        if last and os.path.isfile(last):
            self.open_project(last, quiet=True)

    # ------------------------------------------------------------------ helpers

    def write_log(self, lines, tag=None, heading=None):
        self.log.configure(state="normal")
        if heading:
            self.log.insert("end", heading + "\n", "head")
        for line in lines:
            line_tag = tag
            if line_tag is None:
                if "WARNING" in line:
                    line_tag = "warn"
                elif line.startswith("ERROR"):
                    line_tag = "error"
            self.log.insert("end", line + "\n", line_tag or ())
        self.log.insert("end", "\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    def busy(self, on):
        self.root.config(cursor="watch" if on else "")
        self.root.update_idletasks()

    # ------------------------------------------------------------------ project

    def new_project(self):
        dialog = NewProjectDialog(self.root)
        self.root.wait_window(dialog)
        if dialog.result:
            self.open_project(dialog.result.path)

    def open_project_dialog(self):
        path = filedialog.askopenfilename(title="Open project", filetypes=[("Project files", "*.json")])
        if path:
            self.open_project(path)

    def open_project(self, path, quiet=False):
        self.busy(True)
        try:
            project = Project(path)
            missing = project.missing_files()
            if missing:
                raise FileNotFoundError(
                    "These project files are missing:\n" + "\n".join(project.files[k] for k in missing)
                )
            clips = project.behavior().clip_names()
            character = project.character() or "unknown character"
        except Exception as e:  # noqa: BLE001 - shown to the user
            self.busy(False)
            if not quiet:
                messagebox.showerror("Couldn't open project", friendly_error(e))
            self.write_log([f"ERROR: couldn't open {path}: {friendly_error(e)}"])
            return
        self.busy(False)
        self.project = project
        self.all_clips = clips
        self.source_box["values"] = clips
        self.project_label.config(text=f"{project.name}  ({character}, {len(clips)} clips)")
        has_hks = bool(project.files["cmsg_script"])
        self.hks_var.set(has_hks and character == "c0000")
        self.hks_check.config(state="normal" if has_hks else "disabled")
        self.settings["last_project"] = project.path
        save_settings(self.settings)
        lines = [f"{k}: {v or '(not set)'}" for k, v in project.files.items()]
        self.write_log(lines, heading=f"Opened project {project.name}")
        self.source_changed(force=True)

    # ------------------------------------------------------------------ step 1

    def filter_sources(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        text = self.source_var.get().lower()
        matches = [c for c in self.all_clips if text in c.lower()] if text else self.all_clips
        self.source_box["values"] = matches[:500]

    def show_chain_picker(self, show):
        for widget in (self.chain_label, self.chain_box):
            widget.grid() if show else widget.grid_remove()

    def source_changed(self, force=False):
        name = self.source_var.get().strip()
        if name == self._chains_for and not force:
            return
        self._chains_for = name
        self.chains = []
        self.chain_box["values"] = []
        self.chain_var.set("")
        self.show_chain_picker(False)
        if self.project and name:
            try:
                self.chains = self.project.behavior().find_chains(name)
            except Exception as e:  # noqa: BLE001 - shown to the user
                self.source_hint.config(text=friendly_error(e), foreground="#c0392b")
            else:
                self.chain_box["values"] = [c.describe(types=False) for c in self.chains]
                self.chain_box.current(0)
                self.show_chain_picker(len(self.chains) > 1)
                if name != self._last_source:
                    self.clip_var.set(name)
                    self._anim_edited = False
                    self.clip_name_changed()
                self._last_source = name
        self.chain_changed()

    def chain_changed(self):
        chain = self.current_chain()
        if chain is not None:
            prefix = f"Used in {len(self.chains)} places, pick one above. " if len(self.chains) > 1 else ""
            self.source_hint.config(text=f"{prefix}Path: {chain.describe(types=False)}", foreground="gray")
        available = {
            VARIATION: (chain is not None and chain.cmsg is not None, "Not available: the clip isn't directly inside a CMSG."),
            BRANCH: (chain is not None and chain.branch_selector is not None,
                     "Not available: there's no selector above this clip's CMSG."),
            STATE: (chain is not None, ""),
        }
        for mode, (ok, reason) in available.items():
            note, desc = self.mode_notes[mode]
            self.mode_buttons[mode].config(state="normal" if ok or chain is None else "disabled")
            note.config(text=desc if ok or chain is None else reason)
        if chain is not None and not available[self.mode_var.get()][0]:
            self.mode_var.set(STATE)
        self.mode_changed()

    def current_chain(self):
        if not self.chains:
            return None
        index = self.chain_box.current()
        return self.chains[index if index >= 0 else 0]

    # ------------------------------------------------------------------ step 2/3

    def mode_changed(self):
        mode = self.mode_var.get()
        chain = self.current_chain()
        b = self.project.behavior() if (self.project and chain) else None
        if mode == VARIATION:
            self.new_name_label.config(text="(not needed)")
            self.new_name_entry.config(state="disabled")
            target = b.name_of(chain.cmsg) if b and chain.cmsg else "the CMSG"
            hint = f"The new clip is added to {target}. Change the aXXX offset, e.g. a050_300040 → a106_300040."
        elif mode == BRANCH:
            self.new_name_label.config(text="New branch name")
            self.new_name_entry.config(state="normal")
            target = b.name_of(chain.branch_selector) if b and chain.branch_selector else "the selector"
            hint = (f"Creates <branch name>_CMSG inside {target}, e.g. HangMoveB → HangMoveB_CMSG. "
                    "The log tells you which selector index to use in HKS.")
        else:
            self.new_name_label.config(text="New state name")
            self.new_name_entry.config(state="normal")
            old = b.name_of(chain.state_info) if b else "the original state"
            hint = (f"Copies {old} under the new name; copied objects are renamed by swapping "
                    f"'{old}' for the new name (e.g. HangMove → AltHangMove, HangMoveL_CMSG → AltHangMoveL_CMSG). "
                    "To add to an existing state instead, use variation or branch.")
        self.hks_check.grid() if mode == STATE else self.hks_check.grid_remove()
        self.names_hint.config(text=hint)

    def clip_name_changed(self):
        if self._anim_edited:
            return
        m = re.match(r"(a\d+_\d+)", self.clip_var.get().strip())
        self.anim_var.set(m.group(1) if m else "")

    # ------------------------------------------------------------------ actions

    def build_request(self):
        if not self.project:
            raise ValueError("Open or create a project first.")
        if not self.chains:
            raise ValueError("Pick an existing ClipGen to copy in step 1.")
        source = self.source_var.get().strip()
        clip = self.clip_var.get().strip()
        if clip == source:
            raise ValueError("The new ClipGen name is the same as the original. Change the ID or offset.")
        mode = self.mode_var.get()
        return Request(
            mode=mode,
            source_clip=source,
            chain_index=max(self.chain_box.current(), 0),
            clip_name=clip,
            animation_name=self.anim_var.get().strip(),
            new_name=self.new_name_var.get().strip() if mode != VARIATION else "",
            edit_hks=bool(self.hks_var.get()) and mode == STATE,
        )

    def preview(self):
        try:
            req = self.build_request()
            self.busy(True)
            lines = self.project.preview(req)
        except Exception as e:  # noqa: BLE001 - shown to the user
            self.busy(False)
            self.write_log([f"ERROR: {friendly_error(e)}"], heading="Preview")
            return
        self.busy(False)
        self.write_log(lines, heading="Preview (nothing written yet)")

    def apply(self):
        try:
            req = self.build_request()
        except Exception as e:  # noqa: BLE001
            self.write_log([f"ERROR: {friendly_error(e)}"])
            return
        if not messagebox.askyesno(APP_TITLE, "Write these changes to your files?\nA backup is made first."):
            return
        try:
            self.busy(True)
            result = self.project.apply(req)
        except Exception as e:  # noqa: BLE001 - shown to the user
            self.busy(False)
            self.write_log([f"ERROR: {friendly_error(e)}", "Nothing was written."], heading="Apply failed")
            messagebox.showerror(APP_TITLE, friendly_error(e))
            return
        self.busy(False)
        self.write_log(result.log, heading="Applied")
        self.write_log([f"Backup saved: {result.backup}"] + [f"Wrote {p}" for p in result.written], tag="ok")
        self.write_log(self.next_steps(req), heading="Next steps")
        self.all_clips = self.project.behavior().clip_names()
        self.source_box["values"] = self.all_clips
        self.source_changed(force=True)

    def open_batch(self):
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Open a project first.")
            return
        BatchDialog(self)

    def run_batch(self, spec, apply):
        if spec is None:
            return
        if apply and not messagebox.askyesno(
            APP_TITLE, f"Run {spec.describe()} and write the changes?\nA backup is made first."
        ):
            return
        heading = "Batch" if apply else "Batch preview (nothing written yet)"
        try:
            self.busy(True)
            if apply:
                result = self.project.apply(spec)
            else:
                lines = self.project.preview(spec)
        except Exception as e:  # noqa: BLE001 - shown to the user
            self.busy(False)
            self.write_log([f"ERROR: {friendly_error(e)}", "Nothing was written."], heading=heading)
            messagebox.showerror(APP_TITLE, friendly_error(e))
            return
        self.busy(False)
        if not apply:
            self.write_log(lines, heading=heading)
            return
        self.write_log(result.log, heading=heading)
        if result.written:
            self.write_log([f"Backup saved: {result.backup}"] + [f"Wrote {p}" for p in result.written], tag="ok")
            self.write_log(
                ["• Add the new animations to the character's .anibnd (only the ones the enemy really has).",
                 "• Convert the XML back to .hkx and repack the behbnd."],
                heading="Next steps",
            )
            self.all_clips = self.project.behavior().clip_names()
            self.source_box["values"] = self.all_clips

    def next_steps(self, req):
        steps = ["Add the animation to the character's .anibnd.", "Convert the XML back to .hkx and repack the behbnd."]
        if req.mode == STATE:
            steps.insert(0, f'Fire it from HKS with FireEvent("W_{req.new_name}") (e.g. in c0000_transition.hks or c9997.hks).')
        if req.mode == BRANCH:
            steps.insert(0, "Set the selector's index variable in HKS to play the new branch.")
        return [f"• {s}" for s in steps]

    def restore_backup(self):
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Open a project first.")
            return
        backups = self.project.backups()
        if not backups:
            messagebox.showinfo(APP_TITLE, "This project has no backups yet.")
            return
        path = filedialog.askopenfilename(
            title="Pick a backup to restore", initialdir=self.project.backup_dir,
            filetypes=[("Backups", "*.zip")],
        )
        if not path or not messagebox.askyesno(
            APP_TITLE, f"Restore {os.path.basename(path)}?\nThis overwrites the current project files."
        ):
            return
        try:
            restored = self.project.restore(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, friendly_error(e))
            return
        self.write_log([f"Restored {p}" for p in restored], tag="ok", heading=f"Restored {os.path.basename(path)}")
        self.open_project(self.project.path, quiet=True)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
