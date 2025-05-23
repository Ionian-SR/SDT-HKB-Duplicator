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

xml_file_path = None


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

def backup_file(file_path, backup_dir="backups", max_backups=5):
    if not os.path.exists(file_path):
        print("File not found.")
        return

    os.makedirs(backup_dir, exist_ok=True)

    current_hash = file_hash(file_path)
    base_name = os.path.basename(file_path)
    name, ext = os.path.splitext(base_name)

    # Check for duplicate content
    for fname in os.listdir(backup_dir):
        if fname.endswith(".zip") and name in fname:
            zip_path = os.path.join(backup_dir, fname)
            with zipfile.ZipFile(zip_path, 'r') as z:
                with z.open(base_name) as f:
                    if file_hash(f) == current_hash:
                        print("File unchanged since last backup. Skipping.")
                        return

    # Create .zip backup
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(backup_dir, f"{name}_{timestamp}.zip")

    with zipfile.ZipFile(backup_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.write(file_path, arcname=base_name)

    print(f"✅ ZIP backup saved to: {backup_path}")

    # Trim old backups
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith(name) and f.endswith(".zip")],
        reverse=True
    )
    for old in backups[max_backups:]:
        os.remove(os.path.join(backup_dir, old))
        print(f"Removed old backup: {old}")

def select_xml_file():
    global xml_file_path
    file_path = filedialog.askopenfilename(
        title="Select XML File",
        filetypes=[("XML files", "*.xml")]
    )
    if file_path:
        xml_file_path = file_path
        xml_label.config(text=f"Selected: {file_path}")

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
            "csmg_script": hks_path,
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
    global xml_file_path
    json_path = filedialog.askopenfilename(title="Open Project File", filetypes=[("JSON files", "*.json")])
    if not json_path:
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            xml_file_path = data["files"]["behavior_xml"]
            xml_label.config(text=f"Loaded from project: {xml_file_path}")
            messagebox.showinfo("Project Loaded", f"Loaded: {data['project_name']}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load project:\n{e}")


def run_parser():
    global xml_file_path
    if not xml_file_path:
        result_label.config(text="No XML found. Please open a project.")
        return
    backup_file(xml_file_path)

    a_offset = entry_a_offset.get()
    new_anim_id = entry_anim_id.get()
    #entry_new_name = entry_new_name.get()
    new_csmg_name = f"{entry_new_name.get()}_CSMG"
    new_stateinfo_name = f"{entry_new_name.get()}"
    new_clipgen_name = f"a{a_offset}_{new_anim_id}"
    new_event_name = f"W_{new_stateinfo_name}"
    select_name = entry_select_name.get()

    parser = XMLParser(xml_file_path)
    
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


# tk.Label(root, text="new_csmg_name").grid(row=3, column=0, sticky="e")
# entry_csmg_name = tk.Entry(root)
# entry_csmg_name.grid(row=2, column=1)

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