import re
import xml.etree.ElementTree as ET
import shutil

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
            <field name="name"><string value="{name}/></field>
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
    <object id={objectId}" typeid="type115" > <!-- hkbStateMachine::StateInfo -->
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

"""
Finds the Attack3000 stateinfo objectId so that the next function can find the parent stateinfo array for attacks.
"""
def find_parent_stateinfo_object():
    # Dictionary to store parent references
    parent_map = {child: parent for parent in root.iter() for child in parent}

    # Find the <field> element with name="name" and value="Attack3000"
    for field in root.findall(".//field[@name='name']"):
        string_element = field.find("string")
        if string_element is not None and string_element.attrib.get("value") == "Attack3000":
            print("Found target field:", ET.tostring(field, encoding='unicode'))

            # Find the enclosing <object> by traversing up using parent_map
            object_element = field
            while object_element in parent_map:
                object_element = parent_map[object_element]
                if object_element.tag == "object":
                    object_id = object_element.attrib.get("id")  # Extract object ID
                    print(f"Found enclosing object with ID: {object_id}")
                    return object_id
"""    
Holy fuck this is scuffed. 
No longer uses XML e tree and just uses simple line counting and it writes to the new_c9997.xml.
This edits the parent stateinfo array to increase the count and add new object list.
This also returns the wildcard object id, which will be used for modify_transition
"""
def edit_parent_stateinfo(search_id, new_pointers):
    # Read XML as text to preserve structure
    with open("new_c9997.xml", "r") as f:
        lines = f.readlines()
    
    # Find the array and add new pointers
    for i, line in enumerate(lines):
        if f'<pointer id="{search_id}"' in line:
            # Find the closing </array> tag
            array_end = None
            for j in range(i, len(lines)):
                if "</array>" in lines[j]:
                    array_end = j
                    break
            
            if array_end is None:
                print("Error: </array> tag not found.")
                return
            
            # Insert new pointers before </array>
            new_lines = []
            for pointer_id in new_pointers:
                new_lines.append(f'          <pointer id="{pointer_id}" />\n')
            lines[array_end:array_end] = new_lines
            
            # Update array count
            for k, line in enumerate(lines):
                if "<array count=" in line and "</array>" in lines[k+1]:
                    old_count = int(line.split('count="')[1].split('"')[0])
                    line = line.replace(f'count="{old_count}"', f'count="{old_count + len(new_pointers)}"')
                    lines[k] = line
                    break
            
            # Find wildcardTransitions (search after </array>)
            wildcard_id = None
            for m in range(array_end + len(new_pointers), len(lines)):
                if "<field name=\"wildcardTransitions\">" in lines[m]:
                    # Extract ID even if it's in the same line
                    if "<pointer id=" in lines[m]:
                        wildcard_id = lines[m].split('id="')[1].split('"')[0]
                    break
            
            if wildcard_id:
                print(f"Found wildcardTransitions ID: {wildcard_id}")
            else:
                print("Warning: wildcardTransitions not found after </array>")
            
            # Save changes
            with open("new_c9997.xml", "w") as f:
                f.writelines(lines)
            print("Modified XML saved.")
            return wildcard_id
    
    print("Pointer not found in any array.")
    
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
    with open('modified_' + xml_file, 'w') as f:
        f.writelines(lines)
    
    print(f"Successfully added {len(new_transitions)} transitions. New count: {new_count}")

"""
Uses XML e tools and returns last object.
"""
def find_last_object_id(xml_file):
    #tree = ET.parse(xml_file)
    #root = tree.getroot()
    
    last_id = None
    max_num = -1
    
    for obj in root.findall('.//object'):
        obj_id = obj.get('id')
        if obj_id and obj_id.startswith('object'):
            try:
                current_num = int(obj_id[6:])  # Extract number after "object"
                if current_num > max_num:
                    max_num = current_num
                    last_id = obj_id
            except ValueError:
                continue
                
    return last_id

def add_event(anim_id):
    anim_id = str(anim_id)
    name = "Attack" + anim_id
    animationName = "a000_00" + anim_id
    csmg_name = name + "_CSMG"
    stateinfo_name = name + "_hkx_AutoSet_00"
    print(name)
    print(animationName)
    print(csmg_name)
    print(stateinfo_name)

add_event(3010)

# Example usage:
new_transitions = [
    {"target": "object10", "event_id": "8", "state_id": "2"},
    {"target": "object10", "event_id": "9", "state_id": "3"}
]
    
# Example usage
""" clip_gen = generate_clip_gen("object1300", "a000_003052_hkx_AutoSet_00", "a000_003052", "364")
csmg = generate_csmg("object1301", "Attack3052_CMSG", "21168132", "object1300", "3052")
stateinfo = generate_stateinfo("object1302", "Attack3052", "object1301", "107")
print(clip_gen)
print(csmg)
print(stateinfo) """
#find_parent_stateinfo_object()
new_entries = ["object2001", "object2002"]
modify_transition('new_c9997.xml', edit_parent_stateinfo(find_parent_stateinfo_object(), new_entries), new_transitions)

last_id = find_last_object_id('new_c9997.xml')
print(f"The last object ID is: {last_id}")