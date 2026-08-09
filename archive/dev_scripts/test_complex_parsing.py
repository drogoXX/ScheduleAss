"""
Comprehensive test for relationship parsing with actual examples from user
"""
import re

def parse_relationship_string(rel_string: str) -> list:
    """
    Parse relationship string into structured format

    Examples from actual P6 data:
    - Simple: "A21800: FS"
    - Multiple: "A21550: FF, A21800: FS"
    - With positive lag: "A21740: FF 10"
    - With negative lag: "A30820: FF -5"
    - Complex: "A34350: FS, A7410: FS, A7480: FS, A30820: FF -5, A34380: FS -4, A30830: FS"
    """
    relationships = []
    warnings = []

    if not rel_string or rel_string is None or str(rel_string).lower() in ['nan', 'none', '']:
        return relationships, warnings

    # Split by comma for multiple relationships
    parts = str(rel_string).split(',')

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Pattern: ActivityID: Type Lag
        # - ([A-Za-z0-9_-]+): Activity ID (alphanumeric, underscore, hyphen)
        # - \s*:\s*: Colon with optional whitespace
        # - ([A-Z]{2}): Relationship type (exactly 2 uppercase: FS, FF, SS, SF)
        # - \s*([-]?\d+)?: Optional lag (negative or positive integer with optional space)
        match = re.match(r'([A-Za-z0-9_-]+)\s*:\s*([A-Z]{2})\s*([-]?\d+)?', part)

        if match:
            activity_id = match.group(1)
            rel_type = match.group(2)
            lag = int(match.group(3)) if match.group(3) else 0

            relationships.append({
                'activity': activity_id,
                'type': rel_type,
                'lag': lag
            })
        else:
            warnings.append(f"Could not parse relationship: '{part}'")

    return relationships, warnings


# Test cases from user's actual data
test_cases = [
    ("Simple", "A21800: FS"),
    ("Multiple", "A21550: FF, A21800: FS"),
    ("Positive lag", "A21740: FF 10"),
    ("Negative lag", "A30820: FF -5"),
    ("Complex", "A34350: FS, A7410: FS, A7480: FS, A30820: FF -5, A34380: FS -4, A30830: FS"),
    ("Mixed types", "A21970: FF 10, A21740: FF 10, JCQV1010: FS"),
    ("With spaces", "A21800 : FS"),
    ("Negative with space", "A30820: FF  -5"),
    ("SS type", "A34350: SS 10"),
    ("SF type", "A21800: SF"),
    ("Empty", ""),
    ("None", None),
]

print("=" * 80)
print("COMPREHENSIVE RELATIONSHIP PARSING TEST")
print("=" * 80)
print()

all_passed = True
total_relationships = 0
total_negative_lags = 0
total_positive_lags = 0

for name, test_string in test_cases:
    print(f"Test: {name}")
    print(f"  Input: '{test_string}'")

    relationships, warnings = parse_relationship_string(test_string)

    if warnings:
        print(f"  ⚠️  Warnings: {warnings}")
        all_passed = False

    if relationships:
        print(f"  ✓ Parsed {len(relationships)} relationship(s):")
        for rel in relationships:
            lag_str = ""
            if rel['lag'] > 0:
                lag_str = f" +{rel['lag']}"
                total_positive_lags += 1
            elif rel['lag'] < 0:
                lag_str = f" {rel['lag']}"
                total_negative_lags += 1

            print(f"    → {rel['activity']}: {rel['type']}{lag_str}")
            total_relationships += 1
    elif test_string and test_string.lower() != 'none':
        print(f"  ✗ No relationships parsed (expected some)")
        all_passed = False
    else:
        print(f"  ✓ Correctly returned empty list")

    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total relationships parsed: {total_relationships}")
print(f"  - With positive lags: {total_positive_lags}")
print(f"  - With negative lags: {total_negative_lags}")
print(f"  - With no lag: {total_relationships - total_positive_lags - total_negative_lags}")
print()

if all_passed:
    print("✅ ALL TESTS PASSED!")
else:
    print("❌ SOME TESTS FAILED - See warnings above")

print()
print("=" * 80)
print("EXPECTED DATA STRUCTURE")
print("=" * 80)
print("""
For activity with complex relationships:
{
    'activity_id': 'A21550',
    'predecessors': [
        {'activity': 'A21550', 'type': 'FF', 'lag': 0},
        {'activity': 'A21800', 'type': 'FS', 'lag': 0}
    ],
    'successors': [
        {'activity': 'JCQV1010', 'type': 'FS', 'lag': 0},
        {'activity': 'A21970', 'type': 'FF', 'lag': 10},
        {'activity': 'A21740', 'type': 'FF', 'lag': 10}
    ]
}

This structure is created by:
1. Parsing "Predecessor Details" column → predecessors list
2. Parsing "Successor Details" column → successors list
3. Both stored in DataFrame columns: 'predecessor_list' and 'successor_list'
""")
