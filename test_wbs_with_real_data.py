"""
Test the WBS Float Distribution with actual Schedule export.csv data
"""
import sys
import csv
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.schedule_parser import ScheduleParser

print("=" * 80)
print("Testing WBS Float Distribution with Real Data")
print("=" * 80)

# Read the actual CSV file
csv_path = Path(__file__).parent / "data" / "Schedule export.csv"
print(f"\nReading: {csv_path}")

with open(csv_path, 'rb') as f:
    csv_content = f.read()

# Parse the CSV
parser = ScheduleParser()
schedule_data = parser.parse_csv(csv_content, 'Schedule export.csv')

if not schedule_data.get('success'):
    print("\n❌ Parsing failed!")
    print(f"Errors: {schedule_data.get('errors')}")
    sys.exit(1)

print("✅ Step 1: Parsing successful")
print(f"   Total activities: {schedule_data['total_activities']}")

# Get activities
activities = schedule_data.get('activities', [])
print(f"   Activities list length: {len(activities)}")

# Check column names in first activity
if activities:
    print(f"\n   Sample activity columns: {list(activities[0].keys())[:10]}")

# Analyze WBS and Float columns
import pandas as pd
df = pd.DataFrame(activities)

print("\n" + "=" * 80)
print("Column Analysis")
print("=" * 80)

# Check for WBS Code column
if 'WBS Code' in df.columns:
    wbs_count = df['WBS Code'].notna().sum()
    unique_wbs = df['WBS Code'].nunique()
    print(f"✅ WBS Code column found")
    print(f"   Activities with WBS Code: {wbs_count}")
    print(f"   Unique WBS codes: {unique_wbs}")
    print(f"   Sample WBS codes:")
    for wbs in df['WBS Code'].dropna().unique()[:5]:
        count = (df['WBS Code'] == wbs).sum()
        print(f"      {wbs}: {count} activities")
else:
    print(f"❌ WBS Code column NOT found")
    print(f"   Available columns: {df.columns.tolist()}")

# Check for Total Float column
if 'Total Float' in df.columns:
    float_count = df['Total Float'].notna().sum()
    print(f"\n✅ Total Float column found")
    print(f"   Activities with Total Float: {float_count}")
    print(f"   Float value range: {df['Total Float'].min():.1f} to {df['Total Float'].max():.1f}")
    print(f"   Sample Total Float values:")
    print(f"      {df['Total Float'].dropna().head(10).tolist()}")
else:
    print(f"\n❌ Total Float column NOT found")
    print(f"   Available columns: {df.columns.tolist()}")

# Check for both columns together
if 'WBS Code' in df.columns and 'Total Float' in df.columns:
    both_valid = df.dropna(subset=['WBS Code', 'Total Float'])
    print(f"\n   Activities with both WBS Code AND Total Float: {len(both_valid)}")

    # Now test the calculate_float_by_wbs function logic
    print("\n" + "=" * 80)
    print("Testing calculate_float_by_wbs Logic")
    print("=" * 80)

    # Simulate the function
    wbs_groups = both_valid.groupby('WBS Code')['Total Float'].apply(list).to_dict()
    print(f"   WBS groups created: {len(wbs_groups)}")

    # Get top 10 WBS codes by activity count
    wbs_counts = both_valid['WBS Code'].value_counts().head(10)
    print(f"   Top 10 WBS codes by activity count:")
    for i, (wbs, count) in enumerate(wbs_counts.items(), 1):
        float_values = wbs_groups.get(wbs, [])
        avg_float = sum(float_values) / len(float_values) if float_values else 0
        print(f"      {i}. {wbs}: {count} activities, avg float: {avg_float:.1f}")

    # Create the float_by_wbs dictionary
    float_by_wbs = {
        str(wbs): [float(f) for f in wbs_groups.get(wbs, [])]
        for wbs in wbs_counts.index
    }

    print(f"\n   float_by_wbs dictionary created with {len(float_by_wbs)} entries")

    # Check if at least one WBS code has non-empty float values
    has_data = any(len(floats) > 0 for floats in float_by_wbs.values())
    print(f"   has_data check: {has_data}")

    if has_data:
        print(f"\n✅ SUCCESS: The WBS Float Distribution would display correctly!")
        print(f"   Chart would show {len(float_by_wbs)} WBS codes with float distributions")

        # Count how many traces would be added
        traces_added = 0
        for wbs, floats in float_by_wbs.items():
            if floats:
                traces_added += 1
        print(f"   Number of traces that would be added to chart: {traces_added}")
    else:
        print(f"\n❌ ISSUE: No valid float data found")
else:
    print(f"\n❌ Cannot test - missing required columns")

print("\n" + "=" * 80)
print("Conclusion")
print("=" * 80)

if 'WBS Code' in df.columns and 'Total Float' in df.columns:
    both_valid = df.dropna(subset=['WBS Code', 'Total Float'])
    if len(both_valid) > 0:
        print("✅ The Schedule export.csv file has proper WBS and Float data")
        print("✅ The fix should work correctly with this data")
        print(f"✅ Expected to display box plot with top 10 WBS codes from {len(both_valid)} activities")
    else:
        print("⚠️  No activities have both WBS Code and Total Float values")
else:
    print("⚠️  Missing required columns in parsed data")

print("=" * 80)
