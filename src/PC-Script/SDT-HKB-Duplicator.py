import xml.etree.ElementTree as ET
from xml_parser import XMLParser
from hks_parser import HKSParser
import tkinter as tk
#from tkinter import ttk
from tkinter import filedialog
from tkinter.simpledialog import askstring
import json
from tkinter import messagebox
import os
import zipfile
import hashlib
from datetime import datetime
import re

xml_file_path = None
hks_file_path = None
event_txt_path = None
state_txt_path = None

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
            if not path:
                print(f"[WARNING] Skipping '{label}' - path is None or empty.")
                continue
            if os.path.exists(path):
                arcname = os.path.basename(path)
                z.write(path, arcname=arcname)
                #print(f"Added {arcname} to {zip_name}")
            else:
                print(f"Skipped missing file: {path}")

    print(f"Backup complete: {zip_path}")

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

def to_hkb_state(text):
    if not isinstance(text, str):
        print("⚠️ to_hkb_state received non-string input:", type(text), text)
        return "INVALID_INPUT"
    s1 = re.sub(r'(?<!^)(?=[A-Z])', '_', text)
    s2 = re.sub(r'(\D)(\d)', r'\1_\2', s1)
    return s2.upper()

def entry_exists_in_file(event_file, search_name):
    """
    Checks if the given search_name exists in the event file.

    Args:
        event_file (str): Path to the file containing entries.
        search_name (str): The name to search for (e.g., 'a000_000004.hkx_WC').

    Returns:
        bool: True if found, False otherwise.
    """
    # Step 1: Detect encoding
    try:
        with open(event_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(event_file, 'r', encoding='cp932') as f:
            lines = f.readlines()

    # Step 2: Search for the event name
    for line in lines:
        if '=' in line:
            parts = line.split('=')
            if len(parts) == 2:
                event_name = parts[1].strip().strip('"')
                if event_name == search_name:
                    return True

    return False

def seperate_id_offset(text):
    if '_' not in text:
        print("Error: Underscore separator not found.")
    else:
        parts = text.split("_", 1) 

        if not parts[0].startswith('a'):
            print("Error: First part does not start with 'a'.")
        else:
            part1, part2 = parts
            return part1, part2

def run_parser():
    global xml_file_path
    global hks_file_path
    if not xml_file_path:
        result_label.config(text="No XML found. Please open a project.")
        return

    #   Set up XMLParser with XML file path
    xml_parser = XMLParser(xml_file_path)
    #   Seperate text from input
    a_offset, new_anim_id = seperate_id_offset(entry_new_animationName.get())
    new_animationName = entry_new_animationName.get()
    new_anim_id_stripped = new_anim_id.lstrip("0")
    #   Create new names
    new_cmsg_name = f"{entry_new_stateinfo_name.get()}_CMSG"
    new_stateinfo_name = f"{entry_new_stateinfo_name.get()}"
    new_clipgen_name = f"{entry_new_name.get()}"
    new_event_name = f"W_{new_stateinfo_name}"
    select_name = entry_select_name.get()
    #   Create new IDs
    large_obj_id = xml_parser.get_largest_obj()
    new_clipgen_pointer_id = f"object{large_obj_id + 1}"
    new_cmsg_pointer_id = f"object{large_obj_id + 2}"
    new_stateinfo_pointer_id = f"object{large_obj_id + 3}"
    new_toStateId = xml_parser.get_largest_toStateId() + 1
    new_userData = xml_parser.get_largest_userData() + 1
    eventInfo_entry = xml_parser.generate_event_info_entry()

    is_register_new_event = True    #   default to true
    modify_hks = False              #   default to False

    #   Check if desired object already exists
    #   If NOT, stop
    desired_obj_data = xml_parser.find_object_by_name(new_clipgen_name)
    if desired_obj_data is not None:
        print("\033[91mDesired object already exists. Cancelling operation.\033[0m")
        return

    #   Find selected object
    #   If object doesn't exist, stop.
    selected_obj_data = xml_parser.find_object_by_name(select_name)
    selected_traced_objects = xml_parser.trace_references(selected_obj_data['id'])
    if selected_obj_data is None:
        return
    
    #   Check if selected objects' CMSG already exists. If so, do not register new events.
    selected_new_cmsg_obj_data = xml_parser.find_object_by_name(new_cmsg_name)
    if selected_new_cmsg_obj_data is not None and selected_new_cmsg_obj_data.get('fields', {}).get('name') == new_cmsg_name:
        is_register_new_event = False
        print("\033[93mExisting CMSG found. Appending to CMSG array.\033[0m")

    if hks_file_path and os.path.isfile(hks_file_path):
        hks_parser = HKSParser(hks_file_path)
        modify_hks = True

        # Backup project files
        backup_project_files(
            files_dict={
                "behavior_xml": xml_file_path,
                "cmsg_script": hks_file_path,
                "event_id_map": event_txt_path,
                "state_id_map": state_txt_path
            },
        )
    else:
        hks_parser = None

    #   If registering a new event...
    #   - Append txt files
    #   - Reformat and append cmsg file
    #   - Append to eventNames and eventInfos array in xml
        
    #   Find object that contains animationnames, and eventNames
    animationNames_obj_data = xml_parser.find_object_by_field('field[@name="animationNames"]')
    animationNames_obj_id = animationNames_obj_data['id']
    
    #   Find object that contains eventInfos
    eventInfos_obj_data = xml_parser.find_object_by_field('field[@name="eventInfos"]')
    eventInfos_obj_id = eventInfos_obj_data['id']


    if is_register_new_event == True:
        #   Append txt files
        if modify_hks:
            generate_new_event = entry_exists_in_file(event_txt_path, new_event_name)
            print('Is event in txt files already?', generate_new_event)
            if generate_new_event == False:
                append_to_eventnameid(event_txt_path, new_event_name)
                append_to_statenameid(state_txt_path, new_stateinfo_name)
            
            #   Reformat g_paramHkbState in cmsg
            if edit_cmsg_hks_var.get():
                hks_parser.reformat_g_paramHkbState()

        #   Append eventNames
        xml_parser.append_to_array(animationNames_obj_id, "eventNames", f"{new_event_name}", is_pointer=False)

        #   Append eventInfos
        xml_parser.append_to_array(eventInfos_obj_id, "eventInfos", eventInfo_entry, is_pointer=False)
        new_eventInfos_count = xml_parser.find_array_count(eventInfos_obj_id, "eventInfos") - 1
            
        #   Append new stateInfo object to stateMachine object
        xml_parser.append_to_array(selected_traced_objects[2], "states", f"{new_stateinfo_pointer_id}", is_pointer=True)

        #   Collect Statemachine information
        statemachine_object = xml_parser.find_object_by_id(selected_traced_objects[2])

        #   Find wildcard pointer ID
        wildcard_object_id = xml_parser.get_wildcard_transition(statemachine_object)

        #   Find original wildcard record information
        selected_stateinfo_obj_data = xml_parser.find_object_by_id(selected_traced_objects[1])
        transition_pointer_id = xml_parser.find_transition_record_by_field_value(wildcard_object_id, "toStateId", selected_stateinfo_obj_data['fields']['stateId'])
        
        #   Generate a new transition entry and append it
        new_entry = xml_parser.generate_transition_entry(transition_pointer_id, new_eventInfos_count, new_toStateId)
        xml_parser.append_to_array(wildcard_object_id, "transitions", new_entry, is_pointer=False)

    #   Get last entry of animationNames to get chr id
    last_animationNames_entry = ET.tostring(xml_parser.get_last_array_element(animationNames_obj_id, "animationNames"))
    chr_id = xml_parser.get_chr_id(last_animationNames_entry)
    print(f"CHR ID: {chr_id}")

    #   Append new animation to animationNames array. Update Count. Take new internalID.
    xml_parser.append_to_array(animationNames_obj_id, "animationNames", f"..\\..\\..\\..\\..\\Model\\chr\\{chr_id}\\hkx\\{a_offset}\\{a_offset}_{new_anim_id}.hkx", is_pointer=False)
    new_animationInternalId = xml_parser.find_array_count(animationNames_obj_id, "animationNames") - 1

    #   PASS VARIABLES TO EXTERNAL LIBRARY XML PARSER DUPLICATE FUNCTION
    config = {
        "new_clipgen_pointer_id": new_clipgen_pointer_id,
        "new_cmsg_pointer_id": new_cmsg_pointer_id,
        "new_stateinfo_pointer_id": new_stateinfo_pointer_id,
        "new_clipgen_name": new_clipgen_name,
        "new_animationName": new_animationName,
        "new_cmsg_name": new_cmsg_name,
        "new_stateinfo_name": new_stateinfo_name,
        "new_event_name": new_event_name,
        "new_toStateId": new_toStateId,
        "new_userData": new_userData,
        "new_animationInternalId": new_animationInternalId,
        "new_anim_id": new_anim_id_stripped,
    }

    #   If there is a clipGen object...
    if selected_obj_data:
        #   Duplicate clipGen
        xml_parser.duplicate_object(selected_obj_data, new_clipgen_name, config)
        #   If CMSG already exists, append to it.
        if is_register_new_event == False:
            xml_parser.append_to_array(selected_new_cmsg_obj_data.get('id'), "generators", new_clipgen_pointer_id, is_pointer=True)
        else:
            #   If there is a cmsg object...
            if selected_traced_objects[0] is not None:
                #   Find and duplicate cmsg
                cmsg_obj_data = xml_parser.find_object_by_id(selected_traced_objects[0])
                xml_parser.duplicate_object(cmsg_obj_data, new_cmsg_name, config)
                
                #   If there is a stateInfo object...
                if selected_traced_objects[1] is not None:
                    #   Find and duplicate stateinfo
                    stateinfo_obj_data = xml_parser.find_object_by_id(selected_traced_objects[1])
                    xml_parser.duplicate_object(stateinfo_obj_data, new_stateinfo_name, config)
                    
                    if modify_hks:
                        #   MODIFY CMSG HKS
                        #   Convert new stateinfo name to HKS_STATE
                        new_hks_stateinfo_name = "HKB_STATE_" + to_hkb_state(new_stateinfo_name)
                        #   Find largest number and add 1 to it
                        new_max_number = hks_parser.get_max_number() + 1
                        #   Append new defintion above g_param
                        hks_parser.append_def(new_hks_stateinfo_name + " = " + str(new_max_number))
                        
                        #   Find OG HKB_STATE
                        selected_hks_stateinfo_name = "HKB_STATE_" + to_hkb_state(stateinfo_obj_data['fields']['name'])
                        #   Find hkb_state inside g_param array
                        selected_hks_stateinfo_name_line = hks_parser.find_hkb_state(selected_hks_stateinfo_name)
                        #   If there is an entry in the array, add
                        if selected_hks_stateinfo_name_line is not None:
                            #   Find hkb_state inside g_param array
                            modified_line = re.sub(r"\[.*?\]", f"[{new_hks_stateinfo_name}]", selected_hks_stateinfo_name_line)
                            #   Append to g_param array
                            hks_parser.append_g_param(modified_line)
                        #   Append function
                        hks_parser.append_functions(new_stateinfo_name, new_hks_stateinfo_name)
                                        
            
    xml_parser.save_xml(xml_file_path)
    update_xml_header(xml_file_path)
        
import tkinter as tk

# ----- UI Setup -----
root = tk.Tk()
root.title("SDT HKB Duplicator")
root.geometry("600x300")
root.iconbitmap('favicon.ico')
root.columnconfigure(1, weight=1)

tk.Label(root, text='Type in Clipgen "name" to duplicate').grid(row=0, column=0, sticky="w", padx=10, pady=5)
entry_select_name = tk.Entry(root)
entry_select_name.grid(row=0, column=1, sticky="ew", padx=10, pady=5)
entry_select_name.insert(0, "a000_013800_hkx_AutoSet_00")

tk.Label(root, text='New Clipgen "name"').grid(row=1, column=0, sticky="w", padx=10, pady=5)
entry_new_name = tk.Entry(root)
entry_new_name.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
entry_new_name.insert(0, "a000_013810_hkx_AutoSet_00")

tk.Label(root, text='New Clipgen "animationName"').grid(row=2, column=0, sticky="w", padx=10, pady=5)
entry_new_animationName = tk.Entry(root)
entry_new_animationName.grid(row=2, column=1, sticky="ew", padx=10, pady=5)
entry_new_animationName.insert(0, "a000_013810")

tk.Label(root, text='New Stateinfo "name"').grid(row=3, column=0, sticky="w", padx=10, pady=5)
entry_new_stateinfo_name = tk.Entry(root)
entry_new_stateinfo_name.grid(row=3, column=1, sticky="ew", padx=10, pady=5)
entry_new_stateinfo_name.insert(0, "ThrowDef13810")

edit_cmsg_hks_var = tk.BooleanVar(value=False)

check_edit_cmsg_hks = tk.Checkbutton(
    root,
    text="Edit cmsg_hks file? Only check this for c0000.xml edits",
    variable=edit_cmsg_hks_var
)
check_edit_cmsg_hks.grid(row=4, columnspan=2, pady=5)

project_buttons_frame = tk.Frame(root)
project_buttons_frame.grid(row=7, columnspan=2)

xml_label = tk.Label(root, text="No file selected")


btn_create_project = tk.Button(project_buttons_frame, text="Create Project", command=lambda: create_project())
btn_create_project.grid(row=0, column=0, padx=5)

btn_open_project = tk.Button(project_buttons_frame, text="Open Project", command=lambda: open_project())
btn_open_project.grid(row=0, column=1, padx=5)

#btn_open_only_xml = tk.Button(project_buttons_frame, text="Open only XML", command=lambda: select_only_xml_file())
#btn_open_only_xml.grid(row=0, column=2, padx=5)

run_button = tk.Button(root, text="Run", command=run_parser)
run_button.grid(row=8, columnspan=3, pady=10)

result_label = tk.Label(root, text="")
result_label.grid(row=9, columnspan=2)

root.mainloop()