# Schedule Quality Analyzer — User Guide

For planners, schedulers and project controls engineers using the application,
and for anyone who needs to defend a health score to a client.

Two parts:

1. [Using the application](#part-1--using-the-application)
2. [How the health score is set](#part-2--how-the-health-score-is-set)

---

## Part 1 — Using the application

### What it does

The application reads a Primavera P6 schedule exported as CSV and assesses it
against the **DCMA 14-Point Schedule Assessment**. It returns a set of metrics,
a list of issues, prioritised recommendations, and a single 0–100 health score.

It does not assess the GAO Schedule Assessment Guide, and does not read `.xer`
files. CSV export only.

### Roles

| Role | Can do |
| --- | --- |
| **Admin** | Everything: upload, analyse, delete, generate reports, manage users |
| **Viewer** | Read-only: dashboards, comparisons, report downloads |

Sessions expire after 60 minutes of inactivity. There are no shared or demo
accounts — each person gets their own, created by an admin under
**Settings → User Management**.

### Step 1 — Prepare the P6 export

Export from P6 as CSV with these columns.

**Required** — the file is rejected without them:

- Activity ID
- Activity Name
- Activity Status
- Start
- Finish
- Total Float
- Duration Type

**Strongly recommended** — several checks are skipped without them:

| Column | What depends on it |
| --- | --- |
| **Predecessor Details** | Every logic metric: leads, lags, relationship types, missing logic |
| **Successor Details** | Missing-successor detection, open ends |
| WBS Code | WBS analysis tab, per-area breakdowns |
| At Completion Duration | Duration checks |
| Free Float | Float analysis |
| Primary Constraint | Constraint checks |
| Activity Type | Milestone handling |
| Resource Names | Resource-loading check |

> **The single most important column is `Predecessor Details`.**
> The plain `Predecessors` column contains activity IDs only — no relationship
> type, no lag. If that is all you export, the application warns you and
> assumes every relationship is Finish-to-Start with zero lag. Leads and lags
> then read as zero regardless of what the schedule actually contains.

**Export dates as `YYYY-MM-DD` if you can.** P6 writes dates in the exporting
machine's locale with nothing to say which one it used, and `03/04/2025` is
genuinely ambiguous. The parser inspects every date in the file and picks the
only interpretation consistent with the data, telling you what it chose. If a
file is entirely ambiguous it says so rather than guessing silently — but an
ISO export removes the question altogether.

### Step 2 — Sign in

Open the application and sign in. Repeated failed attempts lock the account
temporarily.

### Step 3 — Create or select a project

**Upload Schedule → 1. Select or Create Project.**

A project groups successive versions of the same schedule. Project codes are
unique. Create the project once, then upload each revision against it — that is
what makes the Comparison page useful.

### Step 4 — Upload and analyse

**Upload Schedule → 2. Upload Schedule File**, then **3. Upload and Analyze**.

Preview the first ten rows to confirm the columns landed where you expect, then
run the analysis. A 1,200-activity schedule takes a few seconds.

**Read the warnings.** They are not noise. They tell you which date format was
detected, which columns were missing, which relationships could not be parsed,
and which dates could not be read. A schedule that analyses "successfully" with
five warnings may have been assessed on incomplete data.

### Step 5 — Review the analysis

**Analysis Dashboard**, seven tabs:

| Tab | What it holds |
| --- | --- |
| **Overview** | Health score, CPLI, BEI, headline counts, data-quality warnings |
| **Detailed Metrics** | Every DCMA check with its count, percentage and status |
| **Float Analysis** | Float distribution, negative float, float by WBS |
| **WBS Analysis** | Per-area breakdown and comparison |
| **Issues** | Findings by severity, with the affected activities |
| **Recommendations** | Prioritised actions with impact and effort |
| **Activities** | The parsed activity table |

On the Overview tab, **"How this score is calculated"** expands to the full
scoring breakdown for that schedule — every check, its measured value, its
target, its weight and its score. That table is the answer to "where did this
number come from".

### Step 6 — Compare versions

**Comparison.** Select two versions of the same project to see metrics
side-by-side with the movement between them. Improvements show green,
regressions red. Needs at least two schedules.

### Step 7 — Generate reports

**Reports.**

- **DOCX** — executive summary: cover page, health score, DCMA checklist,
  CPLI/BEI, issues, recommendations, methodology appendix. For stakeholders.
- **Excel** — full detail: summary, issues, complete activity list, logic
  breakdown, recommendations. For working the problem.

Exports are recorded in the audit log.

---

## Part 2 — How the health score is set

The health score is a **weighted average of twelve DCMA checks**, expressed
0–100.

Its thresholds come from the DCMA 14-Point Assessment. **Its weights do not** —
DCMA defines pass/fail criteria for each point, not a composite score. The
weights below are this application's assessment of relative severity. They are
published so they can be challenged and changed deliberately, rather than
buried in code.

### How one check is scored

Each check is measured as a percentage of the schedule, then scored 0–100:

- At or better than the **DCMA target** → scores **100**
- At or beyond the **zero bound** → scores **0**
- In between → declines **linearly**

For logic completeness (target ≤5%, zero at 30%):

| Measured | Score |
| --- | --- |
| 3% | 100 |
| 5% | 100 |
| 10% | 80 |
| 17.5% | 50 |
| 30% | 0 |
| 45% | 0 |

### The twelve checks

| DCMA | Check | Weight | Target | Scores 0 at | Critical |
| ---: | --- | ---: | ---: | ---: | :---: |
| 1 | Logic completeness | 22 | ≤5% | 30% | ● |
| 7 | Negative float | 12 | ≤0% | 20% | ● |
| 2 | Leads (negative lags) | 10 | ≤0% | 20% | ● |
| 5 | Hard constraints | 9 | ≤5% | 40% | |
| 3 | Lags (positive) | 7 | ≤5% | 40% | |
| 6 | High float (>44d) | 7 | ≤5% | 50% | |
| 8 | Long durations (>44d) | 7 | ≤5% | 50% | |
| 4 | Non-FS relationships | 6 | ≤10% | 50% | |
| 9 | Invalid dates | 6 | ≤0% | 10% | ● |
| 10 | Unresourced activities | 4 | ≤0% | 50% | |
| 13 | CPLI | 5 | ≥0.95 | ≤0.80 | |
| 14 | BEI | 5 | ≥0.95 | ≤0.80 | |
| | **Total** | **100** | | | |

Logic completeness carries the largest weight because every other network
metric depends on it: float, the critical path, CPLI and the relationship
checks are all meaningless in a schedule that is not properly linked.

**One open start and one open finish are expected** in any valid network — the
project's own beginning and end — and are excluded from the missing-logic
measurement. Without that exclusion a clean three-activity chain would measure
67% missing logic.

### Checks with no data

A check whose input column is absent is marked **n/a** and excluded, and the
remaining weights are renormalised over what could actually be measured.

It does **not** score as a silent pass. A schedule exported without resource
names is not credited with being fully resourced.

### Two rules beyond the average

A plain weighted average has a weakness: a catastrophic failure on one check
costs only that check's weight. A schedule with half its relationships as leads
would still average out near "Excellent". Two rules correct that.

**1. Data-sufficiency gates** — caps when the schedule cannot be meaningfully
assessed:

| Condition | Score capped at |
| --- | ---: |
| No relationship data at all | 25 |
| More than 50% of activities missing logic | 40 |

**2. Critical-check ceilings** — each *critical* check (marked ● above) that
fails outright, meaning it scores below 50, costs one rating band:

| Critical checks failed | Score capped at | Best possible rating |
| ---: | ---: | --- |
| 1 | 89 | Good |
| 2 | 74 | Fair |
| 3 or more | 59 | Poor |

Ceilings only ever lower a score. If the weighted average is already below the
ceiling, nothing changes and nothing is reported.

**Every cap that is applied is shown on the dashboard with its reason.** A
reduced score is never unexplained.

### Rating bands

| Score | Rating |
| --- | --- |
| 90–100 | Excellent |
| 75–89 | Good |
| 60–74 | Fair |
| 40–59 | Poor |
| 0–39 | Critical |

### Worked example

A real 1,261-activity P6 export:

| Check | Measured | Target | Score | Weight | Contribution |
| --- | ---: | ---: | ---: | ---: | ---: |
| Logic completeness | 15.38% | ≤5% | 58 | 22 | 12.87 |
| Negative float | 15.36% | ≤0% | 23 | 12 | 2.78 |
| Leads (negative lags) | 0.48% | ≤0% | 98 | 10 | 9.76 |
| Hard constraints | 0.56% | ≤5% | 100 | 9 | 9.00 |
| Lags (positive) | 1.11% | ≤5% | 100 | 7 | 7.00 |
| High float (>44d) | 49.02% | ≤5% | 2 | 7 | 0.15 |
| Long durations (>44d) | 2.13% | ≤5% | 100 | 7 | 7.00 |
| Non-FS relationships | 22.31% | ≤10% | 69 | 6 | 4.15 |
| Invalid dates | 0.00% | ≤0% | 100 | 6 | 6.00 |
| Unresourced activities | 0.00% | ≤0% | 100 | 4 | 4.00 |
| CPLI | 1.10 | ≥0.95 | 100 | 5 | 5.00 |
| BEI | 0.85 | ≥0.95 | 35 | 5 | 1.76 |
| | | | | **100** | **69.5** |

**Score 69.5 — Fair.**

Negative float scored 23, below 50, so it counts as a failed critical check and
sets a ceiling of 89. The average was already 69.5, so the ceiling did not
bind and no cap was reported.

Points recoverable, largest first: negative float **9.2**, logic completeness
**9.2**, high float **6.9**, BEI **3.3**, non-FS relationships **1.9**. Those
five account for all 30.5 points lost, and say exactly where to start.

### What the score is and is not

**It is** a transparent, reproducible summary of twelve DCMA checks, useful for
tracking one schedule across revisions and for directing attention to the worst
areas first.

**It is not:**

- a DCMA-defined figure — DCMA does not publish a composite score
- a substitute for reading the Issues tab
- comparable against scores from any other tool
- meaningful on a schedule that produced parse warnings about missing
  relationship or date data

Use it to answer "is this revision better than the last one, and where should I
look first". Do not use it as an acceptance criterion on its own.

### Changing the weighting

The weights are a business judgement, not a constant. They live in
`src/analysis/health_score.py` in the `COMPONENTS` table, with the gates and
ceilings directly below.

Changing them changes every score the application reports, including on
analyses already issued to clients. Re-run the test suite afterwards
(`python -m pytest tests/test_health_score.py`) — it asserts that the weights
sum to 100, that scoring stays proportional, and that a schedule with no logic
never outranks a well-linked one.

---

## Troubleshooting

| Message | Cause and fix |
| --- | --- |
| Missing required columns | Re-export from P6 including the required columns listed above |
| Date format is ambiguous | Every date could read either way. Re-export as `YYYY-MM-DD`, or set `APP_DATE_ORDER` to `day` or `month` |
| Dates are inconsistent | The file mixes day-first and month-first values. Re-export as `YYYY-MM-DD` |
| *n* values could not be read as a date | Those dates were left empty. Check the source cells for text or a stray format |
| Using 'Predecessors' column | Only activity IDs were available. Re-export with `Predecessor Details` for accurate lead/lag metrics |
| No relationship data | The export has no predecessor or successor columns. Logic metrics are unavailable and the score is capped at 25 |
| Duplicate column headers | Two columns share a name; re-export with unique headers |
| File exceeds the limit | Default ceiling is 50 MB — see `DEPLOYMENT.md` |
| Analysis failed, with a reference code | Quote the reference to your administrator; the full detail is in the application log |

---

See also: [README.md](README.md) for setup, [DEPLOYMENT.md](DEPLOYMENT.md) for
production configuration and backups.
