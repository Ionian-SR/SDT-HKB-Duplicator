import re
import xml.etree.ElementTree as ET
import shutil
import sys
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import xml.etree.ElementTree as ET
from PIL import Image, ImageTk

aXXX = 0
selected_file_path = None

def process_arguments():
    try:
        numbers = []
        for entry in entries:
            if entry.get().strip():
                numbers.append(int(entry.get().strip()))
        
        global aXXX
        aXXX = numbers[0] if numbers else None

        if len(numbers) == 2:
            num = numbers[1]
            if 3000 <= num <= 3109:
                return [num]
            else:
                messagebox.showinfo("错误！", f"忽略{num} - 动作编号必须在3000-3109范围内")
                return []
        elif len(numbers) == 3:
            start = numbers[1]
            end = numbers[2]
            if start < 3000 or end > 3109:
                messagebox.showinfo("错误！", "起始和结束动作编号必须在3000-3109范围内")
                return []
            else:
                return list(range(start, end + 1))
        else:
            messagebox.showinfo("错误！", "Error: Please enter two or three parameters")
            return []
    except ValueError:
        messagebox.showinfo("错误！", "无效输入,请输入正常的动作编号")

def generate_clip_gen(objectId, name, animationName, animInternalId):
    xml_clip = f"""  
    <object id="{objectId}" typeid="type211" > <!-- hkbClipGenerator -->
        <record> <!-- hkbClipGenerator -->
            <field name="propertyBag">
                <array count="0" elementtypeid="type15"> <!-- ArrayOf hkDefaultPropertyBag -->
                </array>
            </field>
            <field name="variableBindingSet"><pointer id="object0"/></field>
            <field name="userData"><integer value="0"/></field>
            <field name="name"><string value="{name}"/></field>
            <field name="animationName"><string value="{animationName}"/></field>
            <field name="triggers"><pointer id="object0"/></field>
            <field name="userPartitionMask"><integer value="0"/></field>
            <field name="cropStartAmountLocalTime"><real dec="0" hex="#0"/></field>
            <field name="cropEndAmountLocalTime"><real dec="0" hex="#0"/></field>
            <field name="startTime"><real dec="0" hex="#0"/></field>
            <field name="playbackSpeed"><real dec="1" hex="#3ff0000000000000"/></field>
            <field name="enforcedDuration"><real dec="0" hex="#0"/></field>
            <field name="userControlledTimeFraction"><real dec="0" hex="#0"/></field>
            <field name="mode"><integer value="0"/><!-- MODE_SINGLE_PLAY --></field>
            <field name="flags"><integer value="0"/></field>
            <field name="animationInternalId"><integer value="{animInternalId}"/></field>
        </record>
    </object>"""
    return xml_clip

def generate_csmg(objectId, name, userData, pointer, animId):
    xml_csmg = f"""
    <object id="{objectId}" typeid="type200" > <!-- CustomManualSelectorGenerator -->
        <record> <!-- CustomManualSelectorGenerator -->
            <field name="propertyBag">
                <array count="0" elementtypeid="type15"> <!-- ArrayOf hkDefaultPropertyBag -->
                </array>
            </field>
            <field name="variableBindingSet"><pointer id="object0"/></field>
            <field name="userData"><integer value="{userData}"/></field>
            <field name="name"><string value="{name}"/></field>
            <field name="generators">
                <array count="1" elementtypeid="type41"> <!-- ArrayOf T*< hkbGenerator > -->
                <pointer id="{pointer}"/>
                </array>
            </field>
            <field name="offsetType"><integer value="15"/><!-- AnimIdOffset --></field>
            <field name="animId"><integer value="{animId}"/></field>
            <field name="animeEndEventType"><integer value="3"/><!-- None --></field>
            <field name="enableScript"><bool value="true"/></field>
            <field name="enableTae"><bool value="true"/></field>
            <field name="changeTypeOfSelectedIndexAfterActivate"><integer value="1"/><!-- SELF_TRANSITION --></field>
            <field name="generatorChangedTransitionEffect"><pointer id="object0"/></field>
            <field name="checkAnimEndSlotNo"><integer value="1"/></field>
            <field name="replanningAI"><integer value="0"/><!-- Enable --></field>
        </record>
    </object>"""
    return xml_csmg

