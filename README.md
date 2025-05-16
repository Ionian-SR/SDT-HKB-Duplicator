# SDT NPC BEH Script 
This is a python tool that automates the process of adding new 3XXX object entries into a c9997.xml file for an NPC behavior BND for Sekiro: Shadows Die Twice.
This will make it so that if an enemy does not have a certain animation such as 3010, adding it via this tool will allow the game to call it for event and AI scripts.

## USAGE:
- Download and run the SDT-NPC-BEH-Script.exe from the Github release page, and follow the instructions.

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