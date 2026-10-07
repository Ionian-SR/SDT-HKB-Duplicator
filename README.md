# SDT HKB Duplicator
This is a tool that automates a majority of the process to add new havok behavior entries in c9997 or c0000.xml files. It also edits the .txt files and hks files associated for adding new events.

- **c0000** is the player. It has the more complicated behavior and uses `c0000_cmsg.hks`.
- **c9997** is the generic NPC.

## Before using this tool
### How to convert hkx to xml
- Make sure to unpack a character's BehBND file, and convert the c9997 or c0000 hkx files into xml. You can download a tool from ?ServerName? discord to perform this: https://discord.com/channels/529802828278005773/529900741998149643/1322128333642924032
### Creating a project
- Click **New Project…** and fill in:
  - Project name
  - c0000.xml or c9997.xml
  - c0000_cmsg.hks (player projects only; NPC projects can leave it empty)
  - eventnameid.txt
  - statenameid.txt
- You should create different projects for different characters, but you will always choose the same c0000_cmsg.hks, eventnameid.txt, statenameid.txt. These files will be located under the action folder.
- The last project you opened is reopened automatically next time.
### Helpful resources
- Refer to Igor's Havok behavior doc editing guide if you want to know how to manually edit the files: https://docs.google.com/document/d/1LEpQDeyv6rCAjM1eKZ1K0kF9Ux-d7Vc81jTFEJHQwuw/edit?tab=t.0#heading=h.gjdgxs

## Usage
1. **Pick the clip to copy.** Start typing a ClipGen name and pick it from the list. This is usually the animation ID found in DS Animation Studio, but it is not always the case. If you want a prosthetic attack, choose an animation ID that is considered a prosthetic attack. Same with Throws, Mid-air, and other special states.
   - *Examples*
     - `a000_013800_hkx_AutoSet_00`: what an NPC ClipGen name looks like (NPC names often have extra text after the ID).
     - `a050_300040`: a Ground Attack of the PC.
   - The tool shows the path from the state down to the clip, e.g. `HangMove → HangMove Docking → HangMove Selector-Dir → HangMoveL_CMSG → a000_020202`. If the clip is used in more than one place, a **Used in** list appears so you can pick which one.
2. **Pick what you want to add.** Options that don't fit the clip are greyed out.

   | Option | What it creates | Example |
   |---|---|---|
   | **Add a variation** | A new clip in the same CMSG | `a105_316020` → `a106_316020` (3rd Mortal Draw attack in `GroundSpecialAttackCombo3`) |
   | **Add a branch to the selector** | A new CMSG + clip next to the existing ones in the selector | `HangMoveB_CMSG` next to `HangMoveL_CMSG`/`HangMoveR_CMSG` |
   | **Create a new state** | A copy of the whole state, with its own event `W_<name>`, wildcard transition, `.txt` entries and HKS entries | `AltHangMove` from `HangMove`, `GroundAttackCombo6` from `GroundAttackCombo5` |

3. **Name the new pieces.**
   - **New ClipGen name**: ideally just increment the original ID in some way, e.g. `a000_013810_hkx_AutoSet_00` or `a050_300050`.
   - **New animationName** is filled in from the ClipGen name (e.g. `a000_013810`). Change it if it differs.
   - **New CMSG name** (branch only): filled in from the source CMSG. Change it the way its siblings differ, e.g. `GroundSpecialAttackHoldMove_F_CMSG_Motion` → `GroundSpecialAttackHoldMove_FL_CMSG_Motion`.
   - **New state name** (new state only): this names the event, state, CMSG and HKS functions. Copied objects are renamed by swapping the old state name for the new one (`HangMove Docking` → `AltHangMove Docking`, `HangMoveL_CMSG` → `AltHangMoveL_CMSG`).
   - **Also update c0000_cmsg.hks**: on by default for c0000 projects.
4. Click **Preview** to see exactly what will change. Nothing is written yet.
5. Click **Apply**. A backup is made first, then all files are written together. If anything goes wrong, nothing is written.

## How each option works
### Layered states (_Motion / _Anime)
Some states, like `GroundSpecialAttackHoldMove` or `StandMoveLoop`, play two layers at once (usually `_Motion` and `_Anime`). Each layer has its own selector, and both selectors are driven by the same variable. The tool detects this and makes **the same change in every matching layer**, so the selectors stay lined up:
- Name things for the layer you picked (e.g. `a106_316511_Motion`, `GroundSpecialAttackHoldMove_FL_CMSG_Motion`). The other layer's names are worked out the same way its existing names differ (`_Motion` → `_Anime`).
- The matching layer is shown under the path in step 1, and the preview lists everything created in each layer.

### Add a variation
- The new clip goes into the *same* CMSG as the clip you picked, so you can no longer add a variation to the wrong state by accident.
- Make sure to change the aXXX offset. The tool refuses if the CMSG already plays that exact animation. It would also be ideal to follow Fromsoft's naming convention, rather than choose a random ID.

### Add a branch to the selector
- Only available when the clip's CMSG sits inside a selector (e.g. `HangMove Selector-Dir`).
- The new CMSG shares the state's `userData`, like its siblings do.
- The log tells you the new branch's index in the selector. Your HKS has to set the selector's variable to that index to play it.

### Create a new state
- The whole path from the state down to the clip is copied. Works for deep chains such as `StateInfo → Docking → Selector → CMSG → Clip`.
- Selectors in the copy keep **only** the branch you picked (e.g. `AltHangMove` gets `AltHangMoveL` but not a copy of `HangMoveR`). Add more branches later with **Add a branch**.
- Variable binding sets and transition effects are **shared** with the original, not copied.
- The wildcard transition is copied from the original state's (same blend, flags and intervals), pointing at the new event and state.
- HKS: adds the `HKB_STATE_` constant, a `g_paramHkbState` entry copied from the original, and `_onUpdate`/`_onActivate`/`_onDeactivate` functions copied from the original's.
- `eventnameid.txt` / `statenameid.txt`: adds `W_<name>` / `<name>` and updates the `Num` count at the top.

## After running this tool
- This tool updates the cmsg_hks file for c0000 edits, but will **NOT** do anything for c9997 edits. You will have to modify c9997.hks yourself if you want to add a new event for NPCs to use.
- You still need to add the animation to the .anibnd file for both c9997 and c0000.
- When creating a new state for c0000, you still need to modify the c0000_transition.hks to call the new animation. Don't forget that the new animation event in hks will have a "W_" before the stateinfo name. Example: FireEvent("W_GroundSpecialAttackCombo3")
- The game instantly crashing or NPCs refusing to perform the event are indicators where something went wrong during the process.
- If something does not work, click **Restore Backup…**. Backups are zip files in the `backups` folder next to your project file.

## Running from source
```
pip install -r requirements.txt
python src/SDT-HKB-Duplicator.py
```

### Building the exe
```
pip install pyinstaller
cd src
pyinstaller --onefile --windowed --icon favicon.ico --add-data "favicon.ico;." SDT-HKB-Duplicator.py
```

### Tests
The tests run every option against the files in `src/template` and check the results, including that unchanged files are saved byte-for-byte identical.
```
python -m unittest discover tests
```

## Things I want to add in future updates
- Maybe add automated c9997.hks edits.
- Integrate this tool as a template for Managarm's HKB Editor: https://github.com/ndahn/HkbEditor
- Mass addition of events. (Something like adding 3000-3109 for NPCs)
