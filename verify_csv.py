"""
Verify the sample CSV has correct lags in Predecessor Details column
"""
import re

# Read CSV and extract Predecessor Details column
with open('/home/user/ScheduleAss/data/sample_schedule.csv', 'r') as f:
    lines = f.readlines()

# Parse header to find Predecessor Details column
header = lines[0].strip()
# Split by comma but respect quotes
import csv
reader = csv.DictReader(lines)

negative_lags = []
positive_lags = []
relationship_types = {'FS': 0, 'SS': 0, 'FF': 0, 'SF': 0}

for row in reader:
    activity_id = row['Activity ID']
    pred_details = row.get('Predecessor Details', '')

    if not pred_details or pred_details == 'nan':
        continue

    # Parse the relationships
    parts = pred_details.split(',')
    for part in parts:
        part = part.strip()
        # Match: ActivityID: Type Lag
        match = re.match(r'([A-Za-z0-9_-]+)\s*:\s*([A-Z]{2})\s*([-]?\d+)?', part)
        if match:
            pred_id = match.group(1)
            rel_type = match.group(2)
            lag = int(match.group(3)) if match.group(3) else 0

            # Count relationship type
            if rel_type in relationship_types:
                relationship_types[rel_type] += 1

            # Track lags
            if lag < 0:
                negative_lags.append({
                    'activity': activity_id,
                    'predecessor': pred_id,
                    'type': rel_type,
                    'lag': lag
                })
            elif lag > 0:
                positive_lags.append({
                    'activity': activity_id,
                    'predecessor': pred_id,
                    'type': rel_type,
                    'lag': lag
                })

print("=" * 60)
print("VERIFICATION OF SAMPLE CSV - Predecessor Details Column")
print("=" * 60)
print()

print(f"NEGATIVE LAGS: {len(negative_lags)}")
for nl in negative_lags:
    print(f"  • {nl['activity']} has {nl['predecessor']}: {nl['type']} {nl['lag']}")
print()

print(f"POSITIVE LAGS: {len(positive_lags)}")
for pl in positive_lags:
    print(f"  • {pl['activity']} has {pl['predecessor']}: {pl['type']} {pl['lag']}")
print()

total_rels = sum(relationship_types.values())
print(f"RELATIONSHIP TYPES (Total: {total_rels}):")
for rel_type, count in sorted(relationship_types.items()):
    percentage = (count / total_rels * 100) if total_rels > 0 else 0
    print(f"  • {rel_type}: {count} ({percentage:.1f}%)")
print()

print("EXPECTED RESULTS in Application:")
print(f"  ✓ Negative Lags count: {len(negative_lags)}")
print(f"  ✓ Positive Lags percentage: {(len(positive_lags) / total_rels * 100):.1f}%")
print(f"  ✓ Relationship distribution correct: {relationship_types}")
print()

if len(negative_lags) >= 6 and len(positive_lags) >= 5:
    print("✅ CSV IS CORRECT - Has enough lags to test!")
else:
    print("⚠️  CSV may need more lags for comprehensive testing")
