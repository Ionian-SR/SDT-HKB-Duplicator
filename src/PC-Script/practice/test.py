import xml.etree.ElementTree as ET

class XMLParser:
    def __init__(self, xml_file):
        self.xml_file = xml_file
        self.tree = ET.parse(xml_file)
        self.root = self.tree.getroot()

    def find_array_count(self):
        """
        Finds the <array> with name 'animationNames' and returns the count - 1.
        """
        for field in self.root.findall(".//field[@name='animationNames']"):
            array = field.find("array")
            if array is not None:
                count = int(array.attrib.get("count", "0"))
                return count - 1

        print("Field 'animationNames' not found.")
        return None

    def append_to_array(self, new_value):
        """
        Appends a new <string> element to the <array> inside 'animationNames' field.
        Updates the count attribute accordingly.
        """
        for field in self.root.findall(".//field[@name='animationNames']"):
            array = field.find("array")
            if array is not None:
                # Append the new string element
                new_string = ET.SubElement(array, "string", value=new_value)
                new_string.tail = "\n           "

                # Update the count attribute
                current_count = int(array.attrib.get("count", "0"))
                new_count = current_count + 1
                array.set("count", str(new_count))

                print(f"Appended '{new_value}' to 'animationNames'. New count: {new_count}")
                return

        print("Field 'animationNames' not found.")

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
                    traced_objects = self.trace_references(obj_data["id"])
                    print(f"Traced objects: {traced_objects}")
                    return obj_data, traced_objects

        print(f"Object with name '{name_value}' not found.")
        return None, []

    def find_object_by_id(self, obj_id):
        """
        Finds the object by its ID and returns its data, along with all traced references.
        """
        # Locate the object by its ID
        obj = self.root.find(f".//object[@id='{obj_id}']")
        
        if obj is not None:
            # Collect object data
            obj_data = self.collect_object_data(obj)
            print(f"Collected data for object ID '{obj_id}'")
            
            # Get the list of traced objects
            #traced_objects = self.trace_references(obj_id)
            #print(f"Traced objects: {traced_objects}")
            return obj_data

        print(f"Object with ID '{obj_id}' not found.")
        return None, []


    def _trace(self, obj_id, visited, referenced_objects, trace_limit=3):
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

    def duplicate_object(self, obj_data, new_name):
        """
        Duplicates the object using the unified 'fields' structure, 
        including handling of pointer fields and arrays.
        """
        # Generate new object ID
        new_id = f"object{self.get_largest_obj() + 1}"
        new_obj = ET.Element("object", id=new_id, typeid=obj_data["typeid"])
        new_obj.text = "\n  "
        record = ET.SubElement(new_obj, "record")
        record.text = "\n    "

        # Iterate through the fields
        for field_name, field_value in obj_data["fields"].items():
            field = ET.SubElement(record, "field", name=field_name)

            # Handle arrays
            if isinstance(field_value, dict) and field_value.get("type") == "array":
                array_data = field_value
                array_element = ET.SubElement(
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

                        # Locate and duplicate the referenced object
                        #referenced_obj = self.root.find(f".//object[@id='{pointer_id}']")
                        #if referenced_obj is not None:
                        #    referenced_data = self.collect_object_data(referenced_obj)
                        #    self.duplicate_object(referenced_data, new_name + "_arr_ptr")

                        pointer_id = new_clipgen_pointer_id

                        # Create the pointer element in the array
                        ET.SubElement(array_element, "pointer", id=pointer_id)

                field.tail = "\n    "

            # Handle pointer fields (outside arrays)
            elif isinstance(field_value, dict) and field_value.get("type") == "pointer":
                pointer_id = field_value["id"]

                # Locate and duplicate the referenced object
                #referenced_obj = self.root.find(f".//object[@id='{pointer_id}']")
                #if referenced_obj is not None:
                #    referenced_data = self.collect_object_data(referenced_obj)
                #    self.duplicate_object(referenced_data, new_name + "_ptr")
                if field_name == "generator":
                    pointer_id = new_csmg_pointer_id
                else:
                    pointer_id = pointer_id
                # Create the pointer element
                ET.SubElement(field, "pointer", id=pointer_id)
                field.tail = "\n    "

            # Handle string fields
            elif isinstance(field_value, str):
                if field_name == "name":
                    value = new_name
                elif field_name == "animationName":
                    value = new_clipgen_name
                else:
                    value = field_value
                ET.SubElement(field, "string", value=value)

            elif isinstance(field_value, bool):
                ET.SubElement(field, "bool", value="true" if field_value else "false")

            # Handle integer fields
            elif isinstance(field_value, int):
                if field_name == "animationInternalId":
                    value = str(new_animationInternalId)
                elif field_name == "animId":
                    value = str(new_anim_id)
                else:
                    value = value=str(field_value)

                ET.SubElement(field, "integer", value=value)

            # Handle real/float fields
            elif isinstance(field_value, float):
                ET.SubElement(field, "real", dec=str(field_value), hex="#0")

            # Ensure new line after each </field>
            field.tail = "\n    "

        # Append the new object to the root
        self.root.append(new_obj)
        print(f"Duplicated object with new name '{new_name}' and ID '{new_id}'")

    def save_xml(self, output_file=None):
        output_file = output_file if output_file else self.xml_file
        self.tree.write(output_file, encoding="utf-8", xml_declaration=True)
        print(f"XML file saved as '{output_file}'")

if __name__ == "__main__":
    xml_file = 'c0000.xml'  # Update this with your XML file path
    parser = XMLParser(xml_file)
    obj_data, traced_objects = parser.find_object_by_name("a050_300040")

    
    a_offset = f"050"
    new_anim_id = f"300050"
    new_csmg_name = f"GroundAttackCombo6_CMSG"
    new_clipgen_name = f"a{a_offset}_{new_anim_id}"
    new_stateinfo_name = f"GroundAttackCombo6"

    new_clipgen_pointer_id = f"object{parser.get_largest_obj() + 1}"
    new_csmg_pointer_id = f"object{parser.get_largest_obj() + 2}"

    #   Append new animation to animationNames array. Update Count. Take new internalID.
    parser.append_to_array(f"..\\..\\..\\..\\..\\Model\\chr\\c0000\\hkx\\{a_offset}\\{new_clipgen_name}.hkx")
    new_animationInternalId = parser.find_array_count()
    #print(new_animationInternalId)
    
    if obj_data:
        parser.duplicate_object(obj_data, new_clipgen_name)
        if traced_objects[0] is not None:
            obj_data1 = parser.find_object_by_id(traced_objects[0])
            #print(obj_data1)
            parser.duplicate_object(obj_data1, new_csmg_name)
            if traced_objects[1] is not None:
                obj_data2 = parser.find_object_by_id(traced_objects[1])
                #print(obj_data1)
                parser.duplicate_object(obj_data2, new_stateinfo_name)
        parser.save_xml()
        
    