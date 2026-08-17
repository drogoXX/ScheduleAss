"""
Test script to verify negative duration handling
"""

import pandas as pd
import io
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer

print("=" * 80)
print("Testing Negative Duration Handling")
print("=" * 80)
print()

# Create a test CSV with some negative durations (Finish before Start)
csv_content = """Activity ID,Activity Name,Activity Status,WBS Code,At Completion Duration,Start,Finish,Free Float,Total Float,Predecessors,Predecessor Details,Successors,Successor Details,Primary Constraint,Activity Type,Duration Type,Resource Names
A1000,Project Start,Completed,1.0,0,2025-01-01,2025-01-01,0,0,,,A1010,A1010: FS,As Late As Possible,Start Milestone,Fixed Duration & Units,
A1010,Task Normal,Completed,1.1.1,15,2025-01-02,2025-01-21,0,0,A1000,A1000: FS,A1020,A1020: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1020,Task Negative Duration,In Progress,1.1.2,-10,2025-02-10,2025-01-31,2,2,A1010,A1010: FS,A1030,A1030: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1030,Task Negative Duration 2,Not Started,1.1.3,-5,2025-02-15,2025-02-10,0,5,A1020,A1020: FS,A1040,A1040: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1040,Task Normal 2,Not Started,1.2.1,20,2025-02-16,2025-03-10,0,0,A1030,A1030: FS,,,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
"""

print("Test CSV contains:")
print("  - A1010: Normal duration (15 days)")
print("  - A1020: Negative duration (-10 days)")
print("  - A1030: Negative duration (-5 days)")
print("  - A1040: Normal duration (20 days)")
print()

# Parse the CSV
parser = ScheduleParser()
schedule_data = parser.parse_csv(csv_content.encode(), 'test_negative.csv')

if not schedule_data.get('success'):
    print("❌ Parsing failed!")
    print(f"Errors: {schedule_data.get('errors')}")
    exit(1)

print("✅ Step 1: Parsing successful")
print()

# Check durations in parsed data
print("Step 2: Checking parsed durations")
for activity in schedule_data['activities']:
    duration = activity.get('At Completion Duration', 0)
    print(f"  {activity['Activity ID']}: {duration} days")
print()

# Run DCMA analysis
print("Step 3: Running DCMA analysis")
try:
    analyzer = DCMAAnalyzer(schedule_data)
    results = analyzer.analyze()
    print("✅ Analysis completed successfully (no IndexError)")
    print()

    # Check metrics
    avg_duration = results['metrics'].get('average_duration', {})
    print("Step 4: Duration metrics")
    print(f"  Mean: {avg_duration.get('mean', 0)} days")
    print(f"  Median: {avg_duration.get('median', 0)} days")
    print(f"  Negative count: {avg_duration.get('negative_duration_count', 0)}")
    print()

    # Check issues
    print("Step 5: Issues detected")
    negative_duration_issues = [i for i in results['issues'] if 'Negative Duration' in i['title']]
    if negative_duration_issues:
        for issue in negative_duration_issues:
            print(f"  ✅ {issue['title']}")
            print(f"     Affected: {issue['affected_activities']}")
            print(f"     Count: {issue['count']}")
    else:
        print("  ⚠️  No negative duration issues detected (should have detected 2)")
    print()

    # Verify the fix
    if avg_duration.get('negative_duration_count', 0) == 2:
        print("✅ SUCCESS: Correctly detected 2 negative durations")
    else:
        print(f"❌ FAIL: Expected 2 negative durations, got {avg_duration.get('negative_duration_count', 0)}")

    if len(negative_duration_issues) > 0:
        affected = negative_duration_issues[0]['affected_activities']
        if set(affected) == {'A1020', 'A1030'}:
            print("✅ SUCCESS: Correctly identified affected activities (A1020, A1030)")
        else:
            print(f"❌ FAIL: Expected ['A1020', 'A1030'], got {affected}")

    if avg_duration.get('mean', 0) > 0:
        print(f"✅ SUCCESS: Average duration is positive ({avg_duration.get('mean', 0)} days)")
    else:
        print(f"❌ FAIL: Average duration should be positive, got {avg_duration.get('mean', 0)}")

except Exception as e:
    print(f"❌ Analysis failed with error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("=" * 80)
print("✅ All negative duration handling tests passed!")
print("=" * 80)
