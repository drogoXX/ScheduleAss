"""
Test to verify duration analysis uses At Completion Duration(d) and excludes milestones
"""

import pandas as pd
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer

print("=" * 80)
print("Testing Duration Analysis with Milestones")
print("=" * 80)
print()

# Create test CSV with:
# - At Completion Duration(d) column (P6 format with suffix)
# - Mix of regular activities and milestones
# - Milestones have duration = 0
csv_content = """Activity ID,Activity Name,Activity Status,WBS Code,At Completion Duration(d),Start,Finish,Free Float,Total Float,Predecessors,Predecessor Details,Successors,Successor Details,Primary Constraint,Activity Type,Duration Type,Resource Names
A1000,Project Start,Completed,1.0,0,2025-01-01,2025-01-01,0,0,,,A1010,A1010: FS,As Late As Possible,Start Milestone,Fixed Duration & Units,
A1010,Mobilization,Completed,1.1,15,2025-01-02,2025-01-21,0,0,A1000,A1000: FS,A1020,A1020: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1020,Foundation Work,In Progress,1.2,30,2025-01-22,2025-02-28,2,2,A1010,A1010: FS,A1030,A1030: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1025,Foundation Complete,Not Started,1.2.1,0,2025-03-01,2025-03-01,0,0,A1020,A1020: FS,A1030,A1030: FS,As Late As Possible,Finish Milestone,Fixed Duration & Units,
A1030,Structural Work,Not Started,1.3,45,2025-03-02,2025-04-30,0,0,A1020,A1020: FS,A1040,A1040: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1035,Structure 50% Complete,Not Started,1.3.1,0,2025-04-01,2025-04-01,0,0,A1030,A1030: SS 30,A1040,A1040: FS,As Late As Possible,Level of Effort Milestone,Fixed Duration & Units,
A1040,MEP Installation,Not Started,1.4,60,2025-05-01,2025-07-15,0,0,A1030,A1030: FS,A1050,A1050: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1050,Project Complete,Not Started,2.0,0,2025-07-16,2025-07-16,0,0,A1040,A1040: FS,,,As Late As Possible,Finish Milestone,Fixed Duration & Units,
"""

print("Test CSV contains:")
print("  - 8 total activities")
print("  - 4 regular tasks (durations: 15, 30, 45, 60)")
print("  - 4 milestones (durations: 0, 0, 0, 0)")
print("  - Column name: 'At Completion Duration(d)' (P6 format)")
print()

# Parse the CSV
print("Step 1: Parsing CSV")
print("-" * 80)

parser = ScheduleParser()
schedule_data = parser.parse_csv(csv_content.encode(), 'test_with_milestones.csv')

if not schedule_data.get('success'):
    print("❌ Parsing failed!")
    print(f"Errors: {schedule_data.get('errors')}")
    exit(1)

print(f"✅ Parsing successful - {schedule_data['total_activities']} activities")

# Check for column normalization
warnings = schedule_data.get('warnings', [])
normalization_warnings = [w for w in warnings if 'Normalized column name' in w]
if normalization_warnings:
    for warning in normalization_warnings:
        print(f"  {warning}")

print()

# Check parsed data
print("Step 2: Checking parsed data")
print("-" * 80)

df = pd.DataFrame(schedule_data['activities'])

# Check column name
if 'At Completion Duration' in df.columns:
    print("✅ Column normalized to 'At Completion Duration'")
else:
    print("❌ Expected column 'At Completion Duration' not found")
    exit(1)

# Check activity types
if 'Activity Type' in df.columns:
    milestone_count = df['Activity Type'].str.contains('Milestone', case=False, na=False).sum()
    task_count = len(df) - milestone_count
    print(f"✅ Found {milestone_count} milestones and {task_count} tasks")
else:
    print("⚠️  No 'Activity Type' column found")

# Show duration values
durations = df['At Completion Duration'].tolist()
print(f"  Durations from P6: {durations}")

print()

# Run DCMA analysis
print("Step 3: Running DCMA Analysis")
print("-" * 80)