def generate_stateinfo(objectId, name, pointer, stateId):
    xml_stateinfo = f"""
    <object id="{objectId}" typeid="type115" > <!-- hkbStateMachine::StateInfo -->
        <record> <!-- hkbStateMachine::StateInfo -->
            <field name="propertyBag">
                <array count="0" elementtypeid="type15"> <!-- ArrayOf hkDefaultPropertyBag -->
                </array>
            </field>
            <field name="variableBindingSet"><pointer id="object0"/></field>
            <field name="listeners">
                <array count="0" elementtypeid="type123"> <!-- ArrayOf T*< hkbStateListener > -->
                </array>
            </field>
            <field name="enterNotifyEvents"><pointer id="object0"/></field>
            <field name="exitNotifyEvents"><pointer id="object0"/></field>
            <field name="transitions"><pointer id="object0"/></field>
            <field name="generator"><pointer id="{pointer}"/></field>
            <field name="name"><string value="{name}"/></field>
            <field name="stateId"><integer value="{stateId}"/></field>
            <field name="probability"><real dec="1" hex="#3ff0000000000000"/></field>
            <field name="enable"><bool value="true"/></field>
        </record>
    </object>
    """
    return xml_stateinfo
    
def modify_transition_attack(xml_file, object_id, new_transitions):
    # Read the XML file
    with open(xml_file, 'r') as f:
        lines = f.readlines()
    
    # Find the object500 section
    object_start = None
    object_end = None
    for i, line in enumerate(lines):
        if f'<object id="{object_id}"' in line:
            object_start = i
        elif object_start is not None and '</object>' in line:
            object_end = i
            break
    
    if object_start is None or object_end is None:
        print(f"错误:无法找到object {object_id}")
        return
    
    # Find the transitions array within object500
    array_start = None
    array_end = None
    for i in range(object_start, object_end):
        if '<field name="transitions">' in lines[i]:
            # Find the opening array tag (could be same line or next line)
            if '<array ' in lines[i]:
                array_start = i
            else:
                array_start = i + 1
            
            # Find the closing array tag
            indent = lines[array_start][:lines[array_start].find('<')]
            for j in range(array_start, object_end):
                if f'{indent}</array>' in lines[j]:
                    array_end = j
                    break
            break
    
    if array_start is None or array_end is None:
        print("错误: 无法找到transitions array")
        return
    
    # Extract current count
    array_line = lines[array_start]
    count_start = array_line.find('count="') + 7
    count_end = array_line.find('"', count_start)
    current_count = int(array_line[count_start:count_end])
    new_count = current_count + len(new_transitions)
    
    # Update the count in the array tag
    lines[array_start] = array_line.replace(
        f'count="{current_count}"',
        f'count="{new_count}"'
    )
    
    # Prepare new transition entries
    new_entries = []
    for transition in new_transitions:
        new_entry = f"""\
        <record> <!-- hkbStateMachine::TransitionInfo -->
            <field name="triggerInterval">
              <record> <!-- hkbStateMachine::TimeInterval -->
                <field name="enterEventId"><integer value="-1"/></field>
                <field name="exitEventId"><integer value="-1"/></field>
                <field name="enterTime"><real dec="0" hex="#0"/></field>
                <field name="exitTime"><real dec="0" hex="#0"/></field>
              </record>
            </field>
            <field name="initiateInterval">
              <record> <!-- hkbStateMachine::TimeInterval -->
                <field name="enterEventId"><integer value="-1"/></field>
                <field name="exitEventId"><integer value="-1"/></field>
                <field name="enterTime"><real dec="0" hex="#0"/></field>
                <field name="exitTime"><real dec="0" hex="#0"/></field>
              </record>
            </field>
            <field name="transition"><pointer id="{transition['target']}"/></field>
            <field name="condition"><pointer id="object0"/></field>
            <field name="eventId"><integer value="{transition['attack_id']}"/></field>
            <field name="toStateId"><integer value="{transition['state_id']}"/></field>
            <field name="fromNestedStateId"><integer value="0"/></field>
            <field name="toNestedStateId"><integer value="0"/></field>
            <field name="priority"><integer value="0"/></field>
            <field name="flags"><integer value="3584"/></field>
          </record>"""
        new_entries.extend([line + '\n' for line in new_entry.split('\n')])
    
    # Insert new entries before the closing array tag
    lines[array_end:array_end] = new_entries
    
    # Write the modified file
    with open(xml_file, 'w') as f:
        f.writelines(lines)
    
    print(f"成功添加{anim_attackid}的transitions. 对应count: {new_count}")

