# SDT HKB Duplicator
This is a tool that automates a majority of the process to add new havok behavior entries in c9997 or c0000.xml files. It also edits the .txt files and hks files associated for adding new events.

## Before using this tool
### How to convert hkx to xml
- Make sure to unpack a character's BehBND file, and convert the c9997 or c0000 hkx files into xml. You can download a tool from ?ServerName? discord to perform this: https://discord.com/channels/529802828278005773/529900741998149643/1322128333642924032
### Creating a project
- Before doing anything, create a project and store it somewhere convenient. 
- It will ask you for:
  - Project name
  - c0000.xml or c9997.xml
  - c0000_cmsg.hks
  - eventnameid.txt
  - statenameid.txt
- You should create different projects for different characters, but you will always choose the same c0000_cmsg.hks, eventnameid.txt, statenameid.txt. These files will be located under the action folder.
### Helpful resources
- Refer to Igor's Havok behavior doc editing guide if you want to know how to manually edit the files: https://docs.google.com/document/d/1LEpQDeyv6rCAjM1eKZ1K0kF9Ux-d7Vc81jTFEJHQwuw/edit?tab=t.0#heading=h.gjdgxs

## Usage
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
3. Type in the new ClipGen "animationName". This will be mostly likely identical to the new ClipGen name, but it can differ in some cases.
- *Examples*
  - a000_013810
  - a050_300050
4. Type in the new Stateinfo "name". This entry will determine the name of the event, state, CMSG, and stateinfo components. You will refer to this name in HKS files.
- *Examples*
  - ThrowDef13810
  - GroundAttackCombo5
5. Check the CMSG box if you are editing c0000.

## IMPORTANT 
### How to create new variations of existing events
- For Stateinfo name, put in the *exact* existing Stateinfo name. If you do not do this, the tool will create an entire new state, which will not be a variation.
- For new ClipGen name, make sure to change the aXXX offset. It would also be ideal to follow Fromsoft's naming convention, rather than choose a random ID.
- *Example*:
  - In this example, we want to create a 3rd Mortal Draw attack. Instead of creating an entire new event, we can simply add a new variation to "GroundSpecialAttackCombo3", which is a generic event used for multiple combat arts. We would use these settings to duplicate and create this 3rd MD attack:
  - Duplicate: a105_316020 (3rd Attack of Floating Passage, which is considered as GroundSpecialAttackCombo3)
  - New ClipGen Name: a10**6**_316020
  - New ClipGen animationName: a10**6**_316020
  - New Stateinfo Name: GroundSpecialAttackCombo3

### Unintended Behavior
- If you are creating a new variation of an event, **DO NOT** duplicate from an event that is different from the desired Stateinfo. 
- *Example*:
  - Duplicate: a105_316020 (3rd Attack of Floating Passage, which is considered as GroundSpecialAttackCombo3)
  - New Stateinfo Name: SwimMoveStart
  - In this case, you are duplicating from an event that is "GroundSpecialAttackCombo3" and adding this as a variation of "SwimMoveStart", which will create unintended behavior. 
  - If you would want to add a variation to "SwimMoveStart", please only duplicate from a "SwimMoveStart" event.

## After running this tool
- This tool will automatically format and add new states to the cmsg_hks file for c0000 edits, but will **NOT** do anything for c9997 edits. You will have to modify c9997.hks yourself if you want to add a new event for NPCs to use.
- You still need to add the animation to the .anibnd file for both c9997 and c0000.
- When creating a new event for c0000, everything should be handsfree once you run the tool, but you still need to modify the c0000_transition.hks to call the new animation. Don't forget that the new animation event in hks will have a "W_" before the stateinfo name. Example: FireEvent("W_GroundSpecialAttackCombo3")
- The game instantly crashing or NPCs refusing to perform the event are indicators where something went wrong during the process.
- If something does not work, make sure to refer to the backups folder in the same directory as the exe. It holds the project's compressed files before they were edited if you want to restore your files.

## Things I want to add in future updates
- A proper log for users.
- Remove "Unintended Behavior" possibility as listed previously.
- Maybe add automated c9997.hks edits.
- Integrate this tool as a template for Managarm's HKB Editor: https://github.com/ndahn/HkbEditor
- Mass addition of events. (Something like adding 3000-3109 for NPCs)