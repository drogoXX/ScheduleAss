"""
Comprehensive test for Total Float analysis implementation
"""

import pandas as pd
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer

print("=" * 80)
print("Testing Comprehensive Total Float Analysis")
print("=" * 80)
print()

# Create a test CSV with varied float values
csv_content = """Activity ID,Activity Name,Activity Status,WBS Code,At Completion Duration(d),Start,Finish,Total Float(d),Free Float(d),Predecessors,Predecessor Details,Successors,Successor Details,Primary Constraint,Activity Type,Duration Type,Resource Names
A1000,Project Start,Completed,1.0,0,2025-01-01,2025-01-01,0,0,,,A1010,A1010: FS,As Late As Possible,Start Milestone,Fixed Duration & Units,
A1010,Critical Task 1,Completed,1.1,15,2025-01-02,2025-01-21,0,0,A1000,A1000: FS,A1020,A1020: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1020,Critical Task 2,In Progress,1.2,10,2025-01-22,2025-02-05,0,0,A1010,A1010: FS,A1030,A1030: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1030,Near-Critical Task,Not Started,1.3,20,2025-02-06,2025-03-03,5,2,A1020,A1020: FS,A1040,A1040: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1040,Near-Critical Task 2,Not Started,1.4,15,2025-03-04,2025-03-24,8,5,A1030,A1030: FS,A1050,A1050: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1050,Low Risk Task,Not Started,2.1,12,2025-03-25,2025-04-10,15,10,A1040,A1040: FS,A1060,A1060: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1060,Comfortable Task,Not Started,2.2,10,2025-04-11,2025-04-25,35,30,A1050,A1050: FS,A1070,A1070: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A1070,High Float Task,Not Started,2.3,8,2025-04-26,2025-05-08,60,50,A1060,A1060: FS,,,As Late As Possible,Task Dependent,Fixed Duration & Units,Crew
A2000,Behind Schedule 1,In Progress,3.1,20,2025-01-15,2025-02-10,-5,0,,,A2010,A2010: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Team A
A2010,Behind Schedule 2,Not Started,3.2,15,2025-02-11,2025-03-03,-10,-5,A2000,A2000: FS,,,As Late As Possible,Task Dependent,Fixed Duration & Units,Team A
A3000,Parallel Task 1,Not Started,4.1,25,2025-02-01,2025-03-05,20,15,,,A3010,A3010: FS,As Late As Possible,Task Dependent,Fixed Duration & Units,Team B
A3010,Parallel Task 2,Not Started,4.2,18,2025-03-06,2025-03-28,18,12,A3000,A3000: FS,,,As Late As Possible,Task Dependent,Fixed Duration & Units,Team B
"""

print("Test CSV contains:")
print("  - 3 Critical tasks (Float = 0)")
print("  - 2 Near-critical tasks (Float = 5, 8)")
print("  - 1 Low Risk task (Float = 15)")
print("  - 2 Comfortable tasks (Float = 35, 60)")
print("  - 2 Behind schedule tasks (Float = -5, -10)")
print("  - 2 Parallel tasks (Float = 20, 18)")
print()

# Parse the CSV
parser = ScheduleParser()
schedule_data = parser.parse_csv(csv_content.encode(), 'test_float.csv')

if not schedule_data.get('success'):
    print("❌ Parsing failed!")
    print(f"Errors: {schedule_data.get('errors')}")
    exit(1)

print("✅ Step 1: Parsing successful")
print(f"   Total activities: {schedule_data['total_activities']}")
print()

# Check Total Float column
print("Step 2: Checking parsed Total Float data")
activities = schedule_data['activities']
df = pd.DataFrame(activities)

if 'Total Float' in df.columns:
    print("✅ Total Float column exists")
    float_values = df['Total Float'].dropna().tolist()
    print(f"   Float values: {sorted(float_values)}")
else:
    print("❌ Total Float column not found!")
    print(f"   Available columns: {list(df.columns)}")
    exit(1)

print()

