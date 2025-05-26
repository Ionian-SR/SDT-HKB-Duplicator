import xml.etree.ElementTree as ET
from xml_parser import XMLParser
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter.simpledialog import askstring
import json
from tkinter import messagebox
import os
import zipfile
import shutil
import hashlib
from datetime import datetime
import re

xml_file_path = None
hks_file_path = None
event_txt_path = None
state_txt_path = None

def reformat_g_paramHkbState(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    start_idx = None
    end_idx = None
    brace_level = 0
    inside_block = False

    for i, line in enumerate(lines):
        if not inside_block and "g_paramHkbState" in line and "=" in line and "{" in line:
            start_idx = i
            brace_level += line.count("{") - line.count("}")
            inside_block = True
        elif inside_block:
            brace_level += line.count("{") - line.count("}")
            if brace_level == 0:
                end_idx = i
                break

    if start_idx is None or end_idx is None:
        print("❌ g_paramHkbState block not found or malformed.")
        return

    # Extract and collapse the original block
    block_lines = lines[start_idx:end_idx + 1]
    raw_block = "".join(block_lines)

    # Extract individual entries like [HKB_STATE_SOMETHING] = { ... }
    entry_pattern = r'(\[\s*HKB_STATE_[^\]]+\s*\]\s*=\s*\{[^}]*\})'
    entries = re.findall(entry_pattern, raw_block)

    # Format entries line-by-line
    formatted_block = "g_paramHkbState = {\n"
    for entry in entries:
        formatted_block += f"    {entry},\n"
    formatted_block = formatted_block.rstrip(",\n") + "\n}\n"

    # Replace original lines
    lines[start_idx:end_idx + 1] = [formatted_block]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print("✅ Reformatted g_paramHkbState block.")

def file_hash(source):
    """Compute SHA-256 hash from a file path or a file-like object"""
    h = hashlib.sha256()

    if isinstance(source, (str, os.PathLike)):
        with open(source, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
    else:
        for chunk in iter(lambda: source.read(8192), b''):
            h.update(chunk)
        source.seek(0)  # Reset stream position if needed later

    return h.hexdigest()

def backup_project_files(files_dict, project_name="project", backup_dir="backups"):
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_name = f"{project_name}_backup_{timestamp}.zip"
    zip_path = os.path.join(backup_dir, zip_name)

    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for label, path in files_dict.items():
            if os.path.exists(path):
                arcname = os.path.basename(path)
                z.write(path, arcname=arcname)
                print(f"Added {arcname} to {zip_name}")
            else:
                print(f"Skipped missing file: {path}")

    print(f"Backup complete: {zip_path}")

def select_xml_file():
    global xml_file_path
    file_path = filedialog.askopenfilename(
        title="Select XML File",
        filetypes=[("XML files", "*.xml")]
    )
    if file_path:
        xml_file_path = file_path
        xml_label.config(text=f"Selected: {file_path}")

def append_to_eventnameid(event_file, new_event_name):
    # Step 1: Detect encoding
    try:
        with open(event_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        encoding_used = 'utf-8-sig'
    except UnicodeDecodeError:
        with open(event_file, 'r', encoding='cp932') as f:
            lines = f.readlines()
        encoding_used = 'cp932'

    # Step 2: Get last ID
    last_id = -1
    for line in lines:
        if '=' in line:
            try:
                last_id = int(line.split('=')[0].strip())
            except ValueError:
                continue

    if last_id == -1:
        print("No valid entries found.")
        return

    new_id = last_id + 1

    # Step 3: Append
    with open(event_file, 'a', encoding=encoding_used) as f:
        f.write(f'{new_id} = "{new_event_name}"\n')

    print(f"Appended: {new_id} = \"{new_event_name}\"")

def append_to_statenameid(state_file, new_state_name):
    # Step 1: Detect encoding
    try:
        with open(state_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        encoding_used = 'utf-8-sig'
    except UnicodeDecodeError:
        with open(state_file, 'r', encoding='cp932') as f:
            lines = f.readlines()
        encoding_used = 'cp932'

    # Step 2: Get the last ID
    last_id = -1
    for line in lines:
        if '=' in line:
            try:
                last_id = int(line.split('=')[0].strip())
            except ValueError:
                continue

    if last_id == -1:
        print("No valid entries found in state file.")
        return

    new_id = last_id + 1

    # Step 3: Append the new line
    with open(state_file, 'a', encoding=encoding_used) as f:
        f.write(f'\n{new_id} = "{new_state_name}"')

    print(f"Appended to state: {new_id} = \"{new_state_name}\"")

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

def create_project():
    global xml_file_path
    project_name = askstring("Project Name", "Enter a name for your project:")
    if not project_name:
        project_name = "SDT-BEH-Project"
        #messagebox.showwarning("Canceled", "Project creation canceled — no name provided.")
        return
    xml_path = filedialog.askopenfilename(title="Select XML File", filetypes=[("XML files", "*.xml")])
    if not xml_path:
        return
    hks_path = filedialog.askopenfilename(title="Select HKS File", filetypes=[("Lua/HKS files", "*.hks *.lua")])
    if not hks_path:
        return
    event_txt = filedialog.askopenfilename(title="Select eventnameid.txt", filetypes=[("Text files", "*.txt")])
    if not event_txt:
        return
    state_txt = filedialog.askopenfilename(title="Select statenameid.txt", filetypes=[("Text files", "*.txt")])
    if not state_txt:
        return

    project_data = {
        "project_name": project_name,
        "files": {
            "behavior_xml": xml_path,
            "cmsg_script": hks_path,
            "event_id_map": event_txt,
            "state_id_map": state_txt
        }
    }

    save_path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        title="Save Project File",
        initialfile=f"{project_name}.json"
    )

    if save_path:
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2)
        messagebox.showinfo("Project Saved", f"Saved to {save_path}")
        json_path = save_path
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            xml_file_path = data["files"]["behavior_xml"]
            xml_label.config(text=f"Loaded from project: {xml_file_path}")
            messagebox.showinfo("Project Loaded", f"Loaded: {data['project_name']}")
    else:
        messagebox.showwarning("Canceled", "Project not saved.")

def open_project():
    global xml_file_path, hks_file_path, event_txt_path, state_txt_path
    json_path = filedialog.askopenfilename(title="Open Project File", filetypes=[("JSON files", "*.json")])
    if not json_path:
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract all file paths
        xml_file_path = data["files"]["behavior_xml"]
        hks_file_path = data["files"]["cmsg_script"]
        event_txt_path = data["files"]["event_id_map"]
        state_txt_path = data["files"]["state_id_map"]

        # Update UI label to reflect loaded XML
        xml_label.config(text=f"Loaded from project: {xml_file_path}")
        messagebox.showinfo("Project Loaded", f"Loaded: {data['project_name']}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load project:\n{e}")

def run_parser():
    global xml_file_path
    if not xml_file_path:
        result_label.config(text="No XML found. Please open a project.")
        return
    
    #   Set up XMLParser with XML file path
    parser = XMLParser(xml_file_path)

    #   Create new names
    a_offset = entry_a_offset.get()
    new_anim_id = entry_anim_id.get()
    new_cmsg_name = f"{entry_new_name.get()}_CMSG"
    new_stateinfo_name = f"{entry_new_name.get()}"
    new_clipgen_name = f"a{a_offset}_{new_anim_id}"
    new_event_name = f"W_{new_stateinfo_name}"
    select_name = entry_select_name.get()
    #   Create variables
    large_obj_id = parser.get_largest_obj()
    new_clipgen_pointer_id = f"object{large_obj_id + 1}"
    new_cmsg_pointer_id = f"object{large_obj_id + 2}"
    new_stateinfo_pointer_id = f"object{large_obj_id + 3}"
    new_toStateId = parser.get_largest_toStateId() + 1
    new_userData = parser.get_largest_userData() + 1
    eventInfo_entry = parser.generate_event_info_entry()

    is_register_new_event = True

    #   Check if desired object already exists
    #   If NOT, stop
    desired_obj_data, desired_traced_objects = parser.find_object_by_name(new_clipgen_name)
    if desired_obj_data is not None:
        print("\033[91mDesired object already exists. Cancelling operation.\033[0m")
        return

    #   Find selected object
    #   If object doesn't exist, stop.
    selected_obj_data, selected_traced_objects = parser.find_object_by_name(select_name)
    if selected_obj_data is None:
        return
    
    #   Check if selected objects' CMSG already exists. If so, do not register new events.
    selected_cmsg_obj_data, selected_cmsg_traced_objects = parser.find_object_by_name(new_cmsg_name)
    if selected_cmsg_obj_data is not None and selected_cmsg_obj_data.get('fields', {}).get('name') == new_cmsg_name:
        is_register_new_event = False
        print("\033[93mExisting CMSG found. Appending to CMSG array.\033[0m")

    #   Backup project files
    backup_project_files(
        files_dict={
            "behavior_xml": xml_file_path,
            "cmsg_script": hks_file_path,
            "event_id_map": event_txt_path,
            "state_id_map": state_txt_path
        },
    )

    #   If registering a new event...
    #   - Append txt files
    #   - Reformat and append cmsg file
    #   - Append to eventNames and eventInfos array in xml
    if is_register_new_event == True:
        #   Append txt files
        append_to_eventnameid(event_txt_path, new_event_name)
        append_to_statenameid(state_txt_path, new_stateinfo_name)
        
        #   Reformat g_paramHkbState in cmsg
        reformat_g_paramHkbState(hks_file_path)

        #   Append eventNames
        parser.append_to_array("object7", "eventNames", f"{new_event_name}", is_pointer=False)
        #new_eventNames_count = parser.find_array_count("object7", "eventNames")

        #   Append eventInfos
        parser.append_to_array("object4", "eventInfos", eventInfo_entry, is_pointer=False)
        new_eventInfos_count = parser.find_array_count("object4", "eventInfos") - 1
            
        #   Append new stateInfo object to stateMachine object
        parser.append_to_array(selected_traced_objects[2], "states", f"{new_stateinfo_pointer_id}", is_pointer=True)

        #   Collect Statemachine information
        statemachine_object = parser.find_object_by_id(selected_traced_objects[2])

        #   Find wildcard pointer ID
        wildcard_object_id = parser.get_wildcard_transition(statemachine_object)
        
        #   Generate a new transition entry and append it
        new_entry = parser.generate_transition_entry("object236", new_eventInfos_count, new_toStateId)
        parser.append_to_array(wildcard_object_id, "transitions", new_entry, is_pointer=False)

    #   Append new animation to animationNames array. Update Count. Take new internalID.
    #   Object 7 contains animationNames eventInfos, and eventNames
    parser.append_to_array("object7", "animationNames", f"..\\..\\..\\..\\..\\Model\\chr\\c0000\\hkx\\a{a_offset}\\{new_clipgen_name}.hkx", is_pointer=False)
    new_animationInternalId = parser.find_array_count("object7", "animationNames") - 1

    #   PASS VARIABLES TO EXTERNAL LIBRARY XML PARSER DUPLICATE FUNCTION
    config = {
        "new_clipgen_pointer_id": new_clipgen_pointer_id,
        "new_cmsg_pointer_id": new_cmsg_pointer_id,
        "new_stateinfo_pointer_id": new_stateinfo_pointer_id,
        "new_clipgen_name": new_clipgen_name,
        "new_cmsg_name": new_cmsg_name,
        "new_stateinfo_name": new_stateinfo_name,
        "new_event_name": new_event_name,
        "new_toStateId": new_toStateId,
        "new_userData": new_userData,
        "new_animationInternalId": new_animationInternalId,
        "new_anim_id": new_anim_id,
    }

    #   If there is a clipGen object...
    if selected_obj_data:
        #   Duplicate clipGen
        parser.duplicate_object(selected_obj_data, new_clipgen_name, config)
        #   If CMSG already exists, append to it.
        if is_register_new_event == False:
            print(selected_cmsg_obj_data.get('id'))
            parser.append_to_array(selected_cmsg_obj_data.get('id'), "generators", new_clipgen_pointer_id, is_pointer=True)
        else:
            #   If there is a cmsg object...
            if selected_traced_objects[0] is not None:
                #   Find and duplicate cmsg
                cmsg_obj_data = parser.find_object_by_id(selected_traced_objects[0])
                parser.duplicate_object(cmsg_obj_data, new_cmsg_name, config)
                #   If there is a stateInfo object...
                if selected_traced_objects[1] is not None:
                    #   Find and duplicate cmsg
                    stateinfo_obj_data = parser.find_object_by_id(selected_traced_objects[1])
                    parser.duplicate_object(stateinfo_obj_data, new_stateinfo_name, config)
            
    parser.save_xml(xml_file_path)
    update_xml_header(xml_file_path)
        
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

project_buttons_frame = tk.Frame(root)
project_buttons_frame.grid(row=7, columnspan=2)

xml_label = tk.Label(root, text="No file selected")


btn_create_project = tk.Button(project_buttons_frame, text="Create Project", command=lambda: create_project())
btn_create_project.grid(row=0, column=0, padx=5)

btn_open_project = tk.Button(project_buttons_frame, text="Open Project", command=lambda: open_project())
btn_open_project.grid(row=0, column=1, padx=5)


#xml_button = tk.Button(root, text="Browse XML File", command=select_xml_file)
#xml_button.grid(row=6, columnspan=2, pady=(5, 0))

#xml_label = tk.Label(root, text="No file selected")
#xml_label.grid(row=5, columnspan=2)    


# tk.Label(root, text="new_cmsg_name").grid(row=3, column=0, sticky="e")
# entry_cmsg_name = tk.Entry(root)
# entry_cmsg_name.grid(row=2, column=1)

# tk.Label(root, text="new_stateinfo_name").grid(row=4, column=0, sticky="e")
# entry_stateinfo_name = tk.Entry(root)
# entry_stateinfo_name.grid(row=3, column=1)

# Arbitrary checkboxes for future logic
# checkbox_vars = []
# for i, label in enumerate(["Extra Transition", "Enable Debug", "Log Only"]):
#     var = tk.BooleanVar()
#     chk = tk.Checkbutton(root, text=label, variable=var)
#     chk.grid(row=5 + i, columnspan=2, sticky="w")
#     checkbox_vars.append(var)

run_button = tk.Button(root, text="Run", command=run_parser)
run_button.grid(row=8, columnspan=2, pady=10)

result_label = tk.Label(root, text="")
result_label.grid(row=9, columnspan=2)

root.mainloop()