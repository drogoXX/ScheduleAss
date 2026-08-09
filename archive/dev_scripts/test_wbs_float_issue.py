"""
Test to reproduce the WBS Float Distribution issue
"""
import pandas as pd

# Simulate the calculate_float_by_wbs function
def calculate_float_by_wbs(activities):
    """Calculate float by WBS code for box plot"""
    try:
        if not activities:
            return {}

        df = pd.DataFrame(activities)

        # Check if required columns exist
        if 'Total Float' not in df.columns:
            print("❌ Total Float column not found")
            return {}

        if 'WBS Code' not in df.columns:
            print("❌ WBS Code column not found")
            return {}

        print(f"✅ Found columns: {df.columns.tolist()}")
        print(f"   Total activities: {len(df)}")

        # Filter out rows with NaN in WBS Code or Total Float
        valid_df = df.dropna(subset=['WBS Code', 'Total Float'])
        print(f"   Activities with both WBS and Float: {len(valid_df)}")

        if len(valid_df) == 0:
            print("❌ No activities with both WBS Code and Total Float")
            return {}

        # Group by WBS and get float values (excluding NaN)
        wbs_groups = valid_df.groupby('WBS Code')['Total Float'].apply(list).to_dict()
        print(f"   WBS groups created: {len(wbs_groups)} groups")
        for wbs, floats in list(wbs_groups.items())[:3]:
            print(f"      {wbs}: {len(floats)} float values")

        # Get top 10 WBS codes by activity count
        wbs_counts = valid_df['WBS Code'].value_counts().head(10)
        print(f"   Top WBS codes: {len(wbs_counts)}")

        if len(wbs_counts) == 0:
            print("❌ No WBS codes found")
            return {}

        # Return float values for top 10 WBS codes
        float_by_wbs = {
            str(wbs): [float(f) for f in wbs_groups.get(wbs, [])]
            for wbs in wbs_counts.index
        }

        print(f"✅ Final float_by_wbs dictionary:")
        for wbs, floats in float_by_wbs.items():
            print(f"      {wbs}: {len(floats)} values")

        return float_by_wbs
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return {}

# Test Case 1: Normal data with WBS codes
print("=" * 80)
print("Test Case 1: Normal data")
print("=" * 80)
activities1 = [
    {'Activity ID': 'A1', 'WBS Code': '1.0', 'Total Float': 0},
    {'Activity ID': 'A2', 'WBS Code': '1.1', 'Total Float': 5},
    {'Activity ID': 'A3', 'WBS Code': '1.2', 'Total Float': 10},
    {'Activity ID': 'A4', 'WBS Code': '2.0', 'Total Float': 15},
]
result1 = calculate_float_by_wbs(activities1)
print(f"\nResult: {result1}")
print(f"Dict is truthy: {bool(result1)}")
print(f"Dict length > 0: {len(result1) > 0}")

# Test Case 2: WBS codes are None/NaN
print("\n" + "=" * 80)
print("Test Case 2: All WBS codes are None")
print("=" * 80)
activities2 = [
    {'Activity ID': 'A1', 'WBS Code': None, 'Total Float': 0},
    {'Activity ID': 'A2', 'WBS Code': None, 'Total Float': 5},
    {'Activity ID': 'A3', 'WBS Code': None, 'Total Float': 10},
]
result2 = calculate_float_by_wbs(activities2)
print(f"\nResult: {result2}")
print(f"Dict is truthy: {bool(result2)}")

# Test Case 3: Mixed - some activities have WBS, some don't
print("\n" + "=" * 80)
print("Test Case 3: Mixed data - some have WBS, some don't")
print("=" * 80)
activities3 = [
    {'Activity ID': 'A1', 'WBS Code': None, 'Total Float': 0},
    {'Activity ID': 'A2', 'WBS Code': '1.0', 'Total Float': 5},
    {'Activity ID': 'A3', 'WBS Code': '1.1', 'Total Float': 10},
    {'Activity ID': 'A4', 'WBS Code': None, 'Total Float': 15},
]
result3 = calculate_float_by_wbs(activities3)
print(f"\nResult: {result3}")

# Test Case 4: WBS codes exist but Total Float is NaN
print("\n" + "=" * 80)
print("Test Case 4: WBS codes exist but Total Float is NaN")
print("=" * 80)
import numpy as np
activities4 = [
    {'Activity ID': 'A1', 'WBS Code': '1.0', 'Total Float': np.nan},
    {'Activity ID': 'A2', 'WBS Code': '1.1', 'Total Float': np.nan},
    {'Activity ID': 'A3', 'WBS Code': '1.2', 'Total Float': np.nan},
]
result4 = calculate_float_by_wbs(activities4)
print(f"\nResult: {result4}")

print("\n" + "=" * 80)
print("Summary")
print("=" * 80)
print(f"Test 1 (Normal): {len(result1)} WBS codes found")
print(f"Test 2 (No WBS): {len(result2)} WBS codes found")
print(f"Test 3 (Mixed): {len(result3)} WBS codes found")
print(f"Test 4 (No Float): {len(result4)} WBS codes found")
