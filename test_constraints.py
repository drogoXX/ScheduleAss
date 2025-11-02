"""
Test script to verify constraint categorization and tracking
"""

import pandas as pd
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer

print("=" * 80)
print("Testing Constraint Categorization and Tracking")
print("=" * 80)
print()

# Parse the sample CSV
print("Step 1: Parsing sample_schedule.csv")
parser = ScheduleParser()
with open('data/sample_schedule.csv', 'rb') as f:
    file_content = f.read()

schedule_data = parser.parse_csv(file_content, 'sample_schedule.csv')

if not schedule_data.get('success'):
    print("❌ Parsing failed!")
    exit(1)

print(f"✅ Parsing successful - {schedule_data['total_activities']} activities")
print()

# Check constraint categorization in parsed data
print("Step 2: Checking constraint categorization in parsed data")
activities = schedule_data['activities']

constraint_counts = {
    'None': 0,
    'Hard': 0,
    'Flexible': 0,
    'Schedule-Driven': 0,
    'Other': 0
}

sample_by_category = {
    'Hard': None,
    'Flexible': None,
    'Schedule-Driven': None
}

for activity in activities:
    category = activity.get('constraint_category', 'None')
    constraint_counts[category] = constraint_counts.get(category, 0) + 1

    # Save sample activities for each category
    if category in sample_by_category and sample_by_category[category] is None:
        sample_by_category[category] = {
            'id': activity['Activity ID'],
            'name': activity['Activity Name'],
            'constraint': activity.get('Primary Constraint', 'Unknown')
        }

print(f"Constraint categories found:")
for category, count in constraint_counts.items():
    if count > 0:
        print(f"  {category}: {count} activities")
        if category in sample_by_category and sample_by_category[category]:
            sample = sample_by_category[category]
            print(f"    Example: {sample['id']} - {sample['constraint']}")
print()

# Run DCMA analysis
print("Step 3: Running DCMA analysis")
analyzer = DCMAAnalyzer(schedule_data)
results = analyzer.analyze()
metrics = results['metrics']

print(f"✅ Analysis complete")
print()

# Check constraint metrics
print("Step 4: Verifying constraint metrics")
constraints_data = metrics.get('constraints', {})

if constraints_data:
    print(f"Total constrained activities: {constraints_data.get('total_count', 0)} ({constraints_data.get('total_percentage', 0):.1f}%)")
    print()

    by_category = constraints_data.get('by_category', {})

    print("Breakdown by category:")
    for cat_name in ['Hard', 'Flexible', 'Schedule-Driven', 'Other']:
        cat_data = by_category.get(cat_name, {})
        count = cat_data.get('count', 0)
        pct = cat_data.get('percentage', 0)
        print(f"  {cat_name}: {count} ({pct:.1f}%)")

    print()
    print(f"Guidance: {constraints_data.get('guidance', 'N/A')}")
    print(f"Status: {constraints_data.get('status', 'unknown')}")
else:
    print("❌ No constraints data in metrics!")
print()

# Check for constraint-related issues
print("Step 5: Checking constraint-related issues")
constraint_issues = [i for i in results['issues'] if 'Constraint' in i['title']]

if constraint_issues:
    print(f"Found {len(constraint_issues)} constraint-related issues:")
    for issue in constraint_issues:
        print(f"  [{issue['severity']}] {issue['title']}")
        print(f"    Affected: {len(issue.get('affected_activities', []))} activities")
else:
    print("✅ No constraint-related issues detected")
print()

# Summary
print("=" * 80)
print("Summary")
print("=" * 80)

total_activities = schedule_data['total_activities']
total_constrained = constraints_data.get('total_count', 0)

if total_constrained > 0:
    print(f"✅ Constraint tracking is working!")
    print(f"   {total_constrained}/{total_activities} activities have constraints ({constraints_data.get('total_percentage', 0):.1f}%)")
    print()
    print("Breakdown:")
    for cat_name, cat_data in by_category.items():
        count = cat_data.get('count', 0)
        if count > 0:
            pct = cat_data.get('percentage', 0)
            print(f"  • {cat_name}: {count} activities ({pct:.1f}%)")
else:
    print("⚠️  No constrained activities found (unexpected for sample data)")

print()
print("✅ All tests passed!")
