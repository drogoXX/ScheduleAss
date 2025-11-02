"""
Quick test to verify relationship parsing
"""
import sys
sys.path.insert(0, '/home/user/ScheduleAss')

from src.parsers.schedule_parser import ScheduleParser

# Test the parser with sample data
parser = ScheduleParser()

# Read the sample CSV
with open('/home/user/ScheduleAss/data/sample_schedule.csv', 'rb') as f:
    content = f.read()

# Parse it
result = parser.parse_csv(content, 'sample_schedule.csv')

if result['success']:
    print("✅ Parsing successful!")
    print(f"Total activities: {result['total_activities']}")
    print(f"Warnings: {result.get('warnings', [])}")
    print()

    # Check a few activities with known lags
    activities = result['activities']

    # Check A1080 - should have FF -3 from A1060
    a1080 = [a for a in activities if a['Activity ID'] == 'A1080'][0]
    print(f"A1080 (Foundation Concrete):")
    print(f"  Predecessor list: {a1080.get('predecessor_list', [])}")
    print(f"  Negative lag count: {a1080.get('negative_lag_count', 0)}")
    print()

    # Check A1090 - should have FS 7 from A1080
    a1090 = [a for a in activities if a['Activity ID'] == 'A1090'][0]
    print(f"A1090 (Foundation Curing):")
    print(f"  Predecessor list: {a1090.get('predecessor_list', [])}")
    print(f"  Positive lag count: {a1090.get('positive_lag_count', 0)}")
    print()

    # Check A2000 - should have SS -15 in successors to A1100
    a2000 = [a for a in activities if a['Activity ID'] == 'A2000'][0]
    print(f"A2000 (Procurement Long Lead):")
    print(f"  Successor list: {a2000.get('successor_list', [])}")
    print()

    # Count total lags
    total_negative = sum(a.get('negative_lag_count', 0) for a in activities)
    total_positive = sum(a.get('positive_lag_count', 0) for a in activities)

    print(f"Total negative lags across all activities: {total_negative}")
    print(f"Total positive lags across all activities: {total_positive}")

else:
    print("❌ Parsing failed!")
    print(f"Errors: {result.get('errors', [])}")
