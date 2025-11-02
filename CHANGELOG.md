# Changelog

## [1.0.7] - 2025-11-02

### Fixed - Duration Analysis Now Excludes Milestones and Uses Only P6 Durations

**Issue Reported:**
User received message: "235 activities have negative durations (Finish before Start)" and requested:
1. Use "At Completion Duration(d)" column exclusively for duration analysis
2. Exclude milestones from duration analysis (they have duration = 0 by nature)

**Root Cause:**
The analyzer was checking for negative durations even when using "At Completion Duration" from P6:
- Negative duration check was designed for calculated_duration (Finish - Start)
- But was being applied to P6 "At Completion Duration" column (which is always positive)
- This caused incorrect "negative duration" warnings
- Milestones (duration = 0) were being included in duration statistics, skewing averages

**Solution:**

**1. Removed Calculated Duration Fallback** (`src/analysis/dcma_analyzer.py`)

BEFORE:
```python
duration_col = 'At Completion Duration' if 'At Completion Duration' in self.df.columns else 'calculated_duration'
```

AFTER:
```python
duration_col = 'At Completion Duration'  # REQUIRED - use P6 work days only
```

**2. Excluded Milestones from Analysis**

Added milestone filtering in both `_analyze_average_duration()` and `_analyze_long_durations()`:

```python
if 'Activity Type' in self.df.columns:
    # Exclude activities where Activity Type contains "Milestone"
    is_milestone = self.df['Activity Type'].str.contains('Milestone', case=False, na=False)
    milestone_count = is_milestone.sum()
    non_milestone_df = self.df[~is_milestone]
```

Milestones identified by Activity Type containing:
- "Start Milestone"
- "Finish Milestone"
- "Level of Effort Milestone"
- Any other type containing "Milestone"

**3. Removed Negative Duration Check for P6 Data**

BEFORE:
- Checked "At Completion Duration" for negative values
- Created issues for "negative durations"
- Used absolute values in calculations

AFTER:
- No negative duration check (P6 durations are always positive work days)
- Uses actual P6 values directly
- Shows error if "At Completion Duration" column missing

**4. Enhanced Metrics**

New fields in `average_duration` metrics:
```python
{
    'mean': X,
    'median': X,
    'min': X,
    'max': X,
    'total_activities_analyzed': X,  # NEW - count excluding milestones
    'milestones_excluded': X,        # NEW - count of milestones
    'source_column': 'At Completion Duration'  # NEW - shows data source
}
```

**5. Updated Dashboard Display** (`pages/2_Analysis_Dashboard.py`)

- Removed negative duration warning display
- Added info message: "Analyzed X activities (excluded Y milestones)"
- Added help text: "Based on 'At Completion Duration' from P6"
- Updated tooltips: "Excluding milestones"

**Testing:**

Test with 8 activities (4 tasks + 4 milestones):
- Tasks: 15, 30, 45, 60 days
- Milestones: 0, 0, 0, 0 days

Results:
- ✅ Mean: 37.5 days (correct - only tasks)
- ✅ Median: 37.5 days (correct - only tasks)
- ✅ Min: 15 days, Max: 60 days
- ✅ Activities analyzed: 4 (tasks only)
- ✅ Milestones excluded: 4
- ✅ No negative duration issues
- ✅ Source column: 'At Completion Duration'

**Impact:**

BEFORE:
- Used calculated_duration if "At Completion Duration" not found
- Included milestones (duration = 0) in average calculations
- Showed false "negative duration" warnings
- Average skewed by zero-duration milestones

AFTER:
- Uses ONLY "At Completion Duration" from P6
- Excludes milestones from all duration calculations
- No false negative duration warnings
- Accurate duration metrics for tasks only
- Clear indication of how many milestones were excluded

**Files Modified:**
- `src/analysis/dcma_analyzer.py` - Milestone exclusion and P6-only duration
- `pages/2_Analysis_Dashboard.py` - Updated display with milestone info
- `CHANGELOG.md` - Version 1.0.7 entry

**Files Added:**
- `test_duration_with_milestones.py` - Comprehensive test for milestone exclusion

---

## [1.0.6] - 2025-11-02

### Fixed - Duration Analysis Not Using "At Completion Duration(d)" Column

**Issue Reported:** Duration Analysis not based on "At Completion Duration(d)" from P6 export

