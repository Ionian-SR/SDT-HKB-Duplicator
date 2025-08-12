# SDT NPC Duplicator
This is a tool that automates a majority of the process to add new havok behavior entries in c9997 or c0000.xml files. It also edits the .txt files and hks files associated for adding new events.

# Usage
1. Type in the ClipGen "name" you would want to duplicate. This is usually the animation ID found in DS Animation Studio, but it is not always the case. If you want a prosthetic attack, choose an animation ID that is considered a prosthetic attack. Same with Throws, Mid-air, and other special states. 
  - *Examples*
  - a000_013800_hkx_AutoSet_00
    - This is what the ClipGen name looks like for a Mikiri animation of an NPC. NPC ClipGen names often have additional text after the ID.
  - a050_300040
    - This is what the ClipGen name looks like for a Ground Attack of the PC. 
2. Type in the new ClipGen "name" you would like. Ideally, you would just increment the original ID in some way, but you can put whatever you want. 
  - *Examples*
  - a000_013810_hkx_AutoSet_00
  - a050_300050
3. Type in the ClipGen "animationName". This will be mostly likely identical to ClipGen name, but it can differ in some cases.
  - *Examples*
  - a000_013810
  - a050_300050
4. Type in Stateinfo "name". This entry will determine the name of the event, state, CMSG, and stateinfo components.
  - *Examples*
  - ThrowDef13810
  - GroundAttackCombo5

**IMPORTANT** 
- For creating new aXXX variations of a particular event, follow these instructions:
- For Stateinfo name, put in the *exact* existing Stateinfo name. If you do not do this, the tool will create an entire new state, which will not be a variation.
  - *Example*
  - GroundSpecialAttackCombo1
- For ClipGen name, put in the *exact* existing ClipGen name, but change the aXXX offset.
  - *Example*
  - a050_300040 &rarr; a051_300040

## IMPORTANT NOTES:
- This tool will check if an animation already exists.
- This tool will also check if an animation in a different aXXX category exists.
- This means you can run a000_003000 to a000_003100 if you wanted do with no issues.
- This tool CANNOT add new entries of 3XXX in a specific aXXX category if that category does not exist. (Can't add a100_003000 to an NPC that doesn't even have a100 category)
- Currently will output new_c9997.xml after running. 

## BUILD INSTRUCTIONS (ONLY FOR PEOPLE WHO WANT TO EDIT THE SOURCE CODE)
### Prerequisites
- **Python 3.10+**
- **PyInstaller**

1. **Clone repository**
- git clone https://github.com/Ionian-SR/SDT-NPC-Behbnd-Script.git
2. **Create python virtual environment**
- python -m venv venv
3. **Activate venv**
- source venv/bin/activate
4. **Install requirements**
- pip install Pillow pyinstaller
5. **Build .exe (Run this in the parent directory)**
- pyinstaller --name=SDT-NPC-BEH-Script --onefile --noconsole --add-data "src/hunfive.jpg;." --add-data "src/event_names.txt;." src/SDT-NPC-BEH-Script.py

## Other Documentation
- Havok behavior doc editing guide by Igor: https://docs.google.com/document/d/1LEpQDeyv6rCAjM1eKZ1K0kF9Ux-d7Vc81jTFEJHQwuw/edit?tab=t.0#heading=h.gjdgxs

## Credit
- Ionian for creating the initial script.
- Last孤影众丶 for creating a UI and adding new functionality such as event compatibility.