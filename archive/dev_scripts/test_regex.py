"""
Test regex pattern for parsing relationships
"""
import re

def parse_relationship(rel_string):
    """Test the regex pattern"""
    relationships = []

    if not rel_string:
        return relationships

    parts = rel_string.split(',')

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Pattern: ActivityID: Type Lag
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
            print(f"  ✓ Parsed: {part} → Activity: {activity_id}, Type: {rel_type}, Lag: {lag}")
        else:
            print(f"  ✗ Failed to parse: {part}")

    return relationships

# Test cases from the CSV
test_cases = [
    ("A1070: FS, A1060: FF -3", "A1080 Predecessor Details"),
    ("A1090: FS 7", "A1080 Successor Details"),
    ("A1080: FS 7", "A1090 Predecessor Details"),
    ("A1100: SS -15", "A2000 Successor Details"),
    ("A1060: SS -10, A2020: FS 5", "A2010 Successor Details"),
    ("A1150: SS -30", "A2020 Successor Details"),
    ("A1070: FS 5, A1110: SS -5", "A2030 Successor Details"),
    ("A1060: SS -5", "A2040 Successor Details"),
    ("A1040: FS, A1060: SS -10", "A2050 Successor Details"),
]

print("Testing relationship parsing:\n")

total_negative = 0
total_positive = 0

for test_string, description in test_cases:
    print(f"{description}: '{test_string}'")
    relationships = parse_relationship(test_string)

    for rel in relationships:
        if rel['lag'] < 0:
            total_negative += 1
            print(f"    → NEGATIVE LAG: {rel['lag']}")
        elif rel['lag'] > 0:
            total_positive += 1
            print(f"    → POSITIVE LAG: {rel['lag']}")

    print()

print(f"\nSummary:")
print(f"  Total negative lags found: {total_negative}")
print(f"  Total positive lags found: {total_positive}")
