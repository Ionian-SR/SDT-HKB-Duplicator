import xml.etree.ElementTree as ET
from xml_parser import XMLParser
import tkinter as tk
from tkinter import ttk

def update_xml_header(file_path):
    """
    Updates the XML declaration header to the specified format.

    Args:
        file_path (str): The path to the XML file to be modified.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Replace the header
    new_content = content.replace(
        "<?xml version='1.0' encoding='UTF-8'?>",
        '<?xml version="1.0" encoding="utf-8"?>'
    )

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(new_content)

    print(f"Updated header in '{file_path}'")

def run_parser():
    a_offset = entry_a_offset.get()
    new_anim_id = entry_anim_id.get()
    #entry_new_name = entry_new_name.get()
    new_csmg_name = f"{entry_new_name.get()}_CSMG"
    new_stateinfo_name = f"{entry_new_name.get()}"
    new_clipgen_name = f"a{a_offset}_{new_anim_id}"
    new_event_name = f"W_{new_stateinfo_name}"
    select_name = entry_select_name.get()
    xml_file = 'c0000.xml'  # Update this with your XML file path
    parser = XMLParser(xml_file)
    
    #   Find selected object
    obj_data, traced_objects = parser.find_object_by_name(select_name)

    #a_offset = f"050"
    #new_anim_id = f"300050"
    #new_csmg_name = f"GroundAttackCombo6_CMSG"
    #new_clipgen_name = f"a{a_offset}_{new_anim_id}"
    #new_stateinfo_name = f"GroundAttackCombo6"
    #new_event_name = f"W_{new_stateinfo_name}"

    new_clipgen_pointer_id = f"object{parser.get_largest_obj() + 1}"
    new_csmg_pointer_id = f"object{parser.get_largest_obj() + 2}"
    new_stateinfo_pointer_id = f"object{parser.get_largest_obj() + 3}"

    new_toStateId = parser.get_largest_toStateId() + 1
    new_userData = parser.get_largest_userData() + 1
    eventInfo_entry = parser.generate_event_info_entry()

    #   Append new animation to animationNames array. Update Count. Take new internalID.
    #   Object 7 contains animationNames eventInfos, and eventNames
    parser.append_to_array("object7", "animationNames", f"..\\..\\..\\..\\..\\Model\\chr\\c0000\\hkx\\a{a_offset}\\{new_clipgen_name}.hkx", is_pointer=False)
    new_animationInternalId = parser.find_array_count("object7", "animationNames") - 1

    #   Append eventNames
    parser.append_to_array("object7", "eventNames", f"{new_event_name}", is_pointer=False)
    new_eventNames_count = parser.find_array_count("object7", "eventNames")

    #   Append eventInfos
    parser.append_to_array("object4", "eventInfos", eventInfo_entry, is_pointer=False)
    new_eventInfos_count = parser.find_array_count("object4", "eventInfos") - 1

    #   Append new stateInfo object to stateMachine object
    parser.append_to_array(traced_objects[2], "states", f"{new_stateinfo_pointer_id}", is_pointer=True)

    #   Collect Statemachine information
    statemachine_object = parser.find_object_by_id(traced_objects[2])
    #   Find wildcard pointer ID
    wildcard_object_id = parser.get_wildcard_transition(statemachine_object)
    #   Generate a new transition entry and append it
    new_entry = parser.generate_transition_entry("object236", new_eventInfos_count, new_toStateId)
    parser.append_to_array(wildcard_object_id, "transitions", new_entry, is_pointer=False)

    #   PASS VARIABLES TO EXTERNAL LIBRARY XML PARSER DUPLICATE FUNCTION
    config = {
        "new_clipgen_pointer_id": new_clipgen_pointer_id,
        "new_csmg_pointer_id": new_csmg_pointer_id,
        "new_stateinfo_pointer_id": new_stateinfo_pointer_id,
        "new_clipgen_name": new_clipgen_name,
        "new_csmg_name": new_csmg_name,
        "new_stateinfo_name": new_stateinfo_name,
        "new_event_name": new_event_name,
        "new_toStateId": new_toStateId,
        "new_userData": new_userData,
        "new_animationInternalId": new_animationInternalId,
        "new_anim_id": new_anim_id,
    }

    #   If there is a clipGen object...
    if obj_data:
        #   Duplicate clipGen
        parser.duplicate_object(obj_data, new_clipgen_name, config)
        #   If there is a CSMG object...
        if traced_objects[0] is not None:
            #   Find and duplicate CSMG
            obj_data1 = parser.find_object_by_id(traced_objects[0])
            parser.duplicate_object(obj_data1, new_csmg_name, config)
            #   If there is a stateInfo object...
            if traced_objects[1] is not None:
                #   Find and duplicate CSMG
                obj_data2 = parser.find_object_by_id(traced_objects[1])
                parser.duplicate_object(obj_data2, new_stateinfo_name, config)
        
    parser.save_xml()
    update_xml_header(xml_file)
        
# ----- UI Setup -----
root = tk.Tk()
root.title("XML Animation Modifier")

tk.Label(root, text="Type in animation ID to duplicate (Example: a050_300040)").grid(row=0, column=0, sticky="e")
entry_select_name = tk.Entry(root)
entry_select_name.grid(row=0, column=1)
entry_select_name.insert(0, "a050_300040")

tk.Label(root, text="Animation offset (Example: '050', '101')").grid(row=1, column=0, sticky="e")
entry_a_offset = tk.Entry(root)
entry_a_offset.grid(row=1, column=1)
entry_a_offset.insert(0, "050")

tk.Label(root, text="New Animation ID (Example: 300050)").grid(row=2, column=0, sticky="e")
entry_anim_id = tk.Entry(root)
entry_anim_id.grid(row=2, column=1)
entry_anim_id.insert(0, "300050")

tk.Label(root, text="New Animation Name (Example: GroundAttackCombo6)").grid(row=3, column=0, sticky="e")
entry_new_name = tk.Entry(root)
entry_new_name.grid(row=3, column=1)
entry_new_name.insert(0, "GroundAttackCombo6")

# tk.Label(root, text="new_csmg_name").grid(row=3, column=0, sticky="e")
# entry_csmg_name = tk.Entry(root)
# entry_csmg_name.grid(row=2, column=1)

# tk.Label(root, text="new_stateinfo_name").grid(row=4, column=0, sticky="e")
# entry_stateinfo_name = tk.Entry(root)
# entry_stateinfo_name.grid(row=3, column=1)

# Arbitrary checkboxes for future logic
checkbox_vars = []
for i, label in enumerate(["Extra Transition", "Enable Debug", "Log Only"]):
    var = tk.BooleanVar()
    chk = tk.Checkbutton(root, text=label, variable=var)
    chk.grid(row=5 + i, columnspan=2, sticky="w")
    checkbox_vars.append(var)

run_button = tk.Button(root, text="Run", command=run_parser)
run_button.grid(row=8, columnspan=2, pady=10)

result_label = tk.Label(root, text="")
result_label.grid(row=9, columnspan=2)

root.mainloop()