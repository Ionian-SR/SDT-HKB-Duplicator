import re
import xml.etree.ElementTree as ET
import shutil
import sys

#   Read event_names.txt
with open("event_names.txt", "r") as file:
    content = file.read()

#   Regex to find all items between '""' and put them into matches as a list.
event_names_list = re.findall(r'"(.*?)"', content)  

# Load XML file
tree = ET.parse("c9997.xml")
root = tree.getroot()

#   Dupe c9997
shutil.copy("c9997.xml", "new_c9997.xml")

def process_arguments():
    """
    Processes command line arguments and returns a validated list of numbers between 3000-3110.
    Supports single numbers or ranges (e.g., 3010 or 3010 3020).
    """
    args = sys.argv[1:]  # Skip script name
    
    if not args:
        print("Usage: python3 code.py <start> [end]")
        print("Example: python3 code.py 3010")
        print("Example: python3 code.py 3010 3020")
        sys.exit(1)
    
    try:
        # Convert to integers
        numbers = [int(arg) for arg in args]
    except ValueError:
        print("Error: All arguments must be numbers")
        sys.exit(1)
    
    # Validate single number
    if len(numbers) == 1:
        num = numbers[0]
        if 3000 <= num <= 3110:
            return [num]
        print(f"Ignoring {num} - must be between 3000-3110")
        return []
    
    # Validate range
    elif len(numbers) == 2:
        start, end = sorted(numbers)  # Handle reverse order automatically
        if start < 3000 or end > 3110:
            print("Both numbers must be between 3000-3110")
            return []
        return list(range(start, end + 1))
    
    else:
        print("Error: Too many arguments (max 2)")
        return []

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
    
def modify_transition(xml_file, object_id, new_transitions):
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
        print(f"Error: Could not find object {object_id}")
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
        print("Error: Could not find transitions array")
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
    
    print(f"Successfully added {len(new_transitions)} transitions. New count: {new_count}")

def last_obj():
    """
    Uses XML e tools and returns last object in XML. 
    This is the only function that uses XML e tools.
    """
    tree = ET.parse("new_c9997.xml")
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
    with open("new_c9997.xml", 'r') as f:
        lines = f.readlines()
    
    #   Find the last line containing </hktagfile>
    hktagfile_pos = None
    for i, line in enumerate(reversed(lines)):
        if '</hktagfile>' in line:
            hktagfile_pos = len(lines) - i - 1
            break
    
    if hktagfile_pos is None:
        raise ValueError("</hktagfile> tag not found in file")
    
    #   Insert our content before this line, maintaining original indentation
    indent = lines[hktagfile_pos][:lines[hktagfile_pos].find('</hktagfile>')]
    formatted_content = indent + content.rstrip('\n') + '\n'
    
    # Insert the new content
    lines.insert(hktagfile_pos, formatted_content)
    
    # Write the modified file back
    with open("new_c9997.xml", 'w') as f:
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
    
    with open("new_c9997.xml", 'r') as f:
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
    with open(file_path, 'r+') as f:
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
    anim_id = str(anim_id)
    name = "Attack" + anim_id
    animationName = "a000_00" + anim_id
    csmg_name = name + "_CMSG"
    #stateinfo_name = name + "_hkx_AutoSet_00"
    clipgen_name = animationName + "_hkx_AutoSet_00"
    animInternalId = 1
    #userData = 21168131
    userData = 1
    state_id = 999
    clip_gen_id = "object" + str(last_obj() + 1)
    csmg_id = "object" + str(last_obj() + 2)
    stateinfo_id = "object" + str(last_obj() + 3)
    new_pointer_ids=[f'          <pointer id="{stateinfo_id}"/>']
    new_transitions = [
        {
            "target": "object10",
            "event_id": find_event_index(anim_id, event_names_list),
            "state_id": state_id
        }
    ]
    
    #   FIND PARENT STATEINFO OF 3000
    line_num, stateinfo_line = find_line(
    start_pattern=['<field name="name"><string value="Attack3000"/></field>'],
    direction='up',
    target_pattern=' <object id='
    )
    print(filter(stateinfo_line))
    #   ADD NEW OBJECT POINTERS TO PARENT STATEINFO ARRAY
    add_pointer_to_array(f'          <pointer id="{filter(stateinfo_line)}"/>', new_pointer_ids)
    #   FIND WILDCARD OBJECT ID
    wildcard_num, wildcard_line = find_line(
    start_pattern=['<pointer id="' + filter(stateinfo_line) + '"/>'],
    direction='down',
    target_pattern='<field name="wildcardTransitions"><pointer id='
    )
    print(filter(wildcard_line, 'id="'))
    #   FIND TRANSITION ARRAY
    transition_num, transition_line = find_line(
    start_pattern= 0,
    direction='down',
    target_pattern='  <object id="' + filter(wildcard_line, 'id="')
    )
    print(transition_num, transition_line)
    modify_transition('new_c9997.xml', filter(wildcard_line, 'id="'), new_transitions)
    append_xml(generate_clip_gen(clip_gen_id, clipgen_name, animationName, animInternalId))
    append_xml(generate_csmg(csmg_id, csmg_name, userData, clip_gen_id, anim_id))
    #print(stateinfo_name)
    append_xml(generate_stateinfo(stateinfo_id, name, csmg_id, state_id))

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
            print(index)
            return index
    #   Return -1 if not found
    return -1  

#####################
if __name__ == "__main__":
    result = process_arguments()
    if result:
        print("Valid numbers to process:", result)
        for entry in result:
            add_event(entry)
    else:
        print("No valid numbers found")
    #add_event(3010)