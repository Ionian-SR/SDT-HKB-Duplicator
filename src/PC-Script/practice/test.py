import xml.etree.ElementTree as ET

class XMLParser:
    def __init__(self, xml_file):
        self.xml_file = xml_file
        self.tree = ET.parse(xml_file)
        self.root = self.tree.getroot()

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
        for obj in self.root.findall(".//object"):
            for field in obj.findall(".//field[@name='name']/string"):
                if field.attrib['value'] == name_value:
                    obj_data = self.collect_object_data(obj)
                    print(f"Collected data for object '{name_value}': {obj_data}")
                    self.trace_references(obj_data["id"])
                    return obj_data
        print(f"Object with name '{name_value}' not found.")
        return None

    def trace_references(self, obj_id):
        visited = set()
        self._trace(obj_id, visited)

    def _trace(self, obj_id, visited):
        if obj_id in visited:
            return
        visited.add(obj_id)
        for obj in self.root.findall(".//object"):
            for pointer in obj.findall(".//pointer"):
                if pointer.attrib.get('id') == obj_id:
                    print(f"Object {obj.attrib['id']} references {obj_id}")
                    self._trace(obj.attrib['id'], visited)

    def duplicate_object(self, obj_data, new_name):
        """
        Duplicates the object using the unified 'fields' structure, 
        including handling of pointer fields and arrays.
        """
        # Generate new object ID
        new_id = f"object{len(self.root)}"
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
                        referenced_obj = self.root.find(f".//object[@id='{pointer_id}']")
                        if referenced_obj is not None:
                            referenced_data = self.collect_object_data(referenced_obj)
                            self.duplicate_object(referenced_data, new_name + "_arr_ptr")

                        # Create the pointer element in the array
                        ET.SubElement(array_element, "pointer", id=pointer_id)

                field.tail = "\n    "

            # Handle pointer fields (outside arrays)
            elif isinstance(field_value, dict) and field_value.get("type") == "pointer":
                pointer_id = field_value["id"]

                # Locate and duplicate the referenced object
                referenced_obj = self.root.find(f".//object[@id='{pointer_id}']")
                if referenced_obj is not None:
                    referenced_data = self.collect_object_data(referenced_obj)
                    self.duplicate_object(referenced_data, new_name + "_ptr")

                # Create the pointer element
                ET.SubElement(field, "pointer", id=pointer_id)
                field.tail = "\n    "

            # Handle string fields
            elif isinstance(field_value, str):
                value = new_name if field_name == "name" else field_value
                ET.SubElement(field, "string", value=value)

            # Handle integer fields
            elif isinstance(field_value, int):
                ET.SubElement(field, "integer", value=str(field_value))

            # Handle real/float fields
            elif isinstance(field_value, float):
                ET.SubElement(field, "real", dec=str(field_value), hex="#0")

            # Handle boolean fields
            elif isinstance(field_value, bool):
                ET.SubElement(field, "bool", value="true" if field_value else "false")

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
    xml_file = 'sample.xml'  # Update this with your XML file path
    parser = XMLParser(xml_file)
    obj_data = parser.find_object_by_name("a050_300040")

    if obj_data:
        parser.duplicate_object(obj_data, "a050_300040_copy")
        parser.save_xml()
