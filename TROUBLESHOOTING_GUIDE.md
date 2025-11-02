# Troubleshooting Guide: Relationship Data and Duration Issues

## Overview

This guide addresses two common issues users may encounter:
1. **"No relationship data available"** in Logic Quality Metrics and Relationship Types Distribution
2. **Negative duration values** in Duration Analysis

## Issue 1: No Relationship Data Available

### Symptoms
- Logic Quality Metrics show zero values
- Relationship Types Distribution shows "No relationship data available"
- Negative and positive lag counts are 0

### Root Causes

#### Missing Relationship Columns
The most common cause is that your CSV file is missing the required relationship columns.

**Required Columns** (in order of preference):
1. **`Predecessor Details`** (BEST) - Contains full relationship information with types and lags
   - Format: `ActivityID: Type Lag`
   - Examples:
     - `A100: FS` - Finish-to-Start with no lag
     - `A100: FF 10` - Finish-to-Finish with 10-day positive lag
     - `A100: SS -5` - Start-to-Start with 5-day negative lag (lead)
     - `A100: FS, A200: FF 10, A300: SS -5` - Multiple relationships

2. **`Predecessors`** (FALLBACK) - Contains only Activity IDs
   - Format: `ActivityID, ActivityID, ...`
   - Example: `A100, A200, A300`
   - **Limitation**: Defaults all relationships to FS with 0 lag
   - **Impact**: Relationship types and lags will NOT be accurate

3. **NONE** - No relationship columns
   - **Result**: Complete loss of relationship data
   - **Error**: "CRITICAL: No 'Predecessor Details' or 'Predecessors' column found"

### How to Fix

#### Step 1: Check Your P6 Export Settings

When exporting from Primavera P6 to CSV, ensure you include these columns:

**Essential Relationship Columns:**
- ☑️ `Predecessor Details` (or `Predecessor Detail`)
- ☑️ `Successor Details` (or `Successor Detail`)
- ☑️ `Predecessors` (if Details not available)
- ☑️ `Successors` (if Details not available)

**Export Steps in P6:**
1. Open your schedule in P6
2. Go to File → Export
3. Select "Spreadsheet (XLS)" or "CSV" format
4. In the column selection dialog, ensure relationship columns are checked
5. Export and verify the CSV contains the columns

#### Step 2: Verify CSV Format

Open your exported CSV in a text editor or Excel and check:

**Good Example:**
```csv
Activity ID,Activity Name,Predecessor Details,Successor Details
A100,Foundation,A50: FS,A150: FS
A150,Walls,"A100: FS, A120: SS -5",A200: FF 10
A200,Roof,A150: FF 10,A250: FS
```

**Bad Example (Missing relationship info):**
```csv
Activity ID,Activity Name,Start,Finish
A100,Foundation,2025-01-01,2025-01-15
A150,Walls,2025-01-16,2025-02-01
```

#### Step 3: Re-upload to Application

1. Go to **Upload Schedule** page
2. Upload your corrected CSV file
3. Check for warnings during parsing:
   - ✅ Green: "Using 'Predecessor Details'" - Full data available
   - ⚠️ Orange: "Using 'Predecessors' column" - Limited data
   - 🔴 Red: "CRITICAL: No relationship columns found" - No data

4. View the **Analysis Dashboard** and check:
   - Relationship Types Distribution should show a bar chart
   - Logic Quality Metrics should show lag counts
   - Overview should show relationship statistics

### Verification

After re-uploading, you should see:
- **Relationship Types**: FS, SS, FF, SF distribution (FS typically 80-90%)
- **Negative Lags**: Count of activities with leads
- **Positive Lags**: Percentage of relationships with lags
- **Total Relationships**: Should match your schedule's logic links

---

## Issue 2: Negative Duration Values

### Symptoms
- Average duration shows negative values (e.g., -15.2 days)
- Median duration is negative
- Duration histogram shows negative bars

### Root Causes

#### Data Quality Issues
The most common causes are:

1. **Finish Date Before Start Date**
   - Activity has Finish < Start
   - Usually due to:
     - Manual date entry errors
     - Incorrect baseline data
     - Timezone conversion issues
     - Schedule updates not properly calculated

2. **Missing or Invalid Duration Column**
   - `At Completion Duration` column is missing
   - Duration values are manually entered incorrectly
   - Duration calculation in P6 is not up to date

3. **Date Format Issues**
   - Start/Finish dates not in expected format
   - Date parsing errors during CSV import
   - Excel date serial numbers instead of dates

### How to Fix

#### Step 1: Identify Problem Activities

1. Upload your schedule
2. Go to **Analysis Dashboard**
3. Check the **Issues** tab for:
   - 🔴 "Negative Durations Detected: X activities"
   - View the list of affected Activity IDs

#### Step 2: Fix in P6

1. Open your schedule in P6
2. For each affected activity:
   ```
   Activity ID: A100
   Start: 2025-02-15
   Finish: 2025-02-10  ← ERROR: Finish is before Start!
   ```

3. **Fix Options:**
   - **Option A**: Swap Start/Finish dates if reversed
   - **Option B**: Recalculate schedule (F9 in P6)
   - **Option C**: Check and fix activity logic
   - **Option D**: Verify constraint types (avoid Must Finish On before Start)

#### Step 3: Verify Duration Column

Ensure your CSV includes the `At Completion Duration` column:

**Good Example:**
```csv
Activity ID,Activity Name,Start,Finish,At Completion Duration
A100,Foundation,2025-01-01,2025-01-15,15
A150,Walls,2025-01-16,2025-02-01,15
```

