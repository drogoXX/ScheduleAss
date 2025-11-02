"""
Test to simulate how data flows through session state storage
"""

import json
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer

print("=" * 80)
print("Testing Session State Simulation")
print("=" * 80)
print()

# Parse CSV
parser = ScheduleParser()
with open('data/sample_schedule.csv', 'rb') as f:
    file_content = f.read()

schedule_data = parser.parse_csv(file_content, 'sample_schedule.csv')

print("Step 1: Parse CSV - ✅")
print(f"  Total activities: {schedule_data['total_activities']}")
print()

# Simulate storing in session state by converting to JSON and back
# This is what happens when Streamlit stores complex objects
print("Step 2: Simulate session state storage (JSON serialization)")
try:
    # Try to serialize to JSON (this is what Streamlit does internally)
    json_str = json.dumps(schedule_data)
    print("  ✅ JSON serialization successful")

    # Deserialize back
    schedule_data_restored = json.loads(json_str)
    print("  ✅ JSON deserialization successful")
except Exception as e:
    print(f"  ❌ JSON serialization failed: {e}")
    schedule_data_restored = schedule_data
print()

# Check if data is still correct
print("Step 3: Check restored data")
activities = schedule_data_restored['activities']

# Check first activity with relationships
sample_activity = None
for act in activities:
    if 'predecessor_list' in act and len(act['predecessor_list']) > 0:
        sample_activity = act
        break

if sample_activity:
    print(f"  Sample activity: {sample_activity['Activity ID']}")
    print(f"  Predecessor list type: {type(sample_activity['predecessor_list'])}")
    print(f"  Predecessor list: {sample_activity['predecessor_list']}")
else:
    print("  ⚠️  No activities with predecessors found in restored data!")

# Count relationships in restored data
total_predecessors = 0
for act in activities:
    pred_list = act.get('predecessor_list', [])
    if pred_list and len(pred_list) > 0:
        total_predecessors += len(pred_list)

print(f"  Total predecessors in restored data: {total_predecessors}")
print()

# Run analyzer on restored data
print("Step 4: Run DCMA Analyzer on restored data")
try:
    analyzer = DCMAAnalyzer(schedule_data_restored)
    results = analyzer.analyze()

    rel_types = results['metrics'].get('relationship_types', {})
    print(f"  Total relationships found: {rel_types.get('total', 0)}")
    print(f"  Relationship counts: {rel_types.get('counts', {})}")

    neg_lags = results['metrics'].get('negative_lags', {})
    print(f"  Negative lags: {neg_lags.get('count', 0)}")

    pos_lags = results['metrics'].get('positive_lags', {})
    print(f"  Positive lags: {pos_lags.get('count', 0)} ({pos_lags.get('percentage', 0)}%)")

    avg_dur = results['metrics'].get('average_duration', {})
    print(f"  Average duration: {avg_dur.get('mean', 0)} days")

    if rel_types.get('total', 0) > 0:
        print("\n  ✅ Analysis successful - data preserved through JSON serialization!")
    else:
        print("\n  ❌ Analysis failed - relationship data lost!")

except Exception as e:
    print(f"  ❌ Analyzer failed: {e}")
    import traceback
    traceback.print_exc()
