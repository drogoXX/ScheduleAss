# CSV Parser Documentation - Relationship Logic Processing

## Overview

The Schedule Quality Analyzer's CSV parser (`src/parsers/schedule_parser.py`) properly handles complex predecessor/successor relationships from Primavera P6 exports, including all relationship types and lag values.

## ✅ Supported Formats

The parser successfully handles all P6 relationship notation patterns:

### 1. Simple Relationships
```
"A21800: FS"
```
**Parsed to:**
```python
[{'activity': 'A21800', 'type': 'FS', 'lag': 0}]
```

### 2. Multiple Relationships
```
"A21550: FF, A21800: FS"
```
**Parsed to:**
```python
[
    {'activity': 'A21550', 'type': 'FF', 'lag': 0},
    {'activity': 'A21800', 'type': 'FS', 'lag': 0}
]
```

### 3. Relationships with Positive Lags
```
"A21740: FF 10"
```
**Parsed to:**
```python
[{'activity': 'A21740', 'type': 'FF', 'lag': 10}]
```

### 4. Relationships with Negative Lags (Leads)
```
"A30820: FF -5"
```
**Parsed to:**
```python
[{'activity': 'A30820', 'type': 'FF', 'lag': -5}]
```

### 5. Complex Multi-Relationship Strings
```
"A34350: FS, A7410: FS, A7480: FS, A30820: FF -5, A34380: FS -4, A30830: FS"
```
**Parsed to:**
```python
[
    {'activity': 'A34350', 'type': 'FS', 'lag': 0},
    {'activity': 'A7410', 'type': 'FS', 'lag': 0},
    {'activity': 'A7480', 'type': 'FS', 'lag': 0},
    {'activity': 'A30820', 'type': 'FF', 'lag': -5},
    {'activity': 'A34380', 'type': 'FS', 'lag': -4},
    {'activity': 'A30830', 'type': 'FS', 'lag': 0}
]
```

## Relationship Types Supported

All four P6 relationship types are fully supported:

| Type | Full Name | Description |
|------|-----------|-------------|
| **FS** | Finish-to-Start | Successor starts when predecessor finishes |
| **FF** | Finish-to-Finish | Successor finishes when predecessor finishes |
| **SS** | Start-to-Start | Successor starts when predecessor starts |
| **SF** | Start-to-Finish | Successor finishes when predecessor starts |

## Lag Value Handling

The parser correctly interprets all lag notations:

- **No lag specified**: Defaults to `lag: 0`
- **Positive lag** (e.g., `FF 10`): Stored as `lag: 10` (10-day delay)
- **Negative lag** (e.g., `FF -5`): Stored as `lag: -5` (5-day lead)

## CSV Column Mapping

The parser prioritizes and processes columns in this order:

### For Predecessors:
1. **"Predecessor Details"** (preferred) - Contains full relationship notation
2. **"Predecessors"** (fallback) - Simple Activity IDs only

### For Successors:
1. **"Successor Details"** (preferred) - Contains full relationship notation
2. **"Successors"** (fallback) - Simple Activity IDs only

## Data Structure Output

For each activity in the schedule, the parser creates:

```python
{
    'Activity ID': 'A21550',
    'Activity Name': 'Foundation Concrete',
    'Activity Status': 'Not Started',
    # ... other standard P6 fields ...

    # Parsed relationship lists:
    'predecessor_list': [
        {'activity': 'A21550', 'type': 'FF', 'lag': 0},
        {'activity': 'A21800', 'type': 'FS', 'lag': 0}
    ],

    'successor_list': [
        {'activity': 'JCQV1010', 'type': 'FS', 'lag': 0},
        {'activity': 'A21970', 'type': 'FF', 'lag': 10},
        {'activity': 'A21740', 'type': 'FF', 'lag': 10}
    ],

    # Derived fields:
    'negative_lag_count': 0,
    'positive_lag_count': 2,
    'missing_predecessor': False,
    'missing_successor': False,
    'missing_logic': False
}
```

## Accessing Parsed Relationship Data

### In Analysis Code

The DCMA analyzer automatically accesses the parsed relationships:

```python
# In src/analysis/dcma_analyzer.py

def _analyze_negative_lags(self):
    """Analyze negative lags (leads)"""
    negative_lags = []

    for idx, row in self.df.iterrows():
        # Access parsed predecessor list
        predecessors = row.get('predecessor_list', [])

        for pred in predecessors:
            # Each pred is a dict with 'activity', 'type', 'lag'
            if pred.get('lag', 0) < 0:
                negative_lags.append({
                    'activity_id': row['Activity ID'],
                    'predecessor': pred['activity'],
                    'relationship_type': pred['type'],
                    'lag': pred['lag']
                })

    # Results automatically appear in metrics and dashboards
    self.metrics['negative_lags'] = {
        'count': len(negative_lags),
        'activities': negative_lags
    }
```

### In Custom Analysis

You can access the parsed data in your own code:

```python
# After parsing the CSV
schedule_data = parser.parse_csv(file_content, file_name)

# Access activities
activities = schedule_data['activities']

for activity in activities:
    activity_id = activity['Activity ID']

    # Get predecessors
    predecessors = activity.get('predecessor_list', [])
    for pred in predecessors:
        print(f"{activity_id} has predecessor {pred['activity']}")
        print(f"  Relationship: {pred['type']}")
        print(f"  Lag: {pred['lag']} days")

    # Get successors
    successors = activity.get('successor_list', [])
    for succ in successors:
        print(f"{activity_id} has successor {succ['activity']}")
        print(f"  Relationship: {succ['type']}")
        print(f"  Lag: {succ['lag']} days")
```