**Best Practice:**
- `At Completion Duration` should always be positive
- Duration = (Finish - Start) in working days
- Check P6 calendar is correctly configured

#### Step 4: Re-export and Upload

1. Fix issues in P6
2. Re-export CSV with corrected data
3. Upload to application
4. Verify Duration Analysis shows positive values

### Application Improvements

**New Features (v1.0.4):**

✅ **Automatic Detection**: The analyzer now detects negative durations and:
- Uses absolute values for average/median calculations
- Shows warning: "X activities have negative durations"
- Creates a high-severity issue with affected activities
- Adds recommendation to fix in P6

✅ **Enhanced Warnings**: The dashboard now shows:
- Count of activities with negative durations
- Data quality warnings section
- Detailed explanations of issues

---

## Common Scenarios

### Scenario 1: "I just uploaded my schedule and see no relationship data"

**Solution:**
1. Check the **Data Quality Warnings** section on the Overview tab
2. Look for: "CRITICAL: No 'Predecessor Details' or 'Predecessors' column found"
3. Re-export from P6 with relationship columns included
4. Re-upload the corrected CSV

### Scenario 2: "My relationships show but all are FS with no lags"

**Solution:**
1. Check warnings for: "Using 'Predecessors' column (Activity IDs only)"
2. Your CSV has `Predecessors` but not `Predecessor Details`
3. Re-export from P6 ensuring `Predecessor Details` column is included
4. This column contains the relationship types (FS/FF/SS/SF) and lag values

### Scenario 3: "Duration shows -15 days average"

**Solution:**
1. Check the **Issues** tab for "Negative Durations Detected"
2. View the list of affected activities
3. Open your schedule in P6 and check those activities
4. Look for activities where Finish Date < Start Date
5. Fix the dates or recalculate the schedule
6. Re-export and re-upload

### Scenario 4: "Some relationships work but others don't"

**Solution:**
1. Check if some activities have relationships and others don't
2. Verify all activities have predecessor information in the CSV
3. Check for parsing errors:
   - Incorrect format in Predecessor Details column
   - Special characters or encoding issues
   - Empty cells vs. "None" text

---

## Testing Your CSV

Use this checklist before uploading:

### Relationship Data
- [ ] CSV contains `Predecessor Details` column
- [ ] Column format is: `ActivityID: Type Lag` (e.g., `A100: FF 10`)
- [ ] Multiple relationships are comma-separated
- [ ] Relationship types are two-letter codes: FS, FF, SS, SF
- [ ] Lag values include sign for negatives (e.g., `-5` not `5-`)

### Duration Data
- [ ] CSV contains `At Completion Duration` column
- [ ] All duration values are positive numbers
- [ ] Start dates are before Finish dates for all activities
- [ ] Duration = (Finish - Start) in working days

### Required Columns
- [ ] Activity ID
- [ ] Activity Name
- [ ] Activity Status
- [ ] Start (date format: YYYY-MM-DD or MM/DD/YYYY)
- [ ] Finish (date format: YYYY-MM-DD or MM/DD/YYYY)
- [ ] Total Float
- [ ] Duration Type

---

## Debug Checklist

If issues persist, work through this checklist:

1. **Upload a new schedule**
   - [ ] File uploads successfully
   - [ ] Parsing completes without errors
   - [ ] Check for warnings in the upload confirmation

2. **Check Overview Tab**
   - [ ] Health score is calculated (not 0)
   - [ ] Total activities count is correct
   - [ ] Data Quality Warnings section shows any issues

3. **Check Detailed Metrics Tab**
   - [ ] Logic Quality Metrics show non-zero values
   - [ ] Relationship Types Distribution shows chart (not "No data")
   - [ ] Duration Analysis shows positive values

4. **Check Issues Tab**
   - [ ] Issues are listed (if any)
   - [ ] Look for data quality issues
   - [ ] Note affected activities

5. **Check Activities Tab**
   - [ ] All activities are listed
   - [ ] Activity details are correct
   - [ ] Predecessor/Successor data is visible

---

## Support

If you've followed this guide and still have issues:

1. **Verify Sample Data Works**
   - Upload `data/sample_schedule.csv`
   - Confirm all metrics display correctly
   - This confirms the application is working

2. **Compare Your CSV to Sample**
   - Open both CSVs side by side
   - Check column names match exactly
   - Verify data format is similar

3. **Export Test Data from P6**
   - Create a small test schedule (5-10 activities)
   - Add relationships with different types and lags
   - Export and test with the application

4. **Check Application Logs**
   - Look for error messages during upload
   - Note any warnings or parsing errors
   - Review the Data Quality Warnings section

---

## Version History

**v1.0.4** (2025-11-02)
- ✅ Enhanced parser warnings for missing relationship columns
- ✅ Critical warning when no relationship columns found
- ✅ Better dashboard messages for missing data
- ✅ Automatic detection and handling of negative durations
- ✅ Data quality warnings section in Overview tab
- ✅ Improved error messages with actionable solutions

**v1.0.3** (2025-11-02)
- ✅ Parser verification and comprehensive documentation
- ✅ Confirmed parser handles all P6 relationship formats

**v1.0.2** (2025-11-02)
- ✅ Fixed multi-session support for database manager
- ✅ Session state initialization improvements

**v1.0.1** (2025-11-01)
- ✅ Fixed sample CSV data - moved lags to Predecessor Details
- ✅ Verified negative lag count (7) and positive lag count (6)
- ✅ Relationship type distribution now accurate