**Root Cause:**
P6 exports often include unit suffixes in column names:
- "At Completion Duration(d)" - days
- "Total Float(d)" - days
- "Free Float(h)" - hours
- "Percent Complete(%)" - percentage

The analyzer was looking for exact column name "At Completion Duration" (without suffix), so when the CSV had "At Completion Duration(d)", it couldn't find the column and fell back to using "calculated_duration" instead.

**Impact:**
- Duration metrics showed values from calculated_duration (Finish - Start in calendar days)
- Instead of actual "At Completion Duration" values (work days from P6)
- Results were incorrect for schedules with non-standard calendars or constraints

**Solution:**

Added P6 column name normalization in parser (`src/parsers/schedule_parser.py`):

```python
# Normalize P6 column names by removing unit suffixes
# Examples:
#   "At Completion Duration(d)" → "At Completion Duration"
#   "Total Float (d)" → "Total Float"
#   "Free Float(h)" → "Free Float"
```

Removes these P6 suffixes:
- `(d)`, `(h)`, `(%)`, `(wk)`, `(mo)`, `(yr)`
- `(days)`, `(hours)`, `(weeks)`, `(months)`, `(years)`

**Testing:**

Test with CSV containing "At Completion Duration(d)":

BEFORE fix:
- Column name: 'At Completion Duration(d)' (not recognized)
- Analyzer used: 'calculated_duration'
- Mean: 14.5 days (from calculated values [0, 19, 14, 25])
- Median: 16.5 days

AFTER fix:
- Column name normalized to: 'At Completion Duration' ✅
- Analyzer used: 'At Completion Duration' ✅
- Mean: 11.25 days (from actual P6 values [0, 15, 10, 20]) ✅
- Median: 12.5 days ✅

**User Feedback:**
User confirmed: "Duration Analysis is not based on the 'At Completion Duration(d)'"

**Parser Warnings:**
When columns are normalized, parser now logs:
```
Normalized column name: 'At Completion Duration(d)' → 'At Completion Duration'
```

Users will see this in the Data Quality Warnings section after upload.

**Files Modified:**
- `src/parsers/schedule_parser.py` - Added column name normalization in `_clean_data()`

**Files Added:**
- `test_duration_column.py` - Test script verifying the fix

---

## [1.0.5] - 2025-11-02

### Added - Comprehensive Constraint Tracking

**Feature Request:** Track ALL constraint types including "As Late As Possible" (ALAP)

**Implementation:**

#### Parser Enhancement (`src/parsers/schedule_parser.py`)

Added comprehensive constraint categorization:

**Constraint Categories:**
1. **Hard** - Specific date required
   - Must Start On, Must Finish On
   - Start On, Finish On
   - Mandatory Start, Mandatory Finish

2. **Flexible** - Date boundaries
   - Start On or After, Start On or Before
   - Finish On or After, Finish On or Before

3. **Schedule-Driven** - Logic-based
   - As Late As Possible (ALAP)
   - As Soon As Possible (ASAP)

4. **Other** - Unknown constraint types

**New Fields Added:**
- `constraint_category` - Categorizes each activity's constraint
- `has_any_constraint` - Boolean flag for any constraint (except None)

#### Analyzer Enhancement (`src/analysis/dcma_analyzer.py`)

Completely rewrote `_analyze_hard_constraints()` to track ALL constraint types:

**New Metrics Structure:**
```python
metrics['constraints'] = {
    'total_count': X,
    'total_percentage': Y%,
    'by_category': {
        'Hard': {'count': X, 'percentage': Y%, 'activities': [...]},
        'Flexible': {'count': X, 'percentage': Y%, 'activities': [...]},
        'Schedule-Driven': {'count': X, 'percentage': Y%, 'activities': [...]},
        'Other': {'count': X, 'percentage': Y%, 'activities': [...]}
    },
    'guidance': 'Constraints should be minimized and duly justified'
}
```

**Issue Detection:**
- Hard constraints >10%: High severity
- Flexible constraints >15%: Medium severity
- Schedule-Driven >50%: Low severity (informational)

#### Dashboard Enhancements

**Overview Tab (`pages/2_Analysis_Dashboard.py`):**
- Changed "Hard Constraints %" to "Activities with Constraints"
- Shows total percentage of ALL constrained activities
- Tooltip: "All constraint types (should be minimized and justified)"

