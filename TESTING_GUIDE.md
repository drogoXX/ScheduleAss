# Testing Guide - Relationship Logic Processing

## Problem Identified

The sample CSV had negative lags in the **Successor Details** column, but the DCMA analyzer reads from the **Predecessor Details** column. This has been fixed.

## What Was Fixed

### Code (Already Working Correctly) ✅
- `src/parsers/schedule_parser.py` - Correctly reads "Predecessor Details" and "Successor Details"
- `src/analysis/dcma_analyzer.py` - Correctly analyzes predecessor_list for lags
- Regex pattern correctly parses: `A21740: FF 10` format

### Data (FIXED) ✅
- `data/sample_schedule.csv` - Now has lags in **Predecessor Details** column

## Verification Before Testing

Run the verification script to confirm the CSV is correct:

```bash
python3 verify_csv.py
```

**Expected Output:**
```
NEGATIVE LAGS: 7
  • A1060 has A2010: SS -10
  • A1060 has A2040: SS -5
  • A1060 has A2050: SS -10
  • A1080 has A1060: FF -3
  • A1100 has A2000: SS -15
  • A1110 has A2030: SS -5
  • A1150 has A2020: SS -30

POSITIVE LAGS: 6
  • A1070 has A2030: FS 5
  • A1090 has A1080: FS 7
  • A1140 has A1130: SS 5
  • A2020 has A2010: FS 5
  • A2030 has A2000: SS 10
  • A2040 has A1030: FS 10

RELATIONSHIP TYPES (Total: 34):
  • FS: 25 (73.5%)
  • SS: 8 (23.5%)
  • FF: 1 (2.9%)

✅ CSV IS CORRECT - Has enough lags to test!
```

## How to Test in Application

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Start the Application

```bash
streamlit run app.py
```

The application will open at `http://localhost:8501`

### Step 3: Login

**Use Admin account:**
- Username: `admin`
- Password: `admin123`

### Step 4: Upload Sample Schedule

1. Click **"Upload Schedule"** in the sidebar
2. **Create a new project:**
   - Project Name: `Test EPC Project`
   - Project Code: `TEST-001`
   - Description: `Testing relationship logic processing`
   - Click "Create Project"
3. **Upload the CSV:**
   - Click "Browse files" or drag and drop
   - Select: `data/sample_schedule.csv`
   - Click "Upload and Analyze"
4. **Wait for analysis** (should take 10-30 seconds)

### Step 5: Verify Results

#### Expected Results in "Analysis Dashboard" → "Overview" Tab:

**Health Score:**
- Should be **< 80** (due to negative lags and excessive positive lags)
- Rating: Likely "Fair" or "Poor"

**Quick Stats (4 columns):**
- **Negative Lags:** Should show **7**
- **Positive Lags %:** Should show **~17.6%**
- **Hard Constraints %:** Should show **~7.4%** (2 out of 27)
- **Missing Logic:** Should show **0**

#### Expected Results in "Detailed Metrics" Tab:

**Negative Lags Gauge:**
- Should show **7** (in red)
- Should be flagged as failing (target = 0)

**Positive Lags Gauge:**
- Should show **17.6%** (in orange/yellow)
- Should show warning (above 5% target)

**Relationship Types Distribution Chart:**
- **FS (Finish-to-Start):** ~73.5% (blue bar)
- **SS (Start-to-Start):** ~23.5% (orange bar)
- **FF (Finish-to-Finish):** ~2.9% (green bar)
- **SF (Start-to-Finish):** 0% (red bar)

#### Expected Results in "Issues" Tab:

**High Priority Issues:**
1. **"Negative Lags Detected: 7"**
   - Description: Negative lags (leads) indicate activities starting before predecessors finish
   - Recommendation: Review and eliminate negative lags
   - Affected activities: A1060, A1080, A1100, A1110, A1150

**Medium Priority Issues:**
1. **"Excessive Positive Lags: 17.6%"**
   - Description: Found 6 positive lags (17.6% of relationships). Target is ≤5%
   - Recommendation: Review positive lags to ensure they represent actual waiting time

#### Expected Results in "Recommendations" Tab:

Should see recommendations for:
- Eliminating negative lags (High Priority)
- Reducing positive lags (Medium Priority)
- Reviewing schedule logic (Medium Priority)

#### Expected Results in "Activities" Tab:

**Filter to see activities with lags:**
- Search for "A1060" - should show as having multiple predecessor relationships
- Search for "A1100" - should show SS -15 lag from A2000
- Download CSV and check the data

### Step 6: Generate Reports

Go to **"Reports"** page:

1. **Generate DOCX Report:**
   - Click "Generate DOCX Report"
   - Download and open the Word document
   - **Verify:** Issues summary should list 7 negative lags

2. **Generate Excel Report:**
   - Click "Generate Excel Report"
   - Download and open the Excel file
   - **Check "Metrics Detail" sheet:** Should list all 7 negative lags
   - **Check "Logic" sheet:** Should show relationship details with lags

## Troubleshooting

### If metrics show 0 negative lags:

1. **Check if you uploaded the NEW CSV:**
   - The file must be from the latest commit (cbf95ae)
   - Run `git pull` to ensure you have the latest version

2. **Clear Streamlit cache:**
   - Stop the application (Ctrl+C)
   - Delete `.streamlit/cache` folder if it exists
   - Restart: `streamlit run app.py`

3. **Verify CSV in file system:**
   ```bash
   python3 verify_csv.py
   ```
   Should show 7 negative lags

4. **Check browser cache:**
   - Hard refresh the page (Ctrl+Shift+R on Windows/Linux, Cmd+Shift+R on Mac)
   - Or try in incognito/private browsing mode

### If positive lags percentage is 0%:

Same steps as above - ensure you're using the updated CSV file.

### If relationship types don't show SS or FF:

Same steps as above - ensure you're using the updated CSV file.

## Summary of Expected Metrics

| Metric | Expected Value | Status |
|--------|----------------|--------|
| Negative Lags | 7 | ❌ FAIL (target: 0) |
| Positive Lags % | 17.6% | ⚠️ WARNING (target: ≤5%) |
| Hard Constraints % | 7.4% | ✅ PASS (target: ≤10%) |
| Missing Logic | 0 | ✅ PASS (target: 0) |
| Relationship Types | FS: 73.5%, SS: 23.5%, FF: 2.9% | ✅ CORRECT |
| Health Score | 60-75 | Fair to Poor |

## Files Modified

1. `src/parsers/schedule_parser.py` - Parser (already correct)
2. `src/analysis/dcma_analyzer.py` - Analyzer (already correct)
3. `data/sample_schedule.csv` - **FIXED** - Now has lags in Predecessor Details
4. `CHANGELOG.md` - Documentation
5. `verify_csv.py` - Verification script (NEW)
6. `test_regex.py` - Regex test (NEW)

## Git Commits

- `2a6d97c` - Fix relationship logic processing (parser code)
- `cbf95ae` - Fix sample CSV (add lags to Predecessor Details) ← **CURRENT**

---

**If you see the expected results above, the relationship logic processing is working correctly!** ✅
