import re

class HKSParser:
    def __init__(self, hks_file):
        self.hks_file = hks_file
    
    def append_def(self, definition):
        with open(self.hks_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        output_lines = []
        for line in lines:
            if "g_paramHkbState" in line:
                output_lines.append(definition + "\n")  # insert before the target line
            output_lines.append(line)

        with open(self.hks_file, 'w', encoding='utf-8') as f:
            f.writelines(output_lines)

        print("✅ Inserted text above 'g_paramHkbState'")
    
    def reformat_g_paramHkbState(self):
        with open(self.hks_file, 'r', encoding='utf-8') as f:
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
            print("g_paramHkbState block not found or malformed.")
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

        with open(self.hks_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        print("Reformatted g_paramHkbState block.")
    
    def get_max_number(self):
        with open(self.hks_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all integers using regex
        numbers = list(map(int, re.findall(r'\b\d+\b', content)))
        if not numbers:
            return 1  # Default start if no numbers found

        return max(numbers)
    
    def find_hkb_state(self, state_name):
        with open(self.hks_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex to find the full line
        pattern = rf"\[\s*{re.escape(state_name)}\s*\]\s*=\s*\{{[^}}]*\}},?"
        match = re.search(pattern, content)
        # Search for the line
        if match:
            return match.group(0)
        else:
            return None
    
    def append_g_param(self, new_line):
        with open(self.hks_file, 'r', encoding='utf-8') as f:
            content = f.read()

        param_name = 'g_paramHkbState'
        pattern = rf"({param_name}\s*=\s*\{{)(.*?)(\n\}})"
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            raise ValueError(f"Could not find {param_name} block in the file.")

        # Break out the parts
        start_block = match.group(1)
        block_body = match.group(2).strip()
        end_block = match.group(3)

        # Split block body into lines and clean up
        block_lines = [line.strip() for line in block_body.splitlines() if line.strip()]
        block_lines.append(new_line.strip())

        # Add commas to all but the last line
        #for i in range(len(block_lines) - 1):
        block_lines[-2] = re.sub(r",?\s*$", ",", block_lines[-2])  # force comma
        block_lines[-1] = re.sub(r",\s*$", "", block_lines[-1])      # remove comma from last

        # Indent all lines
        indented_block = ['    ' + line for line in block_lines]

        # Reconstruct the full content
        modified_block = start_block + "\n" + "\n".join(indented_block) + end_block
        updated_content = re.sub(pattern, modified_block, content, flags=re.DOTALL)

        # Write back to file
        with open(self.hks_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)

    def append_functions(self, state_name, hkb_state_name):
        template = f'''
function {state_name}_onUpdate()
    UpdateState({hkb_state_name})
end

function {state_name}_onActivate()
    return
    
end

function {state_name}_onDeactivate()
    return
    
end
'''
        with open(self.hks_file, 'a', encoding='utf-8') as f:
            f.write('\n' + template)
        