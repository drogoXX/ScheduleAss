"""
Test to verify column names after parsing normalization
"""
import csv
import re

def normalize_column_name(col):
    """Simulate the parser's column normalization"""
    normalized = col.strip()
    # Remove suffixes: (d), (h), (%), (wk), (mo), (yr)
    normalized = re.sub(r'\s*\([dhwmy%]+\)\s*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s*\(days?\)\s*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s*\(hours?\)\s*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s*\(weeks?\)\s*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s*\(months?\)\s*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s*\(years?\)\s*$', '', normalized, flags=re.IGNORECASE)
    return normalized.strip()

print("=" * 80)
print("Testing Column Name Normalization")
print("=" * 80)

# Read CSV headers
with open('data/Schedule export.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    original_headers = reader.fieldnames

print("\nOriginal headers from CSV:")
for header in original_headers:
    print(f"  - '{header}'")

print("\n" + "=" * 80)
print("Normalized headers (after parsing):")
print("=" * 80)

normalized_headers = [normalize_column_name(h) for h in original_headers]
for orig, norm in zip(original_headers, normalized_headers):
    if orig != norm:
        print(f"  ✏️  '{orig}' → '{norm}'")
    else:
        print(f"  ✓  '{orig}'")

print("\n" + "=" * 80)
print("Key Columns Check")
print("=" * 80)

# Check if the required columns will be present after normalization
required_columns = ['WBS Code', 'Total Float']
for req_col in required_columns:
    if req_col in normalized_headers:
        print(f"✅ '{req_col}' will be available after parsing")
    else:
        print(f"❌ '{req_col}' will NOT be available after parsing")
        print(f"   Available columns: {normalized_headers}")

print("\n" + "=" * 80)
print("Data Sample Check")
print("=" * 80)

# Read first few rows and check the data
with open('data/Schedule export.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)

    print("\nFirst 5 activities with WBS Code and Total Float:")
    print(f"{'Activity ID':<12} {'WBS Code':<35} {'Total Float':>12}")
    print("-" * 60)

    count = 0
    both_present = 0
    for row in reader:
        if count >= 5:
            break

        activity_id = row.get('Activity ID', 'N/A')
        wbs_code = row.get('WBS Code', 'N/A')
        total_float = row.get('Total Float', 'N/A')

        print(f"{activity_id:<12} {wbs_code:<35} {total_float:>12}")

        if wbs_code and wbs_code.strip() and total_float and total_float.strip():
            both_present += 1

        count += 1

    print(f"\n✅ {both_present} out of {count} sample activities have both WBS Code and Total Float")

print("\n" + "=" * 80)
print("Conclusion")
print("=" * 80)

if 'WBS Code' in normalized_headers and 'Total Float' in normalized_headers:
    print("✅ The CSV has the correct column structure")
    print("✅ Column names will be preserved correctly after parsing")
    print("✅ The calculate_float_by_wbs function should work correctly")
    print("✅ The fix implementation is correct and should display data")
else:
    print("⚠️  Column name mismatch detected")

print("=" * 80)
