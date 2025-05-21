import xml.etree.ElementTree as ET
from xml_parser import XMLParser

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
if __name__ == "__main__":
    xml_file = 'c0000.xml'  # Update this with your XML file path
    parser = XMLParser(xml_file)
    
    #   Find selected object
    obj_data, traced_objects = parser.find_object_by_name("a050_300040")

    a_offset = f"050"
    new_anim_id = f"300050"
    new_csmg_name = f"GroundAttackCombo6_CMSG"
    new_clipgen_name = f"a{a_offset}_{new_anim_id}"
    new_stateinfo_name = f"GroundAttackCombo6"
    new_event_name = f"W_{new_stateinfo_name}"

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
        
    