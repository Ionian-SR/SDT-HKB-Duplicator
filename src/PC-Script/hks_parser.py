import re

class HKSParser:
    def __init__(self, hks_file):
        self.hks_file = hks_file
    
    def append_def(self, definition):
        with open(self.hks_file, 'r') as f:
            lines = f.readlines()

        output_lines = []
        for line in lines:
            if "g_paramHkbState" in line:
                output_lines.append(definition + "\n")  # insert before the target line
            output_lines.append(line)

        with open(self.hks_file, 'w') as f:
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
