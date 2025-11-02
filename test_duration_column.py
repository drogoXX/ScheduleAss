"""
Test to verify duration parsing with P6 column name variations
"""

import pandas as pd
import io
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer

print("=" * 80)
print("Testing Duration Parsing with Column Name Variations")
print("=" * 80)
print()

# Create test CSV with "At Completion Duration(d)" - P6 export format
csv_with_suffix = """Activity ID,Activity Name,Activity Status,WBS Code,At Completion Duration(d),Start,Finish,Free Float,Total Float,Predecessors,Predecessor Details,Successors,Successor Details,Primary Constraint,Activity Type,Duration Type,Resource Names
A1000,Project Start,Completed,1.0,0,2025-01-01,2025-01-01,0,0,,,A1010,A1010: FS,As Late As Possible,Start Milestone,Fixed Duration & Units,
A1010,Task 1,Completed,1.1,15,2025-01-02,2025-01-21,0,0,A1000,A1000: FS,A1020,A1020: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1020,Task 2,In Progress,1.2,10,2025-01-22,2025-02-05,2,2,A1010,A1010: FS,A1030,A1030: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1030,Task 3,Not Started,1.3,20,2025-02-06,2025-03-03,0,0,A1020,A1020: FS,,,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
"""

print("Test 1: CSV with 'At Completion Duration(d)' column")
print("-" * 80)

parser = ScheduleParser()
schedule_data = parser.parse_csv(csv_with_suffix.encode(), 'test_with_suffix.csv')

if not schedule_data.get('success'):
    print("❌ Parsing failed!")
    print(f"Errors: {schedule_data.get('errors')}")
else:
    print(f"✅ Parsing successful - {schedule_data['total_activities']} activities")

# Check if duration data is present
print()
print("Checking parsed data:")
activities = schedule_data['activities']

# Check if 'At Completion Duration(d)' exists in DataFrame
df = pd.DataFrame(activities)
print(f"  Available columns: {list(df.columns)}")
print()

# Check for duration column variations
duration_cols_found = []
for col in df.columns:
    if 'duration' in col.lower() and 'completion' in col.lower():
        duration_cols_found.append(col)
        print(f"  Found duration column: '{col}'")

if duration_cols_found:
    for col in duration_cols_found:
        durations = df[col].dropna()
        if len(durations) > 0:
            print(f"    - {len(durations)} activities have duration values")
            print(f"    - Durations: {list(durations)}")
            print(f"    - Data type: {df[col].dtype}")
        else:
            print(f"    - No duration values found (all NaN)")
else:
    print("  ❌ No 'At Completion Duration' column found!")

print()

# Check calculated_duration
if 'calculated_duration' in df.columns:
    calc_durations = df['calculated_duration'].dropna()
    print(f"  Found 'calculated_duration': {len(calc_durations)} activities")
    print(f"    - Durations: {list(calc_durations)}")
else:
    print("  No 'calculated_duration' column found")

print()
print("-" * 80)

# Run DCMA analysis
print()
print("Test 2: Running DCMA Analysis")
print("-" * 80)

try:
    analyzer = DCMAAnalyzer(schedule_data)
    results = analyzer.analyze()
    metrics = results['metrics']

    avg_duration = metrics.get('average_duration', {})
    print(f"✅ Analysis completed")
    print()
    print("Duration Analysis Results:")
    print(f"  Mean: {avg_duration.get('mean', 0)} days")
    print(f"  Median: {avg_duration.get('median', 0)} days")
    print(f"  Min: {avg_duration.get('min', 0)} days")
    print(f"  Max: {avg_duration.get('max', 0)} days")
    print(f"  Status: {avg_duration.get('status', 'unknown')}")

    if avg_duration.get('mean', 0) == 0:
        print()
        print("  ⚠️  WARNING: Mean duration is 0 - duration data not being used!")
    else:
        print()
        print("  ✅ Duration data is being analyzed correctly")

except Exception as e:
    print(f"❌ Analysis failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("Summary")
print("=" * 80)

# Check if the column name issue exists
if 'At Completion Duration(d)' in df.columns:
    print("✅ Column 'At Completion Duration(d)' exists in parsed data")

    # Check if it's being used by analyzer
    if avg_duration.get('mean', 0) > 0:
        print("✅ Duration analysis is using the data correctly")
    else:
        print("❌ ISSUE: Duration column exists but analyzer is not using it!")
        print("   Likely cause: Analyzer looking for 'At Completion Duration' (without suffix)")
        print("   Fix needed: Normalize column names to handle '(d)' suffix")
else:
    print("❌ ISSUE: Column name was changed during parsing")
    print(f"   Column names in DataFrame: {[col for col in df.columns if 'duration' in col.lower()]}")