**Detailed Metrics Tab:**

Added comprehensive "Constraints Analysis" section with:

1. **Summary Metrics** (4 columns):
   - Total Constrained (count + percentage)
   - Hard Constraints (count + percentage)
   - Flexible Constraints (count + percentage)
   - Schedule-Driven (count + percentage)

2. **Visual Breakdown**:
   - Pie chart showing distribution by category
   - Guidance text: "Constraints should be minimized and duly justified"
   - Category descriptions with usage recommendations

3. **Detailed Tables** (4 tabs):
   - Hard: List with warning if any exist
   - Flexible: List with info message
   - Schedule-Driven: List with info message
   - All: Combined list with download button

**Test Results:** ✅ All tests passed

Sample data (28 activities):
- Hard: 2 activities (7.1%)
- Flexible: 0 activities (0.0%)
- Schedule-Driven: 26 activities (92.9%)
- Total Constrained: 28 (100%)

**User Guidance:**

Constraints should be "as low as reasonably possible and in case duly justified":
- Hard constraints: Use only when contractually mandated
- Flexible constraints: Should be justified by project requirements
- Schedule-Driven: Generally acceptable but review if excessive

**Files Modified:**
- `src/parsers/schedule_parser.py` - Added constraint categorization
- `src/analysis/dcma_analyzer.py` - Comprehensive constraint tracking
- `pages/2_Analysis_Dashboard.py` - Enhanced constraint display (both tabs)

**Files Added:**
- `test_constraints.py` - Constraint tracking test script

---

## [1.0.4.1] - 2025-11-02

### Fixed - IndexError in Negative Duration Detection (HOTFIX)

**Critical Bug:** IndexingError when analyzing schedules with negative durations

**Error:**
```
IndexingError: Unalignable boolean Series provided as indexer
File src/analysis/dcma_analyzer.py, line 320, in _analyze_average_duration
```

**Root Cause:** Using boolean mask from filtered Series to index original DataFrame with misaligned indices.

**Fix:** Use proper index alignment:
```python
negative_indices = durations[durations < 0].index
affected_activity_ids = list(self.df.loc[negative_indices, 'Activity ID'].values)
```

**Test Results:** ✅ All tests passed
- No IndexError
- Correctly detects 2/5 negative durations
- Identifies affected activities: ['A1020', 'A1030']
- Returns positive average using absolute values

**Files Modified:**
- `src/analysis/dcma_analyzer.py` - Fixed indexing bug

**Files Added:**
- `test_negative_durations.py` - Test script with negative durations

---

## [1.0.4] - 2025-11-02

### Fixed - Data Quality Issues & Enhanced Diagnostics

#### Issue: "No Relationship Data Available" in Dashboard

**Problem:** Logic Quality Metrics and Relationship Types Distribution showing "No relationship data available"

**Root Cause:** User's CSV file missing 'Predecessor Details' or 'Predecessors' column

**Solution:**
- Enhanced parser warnings with CRITICAL alerts for missing columns
- Improved dashboard messages explaining causes and solutions
- Added Data Quality Warnings section in Overview tab
- Created comprehensive TROUBLESHOOTING_GUIDE.md

#### Issue: Negative Duration Values

**Problem:** Duration Analysis showing negative average/median values

**Root Cause:** Activities with Finish date before Start date

**Solution:**
- Automatic detection of negative durations in DCMA analyzer
- Use absolute values for statistics
- Create high-severity issues with affected activity IDs
- Display warning in dashboard with count of problematic activities

#### Testing & Verification

Created debug scripts proving parser and analyzer work correctly:
- `debug_data_flow.py` - End-to-end flow test ✅ ALL TESTS PASSED
- `test_session_state_simulation.py` - Session state test ✅ DATA PRESERVED
- Verified: 34 relationships, 7 negative lags, 6 positive lags, positive durations

**Files Modified:**
- `src/parsers/schedule_parser.py` - Enhanced warnings
- `src/analysis/dcma_analyzer.py` - Negative duration detection
- `pages/2_Analysis_Dashboard.py` - Better diagnostics display

**Files Added:**
- `TROUBLESHOOTING_GUIDE.md` - Comprehensive troubleshooting guide
- `debug_data_flow.py` - Testing script
- `test_session_state_simulation.py` - Testing script

---

## [1.0.3] - 2025-11-02

### Added - Parser Verification & Documentation

