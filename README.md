# USAGE:

python3 code.py {aXXX} {3XXX Beginning Range} {3XXX End Range}

## Examples

- python3 code.py 0 3010
  - This will generate a singular a000_003010 entry.
- python3 code.py 1 3000 3005
  - This will generate a100_003000, a100_003001, a100_003002... a100_003005 entries.

# IMPORTANT NOTES:
### These issues will have to be fixed later.
- This tool will NOT check if a pre-existing entry already exists. If 3000 already exists, don't try to add 3000.
- This tool will NOT check if a pre-existing variation of 3XXX exists in a different aXXX.
- Currently will spit out new_c9997.xml after running. This will be annoying to constantly rename, so I will add a proper backup system later.