def modify_transition_event(xml_file, object_id, new_transitions):
    # Read the XML file
    with open(xml_file, 'r') as f:
        lines = f.readlines()
    
    # Find the object500 section
    object_start = None
    object_end = None
    for i, line in enumerate(lines):
        if f'<object id="{object_id}"' in line:
            object_start = i
        elif object_start is not None and '</object>' in line:
            object_end = i
            break
    
    if object_start is None or object_end is None:
        print(f"错误:无法找到object {object_id}")
        return
    
    # Find the transitions array within object500
    array_start = None
    array_end = None
    for i in range(object_start, object_end):
        if '<field name="transitions">' in lines[i]:
            # Find the opening array tag (could be same line or next line)
            if '<array ' in lines[i]:
                array_start = i
            else:
                array_start = i + 1
            
            # Find the closing array tag
            indent = lines[array_start][:lines[array_start].find('<')]
            for j in range(array_start, object_end):
                if f'{indent}</array>' in lines[j]:
                    array_end = j
                    break
            break
    
    if array_start is None or array_end is None:
        print("错误: 无法找到transitions array")
        return
    
    # Extract current count
    array_line = lines[array_start]
    count_start = array_line.find('count="') + 7
    count_end = array_line.find('"', count_start)
    current_count = int(array_line[count_start:count_end])
    new_count = current_count + len(new_transitions)
    
    # Update the count in the array tag
    lines[array_start] = array_line.replace(
        f'count="{current_count}"',
        f'count="{new_count}"'
    )
    
    # Prepare new transition entries
    new_entries = []
    for transition in new_transitions:
        new_entry = f"""\
        <record> <!-- hkbStateMachine::TransitionInfo -->
            <field name="triggerInterval">
              <record> <!-- hkbStateMachine::TimeInterval -->
                <field name="enterEventId"><integer value="-1"/></field>
                <field name="exitEventId"><integer value="-1"/></field>
                <field name="enterTime"><real dec="0" hex="#0"/></field>
                <field name="exitTime"><real dec="0" hex="#0"/></field>
              </record>
            </field>
            <field name="initiateInterval">
              <record> <!-- hkbStateMachine::TimeInterval -->
                <field name="enterEventId"><integer value="-1"/></field>
                <field name="exitEventId"><integer value="-1"/></field>
                <field name="enterTime"><real dec="0" hex="#0"/></field>
                <field name="exitTime"><real dec="0" hex="#0"/></field>
              </record>
            </field>
            <field name="transition"><pointer id="{transition['target']}"/></field>
            <field name="condition"><pointer id="object0"/></field>
            <field name="eventId"><integer value="{transition['event_id']}"/></field>
            <field name="toStateId"><integer value="{transition['state_id']}"/></field>
            <field name="fromNestedStateId"><integer value="0"/></field>
            <field name="toNestedStateId"><integer value="0"/></field>
            <field name="priority"><integer value="0"/></field>
            <field name="flags"><integer value="3584"/></field>
          </record>"""
        new_entries.extend([line + '\n' for line in new_entry.split('\n')])
    
    # Insert new entries before the closing array tag
    lines[array_end:array_end] = new_entries
    
    # Write the modified file
    with open(xml_file, 'w') as f:
        f.writelines(lines)
    
    print(f"成功添加{anim_eventid}的transitions. 对应count: {new_count}")

