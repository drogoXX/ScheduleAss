"""
Debug script to test data flow from parser to analyzer
"""

import pandas as pd
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer

# Parse the sample CSV
print("=" * 80)
print("STEP 1: Parsing CSV")
print("=" * 80)

parser = ScheduleParser()
with open('data/sample_schedule.csv', 'rb') as f:
    file_content = f.read()

schedule_data = parser.parse_csv(file_content, 'sample_schedule.csv')

if not schedule_data.get('success'):
    print("❌ PARSING FAILED")
    print(f"Errors: {schedule_data.get('errors')}")
    exit(1)

print(f"✅ Parsing successful")
print(f"Total activities: {schedule_data['total_activities']}")
print(f"Warnings: {schedule_data.get('warnings', [])}")
print()

# Check activities data structure
print("=" * 80)
print("STEP 2: Inspecting Activities Data")
print("=" * 80)

activities = schedule_data['activities']
print(f"Number of activities: {len(activities)}")
print(f"Type of activities: {type(activities)}")
print()

# Check first activity with relationships
sample_activity = None
for act in activities:
    if 'predecessor_list' in act and len(act['predecessor_list']) > 0:
        sample_activity = act
        break

if sample_activity:
    print(f"Sample activity with predecessors: {sample_activity['Activity ID']}")
    print(f"  Activity Name: {sample_activity['Activity Name']}")
    print(f"  Predecessor List Type: {type(sample_activity['predecessor_list'])}")
    print(f"  Predecessor List: {sample_activity['predecessor_list']}")
    print()
else:
    print("⚠️  No activities with predecessors found!")
    print()

# Count relationships
total_predecessors = 0
activities_with_predecessors = 0
negative_lags = 0
positive_lags = 0

for act in activities:
    pred_list = act.get('predecessor_list', [])
    if pred_list and len(pred_list) > 0:
        activities_with_predecessors += 1
        total_predecessors += len(pred_list)
        for pred in pred_list:
            lag = pred.get('lag', 0)
            if lag < 0:
                negative_lags += 1
            elif lag > 0:
                positive_lags += 1

print(f"Activities with predecessors: {activities_with_predecessors}")
print(f"Total predecessor relationships: {total_predecessors}")
print(f"  - Negative lags: {negative_lags}")
print(f"  - Positive lags: {positive_lags}")
print(f"  - Zero lags: {total_predecessors - negative_lags - positive_lags}")
print()

# Check duration data
print("=" * 80)
print("STEP 3: Checking Duration Data")
print("=" * 80)

durations = []
for act in activities:
    if 'At Completion Duration' in act:
        dur = act['At Completion Duration']
        if pd.notna(dur):
            durations.append(dur)

if durations:
    print(f"Activities with 'At Completion Duration': {len(durations)}")
    print(f"  Min: {min(durations)}")
    print(f"  Max: {max(durations)}")
    print(f"  Average: {sum(durations) / len(durations):.2f}")
    print(f"  All positive: {all(d >= 0 for d in durations)}")
else:
    print("No 'At Completion Duration' data found")

calc_durations = []
for act in activities:
    if 'calculated_duration' in act:
        dur = act['calculated_duration']
        if pd.notna(dur):
            calc_durations.append(dur)

if calc_durations:
    print(f"\nActivities with 'calculated_duration': {len(calc_durations)}")
    print(f"  Min: {min(calc_durations)}")
    print(f"  Max: {max(calc_durations)}")
    print(f"  Average: {sum(calc_durations) / len(calc_durations):.2f}")
    print(f"  All positive: {all(d >= 0 for d in calc_durations)}")
else:
    print("\nNo 'calculated_duration' data found")
print()

# Create analyzer and test
print("=" * 80)
print("STEP 4: Running DCMA Analyzer")
print("=" * 80)

analyzer = DCMAAnalyzer(schedule_data)
print(f"DataFrame shape: {analyzer.df.shape}")
print(f"DataFrame columns: {list(analyzer.df.columns)}")
print()

# Check if predecessor_list exists in DataFrame
if 'predecessor_list' in analyzer.df.columns:
    print("✅ 'predecessor_list' column exists in DataFrame")

    # Check types
    sample = analyzer.df['predecessor_list'].iloc[0]
    print(f"  Type of first predecessor_list: {type(sample)}")
    print(f"  Value: {sample}")

    # Count non-empty
    non_empty = analyzer.df['predecessor_list'].apply(lambda x: len(x) > 0 if isinstance(x, list) else False).sum()
    print(f"  Activities with non-empty predecessor_list: {non_empty}")
else:
    print("❌ 'predecessor_list' column NOT FOUND in DataFrame!")
print()

# Run analysis
results = analyzer.analyze()
metrics = results['metrics']

print("=" * 80)
print("STEP 5: DCMA Analysis Results")
print("=" * 80)

# Check relationship metrics
if 'relationship_types' in metrics:
    rel_types = metrics['relationship_types']
    print(f"✅ Relationship Types Analysis:")
    print(f"  Total relationships: {rel_types.get('total', 0)}")
    print(f"  Counts: {rel_types.get('counts', {})}")
    print(f"  Percentages: {rel_types.get('percentages', {})}")
else:
    print("❌ No relationship_types in metrics")
print()

# Check lag metrics
if 'negative_lags' in metrics:
    neg = metrics['negative_lags']
    print(f"✅ Negative Lags Analysis:")
    print(f"  Count: {neg.get('count', 0)}")
    print(f"  Status: {neg.get('status', 'unknown')}")
else:
    print("❌ No negative_lags in metrics")
print()

if 'positive_lags' in metrics:
    pos = metrics['positive_lags']
    print(f"✅ Positive Lags Analysis:")
    print(f"  Count: {pos.get('count', 0)}")
    print(f"  Total relationships: {pos.get('total_relationships', 0)}")
    print(f"  Percentage: {pos.get('percentage', 0)}%")
    print(f"  Status: {pos.get('status', 'unknown')}")
else:
    print("❌ No positive_lags in metrics")
print()

# Check duration metrics
if 'average_duration' in metrics:
    avg_dur = metrics['average_duration']
    print(f"✅ Duration Analysis:")
    print(f"  Mean: {avg_dur.get('mean', 0)}")
    print(f"  Median: {avg_dur.get('median', 0)}")
    print(f"  Min: {avg_dur.get('min', 0)}")
    print(f"  Max: {avg_dur.get('max', 0)}")
    print(f"  Status: {avg_dur.get('status', 'unknown')}")
else:
    print("❌ No average_duration in metrics")
print()

print("=" * 80)
print("STEP 6: Summary")
print("=" * 80)

print(f"Total issues found: {len(results.get('issues', []))}")
for issue in results.get('issues', [])[:5]:
    print(f"  - [{issue['severity']}] {issue['title']}")

print("\n✅ Debug complete!")
