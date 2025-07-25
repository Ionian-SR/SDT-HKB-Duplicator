
from lxml import etree

class XMLParser:
    def __init__(self, xml_file):
        self.xml_file = xml_file
        parser = etree.XMLParser(remove_blank_text=False)
        self.tree = etree.parse(xml_file, parser)
        self.root = self.tree.getroot()

    def find_array_count(self, obj_id, field_name):
        """
        Finds the <array> count within the specified field and object.

        Args:
            obj_id (str): The ID of the object containing the field.
            field_name (str): The name of the field containing the array.

        Returns:
            int: The count of elements in the array, or -1 if not found.
        """
        # Locate the specific object by ID
        obj = self.root.find(f".//object[@id='{obj_id}']")

        if obj is not None:
            # Locate the specified field with an <array>
            for field in obj.findall(f".//field[@name='{field_name}']"):
                array = field.find("array")
                if array is not None:
                    count = int(array.attrib.get("count", "0"))
                    return count

            print(f"Field '{field_name}' not found or does not contain an <array> in object '{obj_id}'.")
            return -1

        print(f"Object with ID '{obj_id}' not found.")
        return -1

    def append_to_array(self, obj_id, field_name, new_element, is_pointer=False):
        """
        Appends a new element to the <array> inside the specified field within a specific object.
        Updates the count attribute accordingly.

        Args:
            obj_id (str): The ID of the object containing the field.
            field_name (str): The name of the field containing the array.
            new_element (str, etree._Element): The value to append (string for <string>, pointer ID for <pointer>, or XML element).
            is_pointer (bool): If True, the new value will be added as a <pointer>.
        """
        # Locate the object by ID
        obj = self.root.find(f".//object[@id='{obj_id}']")

        if obj is not None:
            # Locate the specified field within the object
            for field in obj.findall(f".//field[@name='{field_name}']"):
                array = field.find("array")
                if array is not None:
                    
                    # Current count of elements in the array
                    current_count = int(array.attrib.get("count", "0"))

                    # Handle XML Element directly
                    if isinstance(new_element, etree._Element):
                        # Directly append the new XML node
                        array.append(new_element)

                    elif is_pointer:
                        # Append as <pointer>
                        etree.SubElement(array, "pointer", id=str(new_element))

                    else:
                        # Append as <string>
                        etree.SubElement(array, "string", value=str(new_element))

                    # Update the count attribute
                    new_count = current_count + 1
                    array.set("count", str(new_count))

                    print(f"Appended to '{field_name}' in object '{obj_id}'. New count: {new_count}")
                    return

                print(f"Field '{field_name}' not found or does not contain an <array> in object '{obj_id}'.")
        else:
            print(f"Object with ID '{obj_id}' not found.")

    def get_largest_obj(self):
        last_num = -1
        for obj in self.root.findall('.//object'):
            obj_id = obj.get('id')
            if obj_id and obj_id.startswith('object'):
                try:
                    current_num = int(obj_id[6:])
                    if current_num > last_num:
                        last_num = current_num
                except ValueError:
                    continue
        return last_num
    
    def get_largest_toStateId(self):
        max_value = -1
        for field in self.root.findall('.//field[@name="toStateId"]/integer'):
            value = field.get('value')
            if value is not None:
                try:
                    max_value = max(max_value, int(value))
                except ValueError:
                    continue  # Skip invalid values

        return max_value
    
    def get_largest_userData(self):
        max_value = -1
        for field in self.root.findall('.//field[@name="userData"]/integer'):
            value = field.get('value')
            if value is not None:
                try:
                    max_value = max(max_value, int(value))
                except ValueError:
                    continue  # Skip invalid values

        return max_value

    def collect_object_data(self, obj):
        """
        Collects all data fields, including nested structures like <array>.
        """
        obj_data = {
            "id": obj.attrib["id"],
            "typeid": obj.attrib.get("typeid"),
            "fields": {}
        }

        for field in obj.findall(".//field"):
            field_name = field.attrib["name"]
            field_value = None

            # Check for nested <array> structure
            array_element = field.find("array")
            if array_element is not None:
                array_data = {
                    "type": "array",
                    "count": int(array_element.attrib.get("count", "0")),
                    "elementtypeid": array_element.attrib.get("elementtypeid"),
                    "items": []
                }
                # Collect array items
                for item in array_element.findall("pointer"):
                    item_id = item.attrib.get("id")
                    if item_id:
                        array_data["items"].append({"type": "pointer", "id": item_id})

                # Assign array data to the field
                field_value = array_data

            # Handle string fields
            string_element = field.find("string")
            if string_element is not None:
                field_value = string_element.attrib["value"]

            # Handle integer fields
            integer_element = field.find("integer")
            if integer_element is not None:
                field_value = int(integer_element.attrib["value"])

            # Handle real/float fields
            real_element = field.find("real")
            if real_element is not None:
                field_value = float(real_element.attrib["dec"])

            # Handle bool fields
            bool_element = field.find("bool")
            if bool_element is not None:
                field_value = bool_element.attrib["value"] == "true"

            # Handle pointer fields (not inside an array)
            pointer_element = field.find("pointer")
            if pointer_element is not None and not array_element:
                field_value = {"type": "pointer", "id": pointer_element.attrib.get("id")}

            # Assign the field data
            if field_value is not None:
                obj_data["fields"][field_name] = field_value

        return obj_data

    def find_object_by_name(self, name_value):
        """
        Finds the object by its name and returns its data, along with all traced references.
        """
        for obj in self.root.findall(".//object"):
            for field in obj.findall(".//field[@name='name']/string"):
                if field.attrib['value'] == name_value:
                    obj_data = self.collect_object_data(obj)
                    print(f"Collected data for object '{name_value}'")
                    
                    # Get the list of traced objects
                    #traced_objects = self.trace_references(obj_data["id"])
                    #print(f"Traced objects: {traced_objects}")
                    return obj_data

        print(f"Object with name '{name_value}' not found.")
        return None

    def find_object_by_id(self, obj_id):
        """
        Finds the object by its ID and returns its data, along with all traced references.

        Args:
            obj_id (str): The ID of the object.

        Returns:
            tuple: (object_data, traced_references)
        """
        # Locate the object by its ID
        obj = self.root.find(f".//object[@id='{obj_id}']")
        
        if obj is not None:
            # Collect object data
            obj_data = self.collect_object_data(obj)
            print(f"Collected data for object ID '{obj_id}'")

            # return obj_data, traced_objects
            return obj_data

        print(f"Object with ID '{obj_id}' not found.")
        return None, []

    def find_object_by_field(self, xpath_string, index=0):
        #matches = self.root.findall(f".//{xpath_string}")
        
        for obj in self.root.findall(".//object"):
            for field in obj.findall(f'.//{xpath_string}'):
                #if field.attrib['value'] == name_value:
                obj_data = self.collect_object_data(obj)
                print(f"Collected data for object with field: '{xpath_string}'")
                
                # Get the list of traced objects
                #traced_objects = self.trace_references(obj_data["id"])
                #print(f"Traced objects: {traced_objects}")
                return obj_data#, traced_objects

    def find_transition_record_by_field_value(self, obj_id, field_name, target_value):
        obj = self.root.find(f".//object[@id='{obj_id}']")
        if obj is None:
            print(f"No object found with id '{obj_id}'")
            return None

        transitions_field = obj.find(".//field[@name='transitions']")
        if transitions_field is None:
            print("No 'transitions' field found in object.")
            return None

        array = transitions_field.find("array")
        if array is None:
            print("No array found inside 'transitions' field.")
            return None

        for record in array.findall("record"):
            target_field = record.find(f"./field[@name='{field_name}']/integer")
            if target_field is not None and target_field.get("value") == str(target_value):
                # Get the toStateId from the same record 
                transition_pointer_id = record.find("./field[@name='transition']/pointer")
                if transition_pointer_id is not None:
                    transition_pointer_id = transition_pointer_id.get("id")
                    print(f"Found transition pointer id: {transition_pointer_id}")
                    return transition_pointer_id
                else:
                    print(f"No transition pointer id found")
                    return None

        print(f"No record found with {field_name} = {target_value}")
        return None


    def _trace(self, obj_id, visited, referenced_objects, trace_limit=4):
        """
        Recursively traces objects that reference the given object ID.
        Stops tracing after the specified number of traces.
        """
        # Stop condition: Limit the total trace count
        if len(referenced_objects) >= trace_limit:
            print(f"Trace limit of {trace_limit} reached. Stopping trace.")
            return

        if obj_id in visited:
            return

        visited.add(obj_id)

        for obj in self.root.findall(".//object"):
            for pointer in obj.findall(".//pointer"):
                pointer_id = pointer.attrib.get('id')

                if pointer_id == obj_id:
                    obj_id_ref = obj.attrib["id"]

                    if obj_id_ref not in visited:
                        print(f"Object {obj_id_ref} references {obj_id}")
                        referenced_objects.append(obj_id_ref)
                        self._trace(obj_id_ref, visited, referenced_objects, trace_limit)

    def trace_references(self, obj_id, trace_limit=3):
        """
        Collects all objects that reference the given object ID, 
        but limits tracing to a maximum of trace_limit objects.
        """
        visited = set()
        referenced_objects = []
        self._trace(obj_id, visited, referenced_objects, trace_limit)
        return referenced_objects

    def duplicate_object(self, obj_data, new_name, config):
        """
        Duplicates the object using the unified 'fields' structure, 
        including handling of pointer fields and arrays.
        """
        new_clipgen_pointer_id = config.get("new_clipgen_pointer_id")
        new_cmsg_pointer_id = config.get("new_cmsg_pointer_id")
        new_stateinfo_pointer_id = config.get("new_stateinfo_pointer_id")

        new_clipgen_name = config.get("new_clipgen_name")
        new_cmsg_name = config.get("new_cmsg_name")
        new_stateinfo_name = config.get("new_stateinfo_name")
        new_event_name = config.get("new_event_name")

        new_toStateId = config.get("new_toStateId")
        new_userData = config.get("new_userData")
        new_animationInternalId = config.get("new_animationInternalId")
        new_anim_id = config.get("new_anim_id")

        # Generate new object ID
        new_id = f"object{self.get_largest_obj() + 1}"
        
        # Create the new object using lxml.etree
        new_obj = etree.Element("object", id=new_id, typeid=obj_data["typeid"])
        new_obj.text = "\n  "
        new_obj.tail = "\n"
        
        record = etree.SubElement(new_obj, "record")
        record.text = "\n    "
        record.tail = "\n"

        # Iterate through the fields
        for field_name, field_value in obj_data["fields"].items():
            field = etree.SubElement(record, "field", name=field_name)

            # Handle arrays
            if isinstance(field_value, dict) and field_value.get("type") == "array":
                array_data = field_value
                array_element = etree.SubElement(
                    field, 
                    "array", 
                    count=str(array_data["count"]), 
                    elementtypeid=array_data["elementtypeid"]
                )
                array_element.tail = "\n    "

                # Handle array items (pointers)
                for item in array_data["items"]:
                    if item["type"] == "pointer":
                        pointer_id = item["id"]

                        # Handle specific array field replacement
                        if field_name == "generators":
                            pointer_id = new_clipgen_pointer_id

                        # Append the pointer element
                        etree.SubElement(array_element, "pointer", id=pointer_id)

                field.tail = "\n    "

            # Handle pointer fields (outside arrays)
            elif isinstance(field_value, dict) and field_value.get("type") == "pointer":
                pointer_id = field_value["id"]

                # Handle specific pointer replacements
                if field_name == "generator":
                    pointer_id = new_cmsg_pointer_id

                etree.SubElement(field, "pointer", id=pointer_id)
                field.tail = "\n    "

            # Handle string fields
            elif isinstance(field_value, str):
                if field_name == "name":
                    value = new_name
                elif field_name == "animationName":
                    value = new_clipgen_name
                else:
                    value = field_value

                etree.SubElement(field, "string", value=value)

            # Handle boolean fields
            elif isinstance(field_value, bool):
                etree.SubElement(field, "bool", value="true" if field_value else "false")

            # Handle integer fields
            elif isinstance(field_value, int):
                if field_name == "animationInternalId":
                    value = str(new_animationInternalId)
                elif field_name == "animId":
                    value = str(new_anim_id)
                elif field_name == "stateId":
                    value = str(new_toStateId)
                elif field_name == "userData":
                    value = str(new_userData)
                else:
                    value = str(field_value)

                etree.SubElement(field, "integer", value=value)

            # Handle real/float fields
            elif isinstance(field_value, float):
                etree.SubElement(field, "real", dec=str(field_value), hex="#0")

            # Ensure new line after each </field>
            field.tail = "\n    "

        # Append the new object to the root
        self.root.append(new_obj)
        print(f"Duplicated object with new name '{new_name}' and ID '{new_id}'")

    def get_wildcard_transition(self, obj_data):
        """
        Extracts the 'wildcardTransitions' field from the object data.

        Args:
            obj_data (dict): The data structure collected from an object.

        Returns:
            str: The pointer ID associated with 'wildcardTransitions', or None if not found.
        """
        fields = obj_data.get("fields", {})
        wildcard_data = fields.get("wildcardTransitions")

        # Ensure the field exists and is of type 'pointer'
        if wildcard_data and isinstance(wildcard_data, dict) and wildcard_data.get("type") == "pointer":
            return wildcard_data["id"]

        print("Wildcard Transitions field not found or not a pointer.")
        return None

    def generate_transition_entry(self, transition_id, event_id, state_id):
        """
        Generates a transition entry as an XML Element with proper formatting.

        Args:
            transition_id (str): The ID of the transition pointer.
            event_id (str): The event ID.
            state_id (str): The state ID.

        Returns:
            etree._Element: The generated transition entry as an XML Element.
        """
        record = etree.Element("record")
        record.text = "\n    "

        # Trigger Interval
        trigger_interval = etree.SubElement(record, "field", name="triggerInterval")
        trigger_interval.text = "\n      "
        trigger_interval.tail = "\n    "
        
        interval_record = etree.SubElement(trigger_interval, "record")
        interval_record.text = "\n        "
        interval_record.tail = "\n      "
        
        enter_event_field = etree.SubElement(interval_record, "field", name="enterEventId")
        etree.SubElement(enter_event_field, "integer", value="-1")
        enter_event_field.tail = "\n        "

        exit_event_field = etree.SubElement(interval_record, "field", name="exitEventId")
        etree.SubElement(exit_event_field, "integer", value="-1")
        exit_event_field.tail = "\n        "

        enter_time_field = etree.SubElement(interval_record, "field", name="enterTime")
        etree.SubElement(enter_time_field, "real", dec="0", hex="#0")
        enter_time_field.tail = "\n        "

        exit_time_field = etree.SubElement(interval_record, "field", name="exitTime")
        etree.SubElement(exit_time_field, "real", dec="0", hex="#0")
        exit_time_field.tail = "\n      "

        # Initiate Interval
        initiate_interval = etree.SubElement(record, "field", name="initiateInterval")
        initiate_interval.text = "\n      "
        initiate_interval.tail = "\n    "
        
        init_record = etree.SubElement(initiate_interval, "record")
        init_record.text = "\n        "
        init_record.tail = "\n      "
        
        enter_event_field = etree.SubElement(init_record, "field", name="enterEventId")
        etree.SubElement(enter_event_field, "integer", value="-1")
        enter_event_field.tail = "\n        "

        exit_event_field = etree.SubElement(init_record, "field", name="exitEventId")
        etree.SubElement(exit_event_field, "integer", value="-1")
        exit_event_field.tail = "\n        "

        enter_time_field = etree.SubElement(init_record, "field", name="enterTime")
        etree.SubElement(enter_time_field, "real", dec="0", hex="#0")
        enter_time_field.tail = "\n        "

        exit_time_field = etree.SubElement(init_record, "field", name="exitTime")
        etree.SubElement(exit_time_field, "real", dec="0", hex="#0")
        exit_time_field.tail = "\n      "

        # Transition
        transition_field = etree.SubElement(record, "field", name="transition")
        transition_field.text = "\n      "
        etree.SubElement(transition_field, "pointer", id=str(transition_id))
        transition_field.tail = "\n    "

        # Condition
        condition_field = etree.SubElement(record, "field", name="condition")
        condition_field.text = "\n      "
        etree.SubElement(condition_field, "pointer", id="object0")
        condition_field.tail = "\n    "

        # Event ID
        event_field = etree.SubElement(record, "field", name="eventId")
        event_field.text = "\n      "
        etree.SubElement(event_field, "integer", value=str(event_id))
        event_field.tail = "\n    "

        # State ID
        state_field = etree.SubElement(record, "field", name="toStateId")
        state_field.text = "\n      "
        etree.SubElement(state_field, "integer", value=str(state_id))
        state_field.tail = "\n    "

        # Other fields
        from_nested_state_field = etree.SubElement(record, "field", name="fromNestedStateId")
        etree.SubElement(from_nested_state_field, "integer", value="0")
        from_nested_state_field.tail = "\n        "

        to_nested_state_field = etree.SubElement(record, "field", name="toNestedStateId")
        etree.SubElement(to_nested_state_field, "integer", value="0")
        to_nested_state_field.tail = "\n        "

        priority_field = etree.SubElement(record, "field", name="priority")
        etree.SubElement(priority_field, "integer", value="0")
        priority_field.tail = "\n        "

        flags_field = etree.SubElement(record, "field", name="flags")
        etree.SubElement(flags_field, "integer", value="3584")
        flags_field.tail = "\n      "

        record.tail = "\n  "

        return record

    def generate_event_info_entry(self):
        """
        Generates an event info entry as an XML Element with proper formatting.

        Returns:
            etree._Element: The generated event info entry as an XML Element.
        """
        # Create the record element
        record = etree.Element("record")
        record.text = "\n    "  # Indentation for formatting

        # Create the field for 'flags'
        flags_field = etree.SubElement(record, "field", name="flags")
        flags_field.text = "\n      "
        flags_field.tail = "\n    "

        # Add the integer element inside the flags field
        etree.SubElement(flags_field, "integer", value="0")

        record.tail = "\n  "  # Proper indentation after the record

        return record

    def save_xml(self, xml_file_path, output_file=None):
        output_file = output_file if output_file else xml_file_path
        self.tree.write(
            output_file, 
            encoding="utf-8", 
            xml_declaration=True, 
            pretty_print=True
        )
        print(f"XML file saved as '{output_file}'")