def largest_to_state_id():
    """
    Parses 'new_c9997.xml' and finds the largest integer value within:
    <field name="toStateId"><integer value="X"/></field>
    """
    tree = ET.parse(new_c9997_path)
    root = tree.getroot()
    max_value = -1
    
    for field in root.findall('.//field[@name="toStateId"]/integer'):
        value = field.get('value')
        if value is not None:
            try:
                max_value = max(max_value, int(value))
            except ValueError:
                continue  # Skip invalid values

    return max_value

def last_obj():
    """
    Uses XML e tools and returns last object in XML. 
    This is the only function that uses XML e tools.
    """
    tree = ET.parse(new_c9997_path)
    root = tree.getroot()
    last_num = -1
    #last_full_id = None
    
    for obj in root.findall('.//object'):
        obj_id = obj.get('id')
        if obj_id and obj_id.startswith('object'):
            try:
                current_num = int(obj_id[6:])
                if current_num > last_num:
                    last_num = current_num
                    #last_full_id = obj_id
            except ValueError:
                continue
    
    return last_num
def append_xml(content):
    """
    Appends string at the end of the xml file, right before the hktagfile.
    """
    #   Read the entire file
    with open(new_c9997_path, 'r') as f:
        lines = f.readlines()
    
    #   Find the last line containing </hktagfile>
    hktagfile_pos = None
    for i, line in enumerate(reversed(lines)):
        if '</hktagfile>' in line:
            hktagfile_pos = len(lines) - i - 1
            break
    
    if hktagfile_pos is None:
        raise ValueError("</hktagfile> tag 在文本中未找到")
    
    #   Insert our content before this line, maintaining original indentation
    indent = lines[hktagfile_pos][:lines[hktagfile_pos].find('</hktagfile>')]
    formatted_content = indent + content.rstrip('\n') + '\n'
    
    # Insert the new content
    lines.insert(hktagfile_pos, formatted_content)
    
    # Write the modified file back
    with open(new_c9997_path, 'w') as f:
        f.writelines(lines)

def find_line(start_pattern, direction='down', target_pattern=None, stop_pattern=None):
    """
    Searches new_c9997.xml for a line matching start_pattern or starts at a given line number,
    then looks up/down for another line.

    Args:
        start_pattern: String, list of strings, or integer. If an integer, it represents the starting line number.
        direction: 'up' or 'down' to search from the starting point.
        target_pattern: String or list of strings to find in the search direction.
        stop_pattern: String or list of strings that will stop the search if encountered.

    Returns:
        tuple: (found_line_number, found_line_content) or (None, None)
    """
    def pattern_match(line, patterns):
        if patterns is None:
            return False
        if isinstance(patterns, str):
            return patterns in line
        return any(p in line for p in patterns)
    
    with open(new_c9997_path, 'r') as f:
        lines = f.readlines()
    
    # Determine starting line number
    if isinstance(start_pattern, int):
        if 0 <= start_pattern < len(lines):
            start_line = start_pattern
        else:
            return None, None
    else:
        start_line = next((i for i, line in enumerate(lines) 
                          if pattern_match(line, start_pattern)), None)
    
    if start_line is None:
        return None, None
    
    # Determine search range
    if direction == 'up':
        search_range = range(start_line - 1, -1, -1)  # To start of file
    else:
        search_range = range(start_line + 1, len(lines))  # To end of file
    
    # Search in the specified direction
    for i in search_range:
        current_line = lines[i]
        
        if pattern_match(current_line, stop_pattern):
            return None, None
            
        if pattern_match(current_line, target_pattern):
            return i, current_line.strip()
    
    return None, None
