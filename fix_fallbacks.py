#!/usr/bin/env python3
"""
Systematic fallback pattern fixer.
Converts ternary fallback patterns to .get() patterns.
"""

import re
import sys
from pathlib import Path

# Pattern to match: dict["key"] if "key" in dict else "default"
PATTERN = re.compile(
    r'(\w+)\["([^"]+)"\]\s+if\s+"[^"]+"\s+in\s+\1\s+else\s+(.+?)(?=\n|$)',
    re.MULTILINE,
)


def fix_fallback_in_file(filepath: Path) -> int:
    """Fix fallback patterns in a single file. Returns count of replacements."""
    try:
        content = filepath.read_text()
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
        return 0

    original_content = content
    count = 0

    # Find all matches
    for match in PATTERN.finditer(content):
        dict_var = match.group(1)
        key = match.group(2)
        default_val = match.group(3).strip()

        # Construct replacement
        if default_val.startswith("[") and default_val.endswith("]"):
            # List default
            replacement = f'{dict_var}.get("{key}", {default_val})'
        elif default_val.startswith("{") and default_val.endswith("}"):
            # Dict default
            replacement = f'{dict_var}.get("{key}", {default_val})'
        elif default_val.startswith('"') and default_val.endswith('"'):
            # String default - use or pattern for non-empty check
            replacement = f'{dict_var}.get("{key}") or {default_val}'
        elif default_val in ("None", "True", "False", "0"):
            # Boolean/None defaults
            replacement = f'{dict_var}.get("{key}", {default_val})'
        else:
            # Expression - try to use or pattern
            replacement = f'{dict_var}.get("{key}") or {default_val}'

        old_text = match.group(0)
        content = content.replace(old_text, replacement, 1)
        count += 1
        print(f"  Fixed line {len(content[:match.start()].split(chr(10)))}: {old_text[:50]}...")

    if count > 0:
        try:
            filepath.write_text(content)
            print(f"✅ {filepath.name}: Fixed {count} patterns")
        except Exception as e:
            print(f"❌ Error writing {filepath}: {e}")
            return 0
    else:
        print(f"ℹ️  {filepath.name}: No patterns found")

    return count


def main():
    """Main entry point."""
    # Files to fix (priority order)
    priority_files = [
        "cost_toolkit/common/vpc_cleanup_utils.py",
        "cost_toolkit/common/route53_utils.py",
        "cost_toolkit/common/aws_common.py",
        "cost_toolkit/scripts/setup/verify_iwannabenewyork_domain.py",
        "cost_toolkit/scripts/setup/route53_helpers.py",
    ]

    base_path = Path("/Users/mahrens917/aws")
    total_fixed = 0

    print("🔧 Fixing fallback patterns in priority files...\n")

    for file_path in priority_files:
        full_path = base_path / file_path
        if full_path.exists():
            fixed = fix_fallback_in_file(full_path)
            total_fixed += fixed
        else:
            print(f"⚠️  File not found: {full_path}")

    print(f"\n📊 Total patterns fixed: {total_fixed}")


if __name__ == "__main__":
    main()