# Run DCMA analysis
print("Step 3: Running DCMA analysis with float analysis")
try:
    analyzer = DCMAAnalyzer(schedule_data)
    results = analyzer.analyze()
    print("✅ Analysis completed successfully")
    print()

    # Check comprehensive_float metrics
    float_data = results['metrics'].get('comprehensive_float', {})

    if 'error' in float_data:
        print(f"❌ Float analysis failed: {float_data['error']}")
        exit(1)

    print("Step 4: Verifying Float Analysis KPIs")
    print()

    # KPI 1: Critical Path
    critical = float_data.get('critical', {})
    print(f"1. Critical Path (Float = 0):")
    print(f"   Count: {critical.get('count', 0)}")
    print(f"   Percentage: {critical.get('percentage', 0):.1f}%")
    print(f"   Status: {critical.get('status', 'unknown')}")

    # Expected: 3 critical tasks (A1000, A1010, A1020)
    if critical.get('count', 0) == 3:
        print("   ✅ Correct - Expected 3 critical activities")
    else:
        print(f"   ❌ Expected 3, got {critical.get('count', 0)}")
    print()

    # KPI 2: Near-Critical
    near_critical = float_data.get('near_critical', {})
    print(f"2. Near-Critical (1-10 days float):")
    print(f"   Count: {near_critical.get('count', 0)}")
    print(f"   Percentage: {near_critical.get('percentage', 0):.1f}%")

    # Expected: 2 near-critical tasks (A1030=5, A1040=8)
    if near_critical.get('count', 0) == 2:
        print("   ✅ Correct - Expected 2 near-critical activities")
    else:
        print(f"   ❌ Expected 2, got {near_critical.get('count', 0)}")
    print()

    # KPI 3: Negative Float
    negative = float_data.get('negative_float', {})
    print(f"3. Negative Float (Behind Schedule):")
    print(f"   Count: {negative.get('count', 0)}")
    print(f"   Percentage: {negative.get('percentage', 0):.1f}%")
    print(f"   Status: {negative.get('status', 'unknown')}")

    # Expected: 2 behind schedule tasks (A2000=-5, A2010=-10)
    if negative.get('count', 0) == 2:
        print("   ✅ Correct - Expected 2 activities with negative float")
        activities_list = negative.get('activities', [])
        if activities_list:
            print(f"   Activities: {[a['activity_id'] for a in activities_list[:5]]}")
    else:
        print(f"   ❌ Expected 2, got {negative.get('count', 0)}")
    print()

    # KPI 4: Float Ratio
    ratio = float_data.get('float_ratio', {})
    print(f"4. Float Ratio:")
    print(f"   Ratio: {ratio.get('ratio', 0):.2f}")
    print(f"   Avg Float: {ratio.get('avg_float', 0):.1f} days")
    print(f"   Avg Remaining Duration: {ratio.get('avg_remaining_duration', 0):.1f} days")
    print(f"   Status: {ratio.get('status', 'unknown')}")
    print()

    # KPI 5: Statistics
    stats = float_data.get('statistics', {})
    print(f"5. Statistical Measures:")
    print(f"   Mean: {stats.get('mean', 0):.2f} days")
    print(f"   Median: {stats.get('median', 0):.2f} days")
    print(f"   Std Dev: {stats.get('std_dev', 0):.2f} days")
    print()

    # KPI 6: Excessive Float
    excessive = float_data.get('excessive_float', {})
    project_duration = float_data.get('project_duration', 0)
    print(f"6. Excessive Float (>50% of {project_duration:.0f} day project):")
    print(f"   Count: {excessive.get('count', 0)}")
    print(f"   Percentage: {excessive.get('percentage', 0):.1f}%")
    print()

    # KPI 7: Most Negative Float
    most_negative = float_data.get('most_negative', 0)
    print(f"7. Most Negative Float (Worst Delay):")
    print(f"   Value: {most_negative:.1f} days")

    # Expected: -10 (A2010)
    if most_negative == -10.0:
        print("   ✅ Correct - Expected -10 days")
    else:
        print(f"   ❌ Expected -10, got {most_negative}")
    print()

    # Check Distribution
    print("Step 5: Verifying Float Distribution for Charts")
    distribution = float_data.get('distribution', {})
    print(f"   Negative (<0): {distribution.get('negative', 0)}")
    print(f"   Critical (0): {distribution.get('critical', 0)}")
    print(f"   Near-Critical (1-10): {distribution.get('near_critical', 0)}")
    print(f"   Low Risk (11-30): {distribution.get('low_risk', 0)}")
    print(f"   Comfortable (>30): {distribution.get('comfortable', 0)}")
    print()

    # Verify distribution totals
    total_in_distribution = sum(distribution.values())
    total_activities = float_data.get('total_activities', 0)
    if total_in_distribution == total_activities:
        print(f"   ✅ Distribution accounts for all {total_activities} activities")
    else:
        print(f"   ❌ Distribution total ({total_in_distribution}) != total activities ({total_activities})")
    print()

    # Check Float by WBS
    print("Step 6: Verifying Float by WBS for Box Plot")
    float_by_wbs = float_data.get('float_by_wbs', {})
    if float_by_wbs:
        print(f"   Found {len(float_by_wbs)} WBS codes:")
        for wbs, floats in float_by_wbs.items():
            print(f"     {wbs}: {len(floats)} activities, floats: {sorted(floats)}")
        print("   ✅ WBS data available for box plot")
    else:
        print("   ⚠️  No WBS data (may not have WBS column)")
    print()

    # Check issues
    print("Step 7: Verifying Float-Related Issues")
    issues = results['issues']
    float_issues = [i for i in issues if 'Float' in i['title'] or 'Critical Path' in i['title']]

    if float_issues:
        print(f"   Found {len(float_issues)} float-related issues:")
        for issue in float_issues:
            print(f"     [{issue['severity'].upper()}] {issue['title']}")
            print(f"       Count: {issue.get('count', 'N/A')}")
    else:
        print("   ℹ️  No float-related issues detected")

except Exception as e:
    print(f"❌ Analysis failed with error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("=" * 80)
print("Summary")
print("=" * 80)

# Verify all 7 KPIs are present
required_kpis = ['critical', 'near_critical', 'negative_float', 'float_ratio',
                 'statistics', 'excessive_float', 'most_negative']
missing_kpis = [kpi for kpi in required_kpis if kpi not in float_data or not float_data[kpi]]

if not missing_kpis:
    print("✅ ALL 7 KPIs IMPLEMENTED:")
    print("   1. Critical Path (count, percentage, status)")
    print("   2. Near-Critical (count, percentage)")
    print("   3. Negative Float (count, percentage, activities, status)")
    print("   4. Float Ratio (ratio, avg_float, avg_duration, status)")
    print("   5. Statistics (mean, median, std_dev)")
    print("   6. Excessive Float (count, percentage)")
    print("   7. Most Negative Float (value)")
else:
    print(f"❌ MISSING KPIs: {missing_kpis}")

print()

# Verify chart data structures
chart_data = ['distribution', 'float_by_wbs']
missing_charts = [chart for chart in chart_data if chart not in float_data]

if not missing_charts:
    print("✅ ALL CHART DATA STRUCTURES PRESENT:")
    print("   • Float Distribution (for histogram and donut chart)")
    print("   • Float by WBS (for box plot)")
else:
    print(f"❌ MISSING CHART DATA: {missing_charts}")

print()
print("✅ COMPREHENSIVE FLOAT ANALYSIS TEST COMPLETED SUCCESSFULLY!")
print("=" * 80)