def add_pointer_to_array(start_object_id: str,new_pointer_ids: list,file_path: str = "new_c9997.xml") -> bool:
    """
    Adds new pointer entries to an array before the closing </array> tag.
    
    Args:
        start_object_id: Existing pointer ID to locate the array (e.g. "object490")
        new_pointer_ids: List of new IDs to add (e.g. ["object500", "object501"])
        file_path: Path to XML file
        
    Returns:
        bool: True if successful, False if failed
    """
    with open(new_c9997_path, 'r+') as f:
        lines = f.readlines()
        f.seek(0)
        array_start = -1
        array_end = -1
        indent = "          "  # Match your indentation
        
        # Find the array containing the start_object_id
        for i, line in enumerate(lines):
            if start_object_id in line:
                # Search backward for array start
                for j in range(i, -1, -1):
                    if '<array count=' in lines[j]:
                        array_start = j
                        break
                # Search forward for array end
                for j in range(i, len(lines)):
                    if '</array>' in lines[j]:
                        array_end = j
                        break
                break
        
        if array_start == -1 or array_end == -1:
            return False
        
        # Update array count
        count_line = lines[array_start]
        old_count = int(count_line.split('count="')[1].split('"')[0])
        new_count = old_count + len(new_pointer_ids)
        lines[array_start] = count_line.replace(
            f'count="{old_count}"',
            f'count="{new_count}"'
        )
        
        # Insert new pointers before </array>
        new_lines = [f'{pid}\n' for pid in new_pointer_ids]
        lines[array_end:array_end] = new_lines
        
        # Write modified content
        f.writelines(lines)
        f.truncate()
        return True
def filter(line, search_str='="'):
    """
    Filters all the text from the selected line, except for keywords such as array count or "objectXXX"
    """
    if line is not None:
        id_start = line.find(search_str) + len(search_str)
        id_end = line.find('"', id_start)
        return line[id_start:id_end]
    return "Not found."

def add_event(anim_id):
    #   Variables for text generation. Uses aXXX variation.
    global aXXX, anim_attackid, anim_eventid
    aXXX = str(aXXX)
    with open(event_names_path, "r") as file:
        content = file.read()
    event_names_list = re.findall(r'"(.*?)"', content)
    anim_id = str(anim_id)
    anim_attackid = "W_Attack" + anim_id
    anim_eventid = "W_Event" + anim_id
    name = "Attack" + anim_id
    animationName = "a" + aXXX + "00_00" + anim_id
    csmg_name = name + "_CMSG"
    clipgen_name = animationName + "_hkx_AutoSet_0" + aXXX
    #   Find largest possible state_id and increment by 1
    state_id = largest_to_state_id() + 1
    #   Object IDs. Sets of each animation entry will always be by 3.
    clip_gen_id = "object" + str(last_obj() + 1)
    csmg_id = "object" + str(last_obj() + 2)
    stateinfo_id = "object" + str(last_obj() + 3)
    #   Potentially unused?
    animInternalId = animationid_count(animationName)
    userData = 1
    #   New pointer and transition text entries. Will probably be used later to add all entries in 1 search, but i'm too lazy for now.
    new_pointer_ids=[f'          <pointer id="{stateinfo_id}"/>']
    new_transitions = [
        {
            "target": "object10",
            "attack_id": find_event_index(anim_attackid, event_names_list),
            "event_id": find_event_index(anim_eventid, event_names_list),
            "state_id": state_id
        }
    ]
    check_clip_gen_num, check_clip_gen_line = find_line(start_pattern= 0,direction='down',target_pattern=f'string value="{animationName}"')
    #   Check if there is pre-existing clipgen
    if check_clip_gen_line is None:
        #   FIND PARENT STATEINFO OF 3000
        line_num, stateinfo_line = find_line(
        start_pattern=['<field name="name"><string value="Attack3000"/></field>'],
        direction='up',
        target_pattern=' <object id='
        )
        #   FIND WILDCARD OBJECT ID
        wildcard_num, wildcard_line = find_line(
        start_pattern=['<pointer id="' + filter(stateinfo_line) + '"/>'],
        direction='down',
        target_pattern='<field name="wildcardTransitions"><pointer id='
        )
        #print(filter(wildcard_line, 'id="'))
        #   FIND TRANSITION ARRAY
        transition_num, transition_line = find_line(
        start_pattern= 0,
        direction='down',
        target_pattern='  <object id="' + filter(wildcard_line, 'id="')
        )
        #print(transition_num, transition_line)
        #   APPEND OBJECTS
        append_xml(generate_clip_gen(clip_gen_id, clipgen_name, animationName, animInternalId))
        #   Check to see if there is pre-existing CMSG.
        check_cmsg_num, check_cmsg_line = find_line(start_pattern= 0, direction='down', target_pattern=f'string value="{csmg_name}"')
        if check_cmsg_line is None:
            print(csmg_name + " 不存在. 生成 CMSG 和 stateinfo object中. parent stateinfoArray添加数据中. transitionArray修改中.")
             #   ADD NEW OBJECT POINTERS TO PARENT STATEINFO ARRAY
            add_pointer_to_array(f'          <pointer id="{filter(stateinfo_line)}"/>', new_pointer_ids)
            #   MODIFY TRANSITION ARRAY WITH NEW TRANSITIONS
            modify_transition_attack(new_c9997_path, filter(wildcard_line, 'id="'), new_transitions)
            modify_transition_event(new_c9997_path, filter(wildcard_line, 'id="'), new_transitions)
            #   If there is NO pre-existing CMSG, just append CMSG and stateinfo obj normally.
            append_xml(generate_csmg(csmg_id, csmg_name, userData, clip_gen_id, anim_id))
            append_xml(generate_stateinfo(stateinfo_id, name, csmg_id, state_id))
        else:
            print(csmg_name + "已存在. 修改添加CMSG array中")
            #   If there is pre-existing CMSG, find the array and append the stateinfo obj
            check_cmsg_arr_num, check_cmsg_arr_line = find_line(
            start_pattern= check_cmsg_num,
            direction='down',
            target_pattern=f'<pointer id="')
            clip_gen_pointer_id=[f'          <pointer id="{clip_gen_id}"/>']
            add_pointer_to_array(check_cmsg_arr_line, clip_gen_pointer_id)
            #append_xml(generate_stateinfo(stateinfo_id, name, csmg_id, state_id))
    else:
        #   Cancel the appending
        print(animationName + ".hkx已存在.")