try:
    analyzer = DCMAAnalyzer(schedule_data)
    results = analyzer.analyze()
    metrics = results['metrics']

    avg_duration_data = metrics.get('average_duration', {})

    print("✅ Analysis completed")
    print()
    print("Duration Analysis Results:")
    print(f"  Mean: {avg_duration_data.get('mean', 0)} days")
    print(f"  Median: {avg_duration_data.get('median', 0)} days")
    print(f"  Min: {avg_duration_data.get('min', 0)} days")
    print(f"  Max: {avg_duration_data.get('max', 0)} days")
    print(f"  Activities analyzed: {avg_duration_data.get('total_activities_analyzed', 0)}")
    print(f"  Milestones excluded: {avg_duration_data.get('milestones_excluded', 0)}")
    print(f"  Source column: {avg_duration_data.get('source_column', 'Unknown')}")

    # Check for negative duration issue
    if 'negative_duration_count' in avg_duration_data:
        print(f"  ⚠️  Negative duration count: {avg_duration_data.get('negative_duration_count', 0)}")

    print()

    # Verify results
    print("Step 4: Verification")
    print("-" * 80)

    expected_mean = (15 + 30 + 45 + 60) / 4  # Average of 4 tasks (excluding 4 milestones)
    expected_median = (30 + 45) / 2  # Median of [15, 30, 45, 60]
    expected_analyzed = 4  # 4 tasks
    expected_excluded = 4  # 4 milestones

    success = True

    if abs(avg_duration_data.get('mean', 0) - expected_mean) < 0.1:
        print(f"✅ Mean correct: {avg_duration_data.get('mean', 0)} (expected: {expected_mean})")
    else:
        print(f"❌ Mean WRONG: {avg_duration_data.get('mean', 0)} (expected: {expected_mean})")
        success = False

    if abs(avg_duration_data.get('median', 0) - expected_median) < 0.1:
        print(f"✅ Median correct: {avg_duration_data.get('median', 0)} (expected: {expected_median})")
    else:
        print(f"❌ Median WRONG: {avg_duration_data.get('median', 0)} (expected: {expected_median})")
        success = False

    if avg_duration_data.get('total_activities_analyzed', 0) == expected_analyzed:
        print(f"✅ Activities analyzed correct: {avg_duration_data.get('total_activities_analyzed', 0)} (expected: {expected_analyzed})")
    else:
        print(f"❌ Activities analyzed WRONG: {avg_duration_data.get('total_activities_analyzed', 0)} (expected: {expected_analyzed})")
        success = False

    if avg_duration_data.get('milestones_excluded', 0) == expected_excluded:
        print(f"✅ Milestones excluded correct: {avg_duration_data.get('milestones_excluded', 0)} (expected: {expected_excluded})")
    else:
        print(f"❌ Milestones excluded WRONG: {avg_duration_data.get('milestones_excluded', 0)} (expected: {expected_excluded})")
        success = False

    if avg_duration_data.get('source_column', '') == 'At Completion Duration':
        print(f"✅ Source column correct: '{avg_duration_data.get('source_column', '')}'")
    else:
        print(f"❌ Source column WRONG: '{avg_duration_data.get('source_column', '')}' (expected: 'At Completion Duration')")
        success = False

    # Check for negative duration issues
    negative_issues = [i for i in results['issues'] if 'Negative Duration' in i['title']]
    if len(negative_issues) == 0:
        print(f"✅ No negative duration issues (correct - using P6 durations)")
    else:
        print(f"❌ Found negative duration issues: {len(negative_issues)} (should be 0)")
        success = False

    print()

    if success:
        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print()
        print("Summary:")
        print(f"  • Milestones correctly excluded from duration analysis")
        print(f"  • Using 'At Completion Duration' from P6 (not calculated_duration)")
        print(f"  • No negative duration warnings")
        print(f"  • Metrics calculated correctly for tasks only")
    else:
        print("=" * 80)
        print("❌ SOME TESTS FAILED")
        print("=" * 80)

except Exception as e:
    print(f"❌ Analysis failed: {e}")
    import traceback
    traceback.print_exc()