## Regex Pattern Details

The parser uses this regex pattern to extract relationship information:

```python
r'([A-Za-z0-9_-]+)\s*:\s*([A-Z]{2})\s*([-]?\d+)?'
```

**Pattern Breakdown:**
- `([A-Za-z0-9_-]+)` - Activity ID (alphanumeric, underscore, hyphen)
- `\s*:\s*` - Colon with optional whitespace
- `([A-Z]{2})` - Relationship type (exactly 2 uppercase letters)
- `\s*([-]?\d+)?` - Optional lag (negative or positive integer)

**Handles Edge Cases:**
- ✅ Extra whitespace around colons
- ✅ Extra whitespace before lag values
- ✅ Negative signs for leads
- ✅ Activity IDs with numbers, underscores, hyphens
- ✅ Empty cells or missing values
- ✅ Multiple relationships separated by commas

## Error Handling

The parser includes comprehensive error handling:

1. **Missing Data**: Returns empty list if cell is empty/null
2. **Malformed Data**: Logs warning and skips unparseable relationships
3. **Invalid Columns**: Falls back to simple columns or returns empty lists
4. **Whitespace**: Automatically strips and normalizes whitespace

All warnings are collected and available in the parse result:

```python
schedule_data = parser.parse_csv(file_content, file_name)

if schedule_data['warnings']:
    for warning in schedule_data['warnings']:
        print(f"Warning: {warning}")
```

## Testing & Verification

The parser has been tested with all actual P6 export patterns:

### Test Results:
```
✅ Simple relationships (A21800: FS)
✅ Multiple relationships (A21550: FF, A21800: FS)
✅ Positive lags (A21740: FF 10)
✅ Negative lags (A30820: FF -5)
✅ Complex strings with 6+ relationships
✅ Mixed relationship types (FS, FF, SS, SF)
✅ Whitespace variations
✅ Empty/null values
```

**Test Command:**
```bash
python3 test_complex_parsing.py
```

**Expected Output:**
```
Total relationships parsed: 18
  - With positive lags: 4
  - With negative lags: 4
  - With no lag: 10

✅ ALL TESTS PASSED!
```

## Integration with DCMA Analysis

The parsed relationship data automatically feeds into:

### 1. Logic Quality Metrics
- **Negative Lags**: Counts and lists all negative lag relationships
- **Positive Lags**: Calculates percentage of relationships with positive lags
- **Relationship Types**: Distribution of FS/FF/SS/SF relationships

### 2. Issues Detection
- High Priority: Negative lags detected
- Medium Priority: Excessive positive lags (>5% of relationships)
- Low Priority: High non-FS relationship percentage

### 3. Visualizations
- Negative lags gauge (shows count)
- Positive lags gauge (shows percentage)
- Relationship type distribution chart

### 4. Reports
- DOCX: Executive summary with lag counts
- Excel: Detailed logic sheet with all relationship details

## Example: Complete Flow

```
1. User uploads P6 CSV with "Predecessor Details" column
   ↓
2. Parser reads and processes each activity row
   ↓
3. For each activity, parse "Predecessor Details" string:
   "A34350: FS, A7410: FS, A30820: FF -5, A34380: FS -4"
   ↓
4. Create structured list:
   [
     {'activity': 'A34350', 'type': 'FS', 'lag': 0},
     {'activity': 'A7410', 'type': 'FS', 'lag': 0},
     {'activity': 'A30820', 'type': 'FF', 'lag': -5},
     {'activity': 'A34380', 'type': 'FS', 'lag': -4}
   ]
   ↓
5. Store in activity record as 'predecessor_list'
   ↓
6. DCMA analyzer reads 'predecessor_list'
   ↓
7. Counts: 2 negative lags, 0 positive lags, 2 zero-lag relationships
   ↓
8. Displays in dashboard: "Negative Lags: 2"
   ↓
9. Exports to reports with full relationship details
```

## Troubleshooting

### Issue: Relationships not showing in metrics

**Check:**
1. CSV has "Predecessor Details" or "Successor Details" columns
2. Relationships formatted as "ActivityID: Type Lag"
3. No parsing warnings in upload logs

### Issue: Lags showing as 0

**Check:**
1. Lag value included in relationship string (e.g., "FF 10" not just "FF")
2. Space between relationship type and lag value
3. Negative sign directly before number (e.g., "-5" not "- 5")

### Issue: Some relationships missing

**Check:**
1. Relationships comma-separated
2. No special characters in Activity IDs
3. Relationship type is valid (FS, FF, SS, or SF)

## Files

- **Parser Implementation**: `src/parsers/schedule_parser.py`
- **Test Script**: `test_complex_parsing.py`
- **Verification Script**: `verify_csv.py`
- **DCMA Analyzer**: `src/analysis/dcma_analyzer.py`

## Summary

✅ **The parser is fully functional and handles ALL P6 relationship patterns**

The current implementation correctly:
- Parses all relationship types (FS, FF, SS, SF)
- Extracts lag values (positive and negative)
- Handles complex multi-relationship strings
- Processes comma-separated relationships
- Manages whitespace variations
- Provides error handling and warnings
- Stores data in accessible DataFrame structure
- Feeds into DCMA analysis automatically

**No changes needed** - the parser already meets all requirements!