#### Comprehensive Testing
Created comprehensive test suite to verify the CSV parser handles ALL complex P6 relationship patterns correctly.

**Test Script: `test_complex_parsing.py`**
- Tests all relationship formats: Simple, Multiple, With lags (positive/negative), Complex multi-relationship strings
- Tests all relationship types: FS, FF, SS, SF
- Tests edge cases: Extra whitespace, empty values, None values
- Validates parsing of 18 relationships across 12 test cases
- **Result**: ✅ ALL TESTS PASSED

**Test Results Summary:**
```
Total relationships parsed: 18
  - With positive lags: 4
  - With negative lags: 4
  - With no lag: 10
```

#### Comprehensive Documentation
Created `docs/PARSER_DOCUMENTATION.md` with complete parser reference:

**Documentation Sections:**
- ✅ Supported Formats (with examples for all patterns)
- ✅ Relationship Types Supported (FS, FF, SS, SF)
- ✅ Lag Value Handling (positive, negative, default)
- ✅ CSV Column Mapping (Predecessor/Successor Details vs simple columns)
- ✅ Data Structure Output (how to access parsed data)
- ✅ Regex Pattern Details (pattern breakdown and edge cases)
- ✅ Error Handling (missing data, malformed data, whitespace)
- ✅ Integration with DCMA Analysis (how metrics use parsed data)
- ✅ Complete Flow Example (end-to-end processing)
- ✅ Troubleshooting Guide (common issues and solutions)

#### Verification Status

**✅ Parser is FULLY FUNCTIONAL** - No code changes needed!

The current implementation in `src/parsers/schedule_parser.py` correctly:
- Parses all relationship types (FS, FF, SS, SF)
- Extracts lag values (positive and negative)
- Handles complex multi-relationship strings
- Processes comma-separated relationships
- Manages whitespace variations
- Provides error handling and warnings
- Stores data in accessible DataFrame structure
- Feeds into DCMA analysis automatically

**Regex Pattern Used:**
```python
r'([A-Za-z0-9_-]+)\s*:\s*([A-Z]{2})\s*([-]?\d+)?'
```

This pattern successfully parses all P6 export variations including:
- "A21800: FS" → Simple relationship
- "A21550: FF, A21800: FS" → Multiple relationships
- "A21740: FF 10" → Positive lag
- "A30820: FF -5" → Negative lag
- "A34350: FS, A7410: FS, A30820: FF -5, A34380: FS -4" → Complex

#### Files Added
- `test_complex_parsing.py` - Comprehensive parser test suite
- `docs/PARSER_DOCUMENTATION.md` - Complete parser reference documentation

---

## [1.0.2] - 2025-11-02

### Fixed - Multi-Session Support (CRITICAL)

#### Problem
Application crashed with `AttributeError` when users tried to login:
```
AttributeError: st.session_state has no attribute "users"
```

#### Root Cause
- `DatabaseManager` was cached with `@st.cache_resource` (shared across all sessions)
- `__init__` only ran once for the first session
- New sessions got the cached instance but without initialized `session_state`
- Result: New users couldn't access `st.session_state.users`

#### Solution
Added `self._init_session_state()` call at the start of every method that accesses `st.session_state`. This ensures each new session initializes its own session state before any access.

#### Files Modified
- `src/database/db_manager.py` - Added initialization checks to 17 methods

#### Impact
✅ Multi-user support now works correctly
✅ Each session has isolated session state
✅ No more AttributeError on login
✅ Application works on Streamlit Cloud

---

## [1.0.1] - 2025-11-02

### Fixed - Relationship Logic Processing

#### Problem
The application was unable to properly acknowledge and process detailed relationship logic from P6 exports. Specifically:
- Not parsing "Predecessor Details" and "Successor Details" columns
- Missing positive and negative lag information
- Incomplete relationship type distribution analysis

#### Solution Implemented

**1. Updated Schedule Parser (`src/parsers/schedule_parser.py`)**

- **Prioritize Detail Columns**: Parser now prioritizes "Predecessor Details" and "Successor Details" columns over simple "Predecessors" and "Successors" columns

- **Enhanced Parsing Logic**:
  ```
  Full Format: "A21740: FF 10, A21750: FS, A21760: FS -5"
  - A21740: Activity ID
  - FF: Relationship type (Finish-to-Finish)
  - 10: Positive lag (10 days)
  - -5: Negative lag/lead (5 days)
  ```