def find_event_index(event_number, event_names):
    '''
    Finds event_id from event_names list for transitionArray.
    '''
    #   Convert the event number param to a str
    search_str = str(event_number)
    #   For each line in event_names list...
    for index, name in enumerate(event_names):
        #   If search_str matches the name of the current line, return that line index.
        if search_str in name:
            #print(index)
            return index
    #   Return -1 if not found
    return -1  

def count_existing_strings(lines):
    """数注册的hkx个数,用于填写hkx"""
    hkx_count = 0
    last_index = -1
    for i, line in enumerate(lines):
        if '<string value="..\\..\\..\\..\\..\\Model\\chr\\c9997\\hkx' in line:
            hkx_count += 1
            last_index = i
    print(f"原文件已注册hkx个数:"+str(hkx_count))
    return hkx_count, last_index

def insert_new_strings(lines, last_index, Axxx, start_value, end_value):
    """在末尾注册 hkx"""
    new_strings = []
    existing_strings = set(line.strip() for line in lines if '          <string value="' in line)
    for i in range(start_value, end_value + 1):
        new_string = f'          <string value="..\\..\\..\\..\\..\\Model\\chr\\c9997\\hkx\\a{str(Axxx)}00\\a{str(Axxx)}00_{i:06d}.hkx"/>\n'
        if new_string.strip() in existing_strings:
            existing_hkx_name = f'a{str(Axxx)}00_{i:06d}'
            print(f"重复注册动作编号: {existing_hkx_name}.hkx")
        else:
            new_strings.append(new_string)
            existing_strings.add(new_string.strip())
    lines_with_new_strings = lines[:last_index+1] + new_strings + lines[last_index+1:]
    return lines_with_new_strings