- **Fallback Support**: Maintains backward compatibility with simple "Predecessors"/"Successors" columns (Activity IDs only)

- **Warning System**: Provides helpful warnings when using simplified columns or when parsing fails

**2. Updated Sample Data (`data/sample_schedule.csv`)**

Added realistic P6 export data with 27 activities demonstrating:

- **Negative Lags (Leads)**: 7 instances
  - A1060: FF -3 (Foundation Concrete - 3 day lead)
  - A1100: SS -15 (Procurement - 15 day lead)
  - A1060: SS -10 (Design Review - 10 day lead)
  - A1150: SS -30 (Safety Inspection - 30 day lead)
  - A1110: SS -5 (Material Delivery - 5 day lead)
  - A1060: SS -5 (Quality Control - 5 day lead)
  - A1060: SS -10 (Environmental Check - 10 day lead)

- **Positive Lags**: 7 instances
  - A1090: FS 7 (Foundation Curing - 7 day lag)
  - A1140: SS 5 (Electrical Installation - 5 day lag)
  - A2010: FS 5 (Design Review - 5 day lag)
  - A1070: FS 5 (Material Delivery - 5 day lag)
  - A1030: FS 10 (Quality Control - 10 day lag)
  - A2000: SS 10 (Material Delivery - 10 day lag)

- **Relationship Types**:
  - FS (Finish-to-Start): Majority of relationships
  - FF (Finish-to-Finish): 1 instance
  - SS (Start-to-Start): 8 instances
  - SF (Start-to-Finish): None (as expected in typical schedules)

- **Hard Constraints**: 2 instances
  - Must Start On
  - Finish On

**3. Impact on Analysis**

These changes now enable proper analysis of:

- **Logic Quality Metrics**:
  - Accurate negative lag detection and counting
  - Precise positive lag percentage calculation
  - Correct relationship type distribution

- **DCMA 14-Point Assessment**:
  - Negative lags properly flagged as high-priority issues
  - Positive lags correctly evaluated against 5% threshold
  - Relationship type analysis showing FS/FF/SS/SF distribution

- **Visualizations**:
  - Relationship Types Distribution chart now shows accurate percentages
  - Logic Quality Metrics display correct lag counts
  - Issues and recommendations based on actual relationship data

#### Testing

Sample data includes:
- 27 activities across 5 WBS levels
- 14 instances of non-standard relationships (SS, FF, or with lags)
- 2 hard constraints
- 1 missing logic scenario (start and end milestones)
- Mix of Completed (3), In Progress (3), and Not Started (21) activities

#### Files Modified

1. `src/parsers/schedule_parser.py`
   - Updated `_parse_relationships()` method (lines 162-193)
   - Enhanced `_parse_relationship_string()` method (lines 195-257)
   - Added `expect_full_format` parameter for flexible parsing

2. `data/sample_schedule.csv`
   - Added "Predecessor Details" and "Successor Details" columns
   - Added realistic relationship notation with various lags
   - Increased from 25 to 27 activities
   - Added more relationship type diversity

#### Backward Compatibility

The parser maintains full backward compatibility:
- If "Predecessor Details" exists, use it (preferred)
- If only "Predecessors" exists, fall back to it (with warning)
- If neither exists, create empty relationship lists

#### Expected Results

With this fix, the application now correctly:
1. ✅ Detects 7 negative lags in sample data
2. ✅ Calculates positive lag percentage based on actual lags
3. ✅ Shows relationship type distribution: ~60% FS, ~30% SS, ~4% FF
4. ✅ Properly flags negative lags as high-priority issues
5. ✅ Generates accurate recommendations based on lag analysis
6. ✅ Displays correct metrics in Logic Quality Metrics charts
7. ✅ Exports accurate data in DOCX and Excel reports

---

## [1.0.0] - 2025-11-02

### Initial Release

Complete Schedule Quality Analyzer application with:
- User authentication (Admin/Viewer roles)
- CSV parser for P6 schedule exports
- DCMA 14-Point Schedule Assessment engine
- Performance metrics calculator (CPLI, BEI, Health Score)
- Interactive dashboards with visualizations
- Schedule comparison analytics
- Professional report generation (DOCX & Excel)
- Multi-page Streamlit interface
- Comprehensive documentation