def update_first_array_count(lines):
    """读取注册后的hkx计数后将原本的hkx计数替换"""
    field_tag_found = False
    updated_lines = []
    new_hkx_count = 0
    for i, line in enumerate(lines):
        if '<string value="..\\..\\..\\..\\..\\Model\\chr\\c9997\\hkx' in line:
            new_hkx_count += 1
    for line in lines:
        if '<field name="animationNames">' in line:
            field_tag_found = True
        if field_tag_found and '<array count="' in line:
            line = re.sub(r'<array count="\d+"', f'<array count="{new_hkx_count}"', line, count=1)
            field_tag_found = False
        updated_lines.append(line)
    print(f"新文件已注册hkx数:"+str(new_hkx_count))
    return updated_lines

def hkx_register():
    Axxx = entry1.get()
    start_value = int(entry2.get())
    if entry3.get() == "":
        end_value = start_value
    else:
        end_value = int(entry3.get())
    with open(new_c9997_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    print(f"开始hkx注册")
    hkx_count, last_index = count_existing_strings(lines)
    lines_with_new_strings = insert_new_strings(lines, last_index, Axxx, start_value, end_value)
    updated_lines = update_first_array_count(lines_with_new_strings)
    with open(new_c9997_path, 'w', encoding='utf-8') as file:
        file.writelines(updated_lines)
    print(f"hkx注册完成,事件可调用")

def select_file():
    global selected_file_path, gyzcount, selected_file_path_one, new_c9997_path, folder_path
    gyzcount = 0
    filepath = filedialog.askopenfilename(
        title="选择c9997.xml",
        filetypes=[("XML Files", "*.xml")]
    )
    if filepath:
        if os.path.basename(filepath) != "c9997.xml":
            messagebox.showerror("错误", "文件必须为c9997.xml")
            selected_file_path = None
        else:
            selected_file_path = filepath
            selected_file_path_one = selected_file_path
            folder_path = os.path.dirname(selected_file_path_one)
            new_c9997_path = os.path.join(folder_path, "new_c9997.xml")
            shutil.copy(selected_file_path_one, new_c9997_path)
            messagebox.showinfo("成功", f"c9997.xml已选择")


def event_names(input_file_path):
    input_dir = os.path.dirname(input_file_path)
    output_file_path = os.path.join(input_dir, 'event_names.txt')
    with open(input_file_path, 'r', encoding='utf-8') as file:
        xml_data = file.read()
    start_tag = '<field name="eventNames">'
    end_tag = '</field>'
    start_index = xml_data.find(start_tag)
    end_index = xml_data.find(end_tag, start_index) + len(end_tag)
    field_content = xml_data[start_index:end_index]
    root = ET.fromstring(field_content)
    event_names = [elem.attrib['value'] for elem in root.findall(".//string")]

    converted_content = 'event_names = [\n'
    for name in event_names:
        converted_content += f'    "{name}",\n'
    converted_content += ']'

    lines = converted_content.splitlines()
    lines = [line for line in lines if line.strip() != 'event_names = [' and line.strip() != ']']

    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write('event_names = [\n')
        for idx, line in enumerate(lines):
            line = line.strip().replace("\"", "")
            line = line.rstrip(',')
            if line:
                file.write(f'    {idx} = "{line}",\n')
        file.write(']\n')

    print(f"已将注册的event name全部导出到eventNames.txt中")

def animationid_count(animationName):
    with open(new_c9997_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    animation_start_index = -1
    animation_end_index = -1
    animationName_index = -1
    for index, line in enumerate(lines):
        if '<field name="animationNames">' in line:
            animation_start_index = index + 1 
            break
    for index in range(animation_start_index, len(lines)):
        if '</field>' in lines[index]:
            animation_end_index = index + 1
            break
    for index in range(animation_start_index, animation_end_index):
        if animationName in lines[index]:
            animationName_index = index + 1
            break
    animationid = animationName_index - animation_start_index - 2
    return(animationid)
    
def show_welcome_window():
    welcome_window = tk.Toplevel()
    welcome_window.title("只狼NPC动作注册工具V0.0")

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 600
    window_height = 600
    position_top = int((screen_height - window_height) / 2)
    position_left = int((screen_width - window_width) / 2)
    welcome_window.geometry(f'{window_width}x{window_height}+{position_left}+{position_top}')

    font1 = ('Times New Roman', 12)
    font2 = ('Times New Roman', 14)
    label = tk.Label(welcome_window, text="欢迎使用只狼NPC动作注册工具!当前工具版本V0.1\n本工具由只狼复兴mod作者制作,由Last孤影众汉化优化打包", font=font1)
    label.pack(pady=5)
    label = tk.Label(welcome_window, text="本工具可对任意敌人进行3000~3109动作注册,可AI和事件调用\n可在cmd窗口查看具体修改内容", font=font1)
    label.pack(pady=5)

    img = Image.open("hunfive.jpg")
    img = img.resize((400, 400), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(img)

    img_label = tk.Label(welcome_window, image=photo)
    img_label.photo = photo
    img_label.pack(pady=10)

    def on_confirm():
        welcome_window.destroy()
        root.deiconify()

    confirm_button = tk.Button(welcome_window, text="确定", command=on_confirm, font=font2)
    confirm_button.pack()
    welcome_window.protocol("WM_DELETE_WINDOW", lambda: (welcome_window.destroy(), root.deiconify()))
    
    welcome_window.mainloop()

def submit():
    global gyzcount, folder_path, selected_file_path, event_names_path, new_c9997_path, new_c9997_file_path, selected_file_path_one
    gyzcount = gyzcount + 1
    gyzcount_name = str(gyzcount)
    if not selected_file_path:
        if not os.path.exists('c9997.xml'):
            messagebox.showinfo("错误！", f"错误:当前目录找不到文件c9997.xml")
            return
        else:
            selected_file_path = os.path.join(os.path.dirname(sys.argv[0]), "c9997.xml")
            selected_file_path_one = selected_file_path
            folder_path = os.path.dirname(selected_file_path_one)
            new_c9997_path = os.path.join(folder_path, "new_c9997.xml")
            shutil.copy(selected_file_path, new_c9997_path)
    event_names_path = os.path.join(folder_path, "event_names.txt")
    new_c9997_path = os.path.join(folder_path, "new_c9997.xml")
    tree = ET.parse(selected_file_path)
    root = tree.getroot()
    event_names(selected_file_path)
    result = process_arguments()
    hkx_register()
    if result:
        print("本次生成动作编号如下:", result)
        for entry in result:
            add_event(entry)
    else:
        print("没有找到有效的动作编号")
    
    selected_file_path = new_c9997_path
    print("当前生成动作次数："+ gyzcount_name + ", 可继续点击生成按钮在新文件基础上注册动作"+ '\n' + "若重新选择文件则重新注册动作")

global gyzcount
gyzcount = 0

root = tk.Tk()
root.title("只狼NPC动作注册工具")

root.geometry("600x400")

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
window_width = 600
window_height = 400
position_top = int((screen_height - window_height) / 2)
position_left = int((screen_width - window_width) / 2)
root.geometry(f'{window_width}x{window_height}+{position_left}+{position_top}')
font = ('Times New Roman', 14)

tk.Label(root, text="请输入动作组编号:例如输入3则生成a300", font=font).pack(pady=(20, 5))
entry1 = tk.Entry(root, font=font)
entry1.insert(0, "3")
entry1.pack(pady=5)

tk.Label(root, text="请输入起始动作编号(3000~3109)", font=font).pack(pady=(20, 5))
entry2 = tk.Entry(root, font=font)
entry2.insert(0, "3000")
entry2.pack(pady=5)

tk.Label(root, text="请输入结束动作编号(3000~3109)", font=font).pack(pady=(20, 5))
entry3 = tk.Entry(root, font=font)
entry3.insert(0, "")
entry3.pack(pady=5)

entries = [entry1, entry2, entry3]

button_frame = tk.Frame(root)
button_frame.pack(pady=10)

button1 = tk.Button(button_frame, text="选择文件", command=select_file, font=('Times New Roman', 14))
button1.pack(side='left', padx=20)

button2 = tk.Button(button_frame, text="生成", command=submit, font=('Times New Roman', 14))
button2.pack(side='right', padx=20)

root.withdraw() 
show_welcome_window()

root.mainloop()
