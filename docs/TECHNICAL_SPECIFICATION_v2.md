# Schedule Assessment Platform — Technical Specification v2.0

**Status:** Option A (targeted refactor) in progress — see §17 for status and next steps
**Date:** 17 August 2026 (revised same day against `main` @ `8a1d3de`)
**Supersedes:** `Schedule_Quality_Analyzer_PRD.md`
**Target repository:** `github.com/drogoXX/ScheduleAss` (clean rewrite, history retained)

---

## 1. Purpose

This specification defines a ground-up rebuild of the schedule assessment application. The
existing codebase works and encodes real domain knowledge, but its architecture has degraded
to the point where correctness can no longer be demonstrated: the "database" is a dictionary
in browser session memory, analysis results embed megabytes of duplicated activity data, and
several DCMA checks silently substitute fabricated inputs when real ones are absent.

The rebuild has one governing objective: **every number the application prints must be
traceable to a documented rule, a declared denominator, and the specific activities that
produced it.** An assessment that cannot be defended in a schedule review meeting has no value,
regardless of how fast it renders.

Scope is deliberately narrowed to the **DCMA 14-Point Assessment** only. GAO framework content,
the parallel "comprehensive float" analysis, and the ad-hoc health scoring are removed.

---

## 2. What we keep

The current application solved a number of genuinely hard problems. These are requirements of
the new system, not optional carry-over. Each was learned from real P6 exports and re-deriving
them would be expensive.

### 2.1 P6 column normalisation

P6 exports append unit suffixes to column headers — `Total Float(d)`, `At Completion Duration(d)`,
`(*)Free Float(d)`. Header matching must normalise these before comparison, case-insensitively,
covering `(d) (h) (w) (m) (y) (%)` and the long forms `(days) (hours) (weeks) (months) (years)`.

**Extension required.** The current implementation matches the WBS column on the exact string
`WBS Code`. The export at `Schedule extract/P6_Extract.csv` names it `WBS`, so every WBS-dependent
feature silently degrades to "not available" for that export format. The new ingester must resolve
columns through a **declared alias table**, not exact strings, and must **fail loudly** when a
column backing an enabled check cannot be resolved.

### 2.2 Relationship parsing with type and lag

`Predecessor Details` / `Successor Details` carry full relationship notation
(`A21740: FF 10, A21750: FS, A21760: FS -5`). The bare `Predecessors` / `Successors` columns carry
activity IDs only. The current parser correctly prefers the Details columns, falls back to the bare
columns with an explicit warning, and defaults the fallback to `FS` with zero lag.

This behaviour is **retained exactly**, with one hardening: when only bare columns are available,
DCMA checks 2, 3 and 4 (Leads, Lags, Relationship Types) must report **Not Assessable** rather
than computing against fabricated `FS`/`0` defaults. Defaulting and then scoring is the single
most dangerous pattern in the current code.

### 2.3 Domain exclusion rules

Hard-won and correct. These were fixed in commits `02f288f` and `02edcbb` and must be preserved:

- **Milestones are excluded from duration tests.** A milestone has zero duration by nature;
  including it in a duration distribution corrupts the denominator. Detected via `Activity Type`
  containing "Milestone", case-insensitive.
- **Completed activities are excluded from float and duration tests.** DCMA tests forward-looking
  schedule quality. A completed activity's float is not actionable.
- **Missing-logic counts must be decomposed.** Reporting a single "missing logic" number invites
  exactly the reconciliation disputes that commit `02edcbb` fixed. The breakdown —
  *missing predecessor only*, *missing successor only*, *missing both*, *total unique* — is
  mandatory, and the report must state that activities missing both are counted once in the
  unique total and in each category total.
- **Constraint categorisation.** Three-way split — Hard (`Must Start On`, `Must Finish On`,
  `Start On`, `Finish On`, `Mandatory Start`, `Mandatory Finish`), Flexible (`Start On or After`
  and the other three boundary forms), Schedule-Driven (`As Late As Possible`, `As Soon As
  Possible`) — is more useful than a hard/soft binary and is retained.

### 2.4 WBS hierarchy decomposition

Splitting the WBS code into level columns and rolling metrics up by level is genuinely valuable
for EPC schedules and is retained. It becomes a **reporting dimension**, not a separate analysis
module: any DCMA check can be sliced by WBS level.

### 2.5 Performance characteristics already achieved

The optimisation work committed in `f79d5a6` established measured baselines the rebuild must
match or beat. On a 6,345-activity export: full pipeline 0.76 s, dashboard interaction 0.37 s.
The lesson encoded there — **never iterate a DataFrame row-wise when a columnar operation exists** —
is a standing rule, not a one-off fix.

---

## 3. Current state of `main`

> **Revised 17 August 2026.** The first draft of this section was written against the
> `restore/nov-2025` line. While the performance work was in progress, `main` absorbed the
> production-readiness effort (PRs #28–30, 71 files, +8,764/−1,487), which independently fixed
> four of the seven items originally listed for removal. This section now records what is
> genuinely outstanding. **The scope of the rebuild is materially smaller than first drafted.**

### 3.1 Already fixed on `main` — do not rebuild

| Item | Resolution on `main` |
|---|---|
| `session_state` as database | Replaced by a real SQLite backend with a declared schema, connection timeout and `check_same_thread=False`. |
| Hardcoded credentials | Gone. `src/auth/security.py` implements PBKDF2-SHA256 with per-user salt, configurable iterations, and rehash-on-login. A sound implementation, not a stopgap. |
| Ad-hoc root test scripts | Removed. Replaced by a 12-file `tests/` suite with `conftest.py`, `pytest.ini` and `requirements-dev.txt`, including `test_security.py` and `test_ui_safety.py`. **223 tests, all passing.** |
| No design system | `src/ui/` added: `theme.py`, `palette.py`, `charts.py`, `diagnostics.py`. |
| Row-wise pandas scans | Fixed in `f79d5a6`, merged to `main` in `8a1d3de`. `analyze()` 2.65 s → 0.45 s, output verified identical. |

Carrying these forward is now a **migration** concern, not a rebuild one. In particular the auth
implementation and the test suite should be moved across largely intact.

### 3.2 Still outstanding — the actual case for this work

| To remove or fix | Reason |
|---|---|
| **Fabricated data date** | `data_date` is never populated; falls back to `df['Start'].min()`. See §7.1. **The single strongest argument for this work.** |
| **BEI without a baseline** | Not a baseline execution index. See §7.1. |
| **CPLI approximation** | Self-documented as approximate, printed as the real metric. See §7.1. |
| ~~Ad-hoc health score~~ | **Largely resolved.** `src/analysis/health_score.py` now implements a proportional, weight-renormalising, per-component-explainable index. See §17.1. What remains from §8 is leading with the compliance fraction and printing the weights in the report appendix. |
| GAO framework content | Out of scope. A partial second framework is worse than none. |
| `comprehensive_float` module | Duplicates DCMA 6 and 7 at different thresholds with no stated basis. |
| Excel report generator | Superseded by DOCX (§10). Activity export remains available as CSV. |
| No calendar handling | 44-day thresholds evaluated without calendars; see §7.4. |
| No XER ingest | Every metadata gap above is closed by XER (§6.1). |
| `archive/`, `instance/*.db`, `.coverage` | Development detritus, still tracked. |

### 3.3 Consequence for the delivery strategy

With the database, authentication, test suite and design system already sound, a full clean-slate
rewrite would re-derive working code. The remaining defects are concentrated in **`core/`
correctness** — ingestion metadata, calendars, the DCMA rule set, and scoring — not in the
surrounding application.

The layered architecture of §4 remains the right target, since `main` has no separation between
analysis logic and Streamlit. But it is reachable by **extracting a pure `core/` package and
migrating the existing UI onto it**, rather than by emptying the repository. The delivery decision
between full rewrite and targeted refactor is recorded as open in §16.

---

## 4. Architecture

Four layers, strictly ordered. **A layer may only import from layers above it.** This is enforced
by an import-linter rule in CI, not by convention.

```
┌──────────────────────────────────────────────────────────────┐
│  core/          Pure Python. No Streamlit, no DB, no I/O.    │
│                 Ingestion, normalisation, DCMA rules, scoring.│
│                 Deterministic: same input -> same output.     │
├──────────────────────────────────────────────────────────────┤
│  persistence/   SQLAlchemy models, repositories, migrations.  │
│                 Depends on core types only.                   │
├──────────────────────────────────────────────────────────────┤
│  reporting/     DOCX generation. Consumes core result objects.│
├──────────────────────────────────────────────────────────────┤
│  ui/            Streamlit pages. Thin. No business logic.     │
└──────────────────────────────────────────────────────────────┘
```

The critical constraint is that **`core/` must be runnable without Streamlit**. This is what makes
the rules unit-testable, lets the assessment run in CI against reference schedules, and permits a
future CLI or API without rework. The current codebase cannot do this — `db_manager.py` imports
Streamlit to define what it calls a database.

```
src/
├─ core/
│  ├─ ingest/        readers (csv, xlsx, xer), column alias resolution, validation
│  ├─ model/         Schedule, Activity, Relationship, DataDate, Baseline (typed)
│  ├─ rules/         one module per DCMA check, uniform interface
│  ├─ scoring/       compliance roll-up (§8)
│  └─ ruleset.py     versioned thresholds + config
├─ persistence/
├─ reporting/docx/
└─ ui/
```

### 4.1 Uniform rule interface

Every DCMA check implements the same contract. This is what makes the assessment auditable and
the report generator generic.

```python
@dataclass(frozen=True)
class CheckResult:
    check_id: str                 # "DCMA-06"
    name: str                     # "High Float"
    status: Status                # PASS | FAIL | NOT_ASSESSABLE
    value: float | int | None     # measured result
    threshold: str                # "<= 5%"  (rendered from ruleset)
    denominator_label: str        # "incomplete, non-milestone activities"
    denominator_count: int
    numerator_count: int
    evidence: list[ActivityRef]   # capped; see §5.4
    evidence_truncated_at: int | None
    not_assessable_reason: str | None
    ruleset_version: str

class Check(Protocol):
    check_id: str
    required_fields: frozenset[str]      # drives NOT_ASSESSABLE automatically
    def evaluate(self, s: Schedule, cfg: RuleSet) -> CheckResult: ...
```

`required_fields` is the mechanism that eliminates silent degradation: the runner inspects the
normalised schedule, and any check whose required fields are absent returns `NOT_ASSESSABLE` with
a specific reason **before** its logic runs. No check can accidentally score against a default.

---

## 5. Data model and persistence

### 5.1 Database choice

**Current state:** `main` already uses SQLite directly via `sqlite3`, with a declared schema,
`timeout=30` and `check_same_thread=False`. This works and should not be discarded casually.

**Target: PostgreSQL 15+** for the shared-server deployment, SQLite for local development, accessed
through SQLAlchemy 2.x so one codebase serves both.

`main` already sets `PRAGMA journal_mode = WAL`, so concurrent readers are handled and the obvious
interim mitigation is in place.

Rationale for the eventual move: the deployment is a small team on a shared server, meaning
concurrent writes from independent Streamlit sessions. Even under WAL, SQLite serialises writers,
and `timeout=30` converts that contention into a 30-second stall rather than removing it — under
simultaneous uploads users see the app hang, not error. Postgres removes the failure mode and
provides `jsonb`, `timestamptz` and arrays the metric store uses directly.

**This is a migration, not a prerequisite.** The schema in §5.3 can be delivered on SQLite first
and moved to Postgres when concurrent-write pain is actually observed. Introducing SQLAlchemy at
the point the schema is rewritten costs little; rewriting a working, WAL-enabled `sqlite3` layer
purely to change engines, before the contention is real, is not justified.

### 5.2 Separating bulk data from metadata

The central storage mistake in the current design is treating one Python dict as both the record
and the payload. The rebuild splits them:

- **Relational tables** hold metadata, check results, and everything queried or aggregated.
- **Activity rows are never stored in the relational schema.** The normalised activity table is
  persisted once as a **Parquet blob**, addressed by the SHA-256 of the source upload. Parquet is
  columnar and typed, so loading only the columns a given view needs costs a fraction of rehydrating
  a JSON list of dicts.
- **Session state holds identifiers only** — `schedule_id`, `analysis_id`, filter selections.
  Never a DataFrame, never an activity list. This is the fix for the 3.77 MB-per-upload leak.

### 5.3 Schema

```sql
project(id, code UNIQUE, name, description, created_by, created_at)

upload(id, project_id, sha256 UNIQUE, filename, source_format,   -- xer | csv | xlsx
       size_bytes,
       storage_uri,              -- original file, retained indefinitely (§14.5)
       parquet_uri,              -- normalised activities
       data_date,                -- REQUIRED, see §7.1
       finish_date, finish_date_field,   -- which P6 field was used, printed in report
       calendar_basis,           -- 'xer_per_activity' | 'declared_default'
       declared_calendar,        -- e.g. '5x8h', when basis is declared_default
       is_baseline BOOL,
       uploaded_by, uploaded_at)

calendar(id, upload_id, p6_clndr_id, name, hours_per_day,
         workweek jsonb, exceptions jsonb)     -- from XER CALENDAR

baseline(id, project_id, upload_id,            -- upload_id -> a baseline XER
         label, is_current, created_at, created_by)

analysis(id, upload_id, baseline_id NULL, ruleset_version, ruleset_profile,
         engine_version, compliance_passed, compliance_applicable,
         quality_index NULL, checks_passed, checks_failed,
         checks_not_assessable, created_at)

check_result(id, analysis_id, check_id, status, value,
             numerator, denominator, threshold_text,
             not_assessable_reason)          -- one row per check

check_evidence(id, check_result_id, activity_id, activity_name,
               detail jsonb)                 -- capped per §5.4

attestation(id, analysis_id, check_id,          -- DCMA-12, see §14.3
            outcome,                            -- PASS | FAIL
            delay_days_applied, activity_tested,
            observed_finish_shift_days, notes,
            attested_by, attested_at)

audit_event(id, actor_id, action, entity_type, entity_id,
            detail jsonb, occurred_at)
```

`check_result` as **one row per check** rather than a JSON blob is what makes version-over-version
trending a SQL `GROUP BY` instead of a Python loop over nested dictionaries. Comparison — currently
a whole page of bespoke code — becomes a query.

### 5.4 Evidence capping

Evidence lists are capped at **200 activities per check**, with `evidence_truncated_at` recording
the true count. The current system stores every affected activity inside the metrics dict — 3,764
entries for one check, 1.02 MB per analysis — while the UI renders at most 20 and the report at
most a page. Full populations remain reachable via CSV export, which streams from Parquet.

### 5.5 Content-addressed caching

`upload.sha256` doubles as the analysis cache key. Re-uploading a byte-identical file with the same
`ruleset_version` returns the stored analysis instead of recomputing. This also gives free
deduplication and makes results reproducible by construction.

---

## 6. Ingestion

### 6.1 Supported inputs

**XER is the primary format and a Phase 1 requirement.** This is a change from the initial draft,
driven by inspection of the actual project exports (§6.2): the CSV and XLSX exports omit every
piece of metadata the assessment depends on, while the XER carries all of it natively.

| Format | Priority | Carries |
|---|---|---|
| **P6 XER** | **Required, Phase 1** | Data date, scheduled/planned finish, per-activity calendars, typed relationships, resource assignments, WBS tree, scheduling options. Full assessment possible. |
| P6 CSV export | Required, Phase 1 | Activities, float, typed relationships via Details columns. **No** data date, calendars, resources or baseline. Degraded assessment; missing inputs prompted or reported `NOT_ASSESSABLE`. |
| P6 XLSX export | Required, Phase 1 | As CSV. Note the two dialects below. |

**Two distinct XLSX dialects exist in real use** and both must be supported by the alias table:
a human-readable dialect (`Activity ID`, `Total Float`) and a raw P6 internal-field dialect
(`task_code`, `total_float_hr_cnt`, `pred_details`, `cstr_type`). The raw dialect reports float and
duration in **hours**, not days, and must be converted using the activity calendar's hours-per-day
before any 44-day threshold is applied. Treating an hour count as a day count is a silent 8× error.

### 6.2 What the real exports actually contain

Measured across the exports in `Schedule extract/`, this is the evidence base for the decisions
in §14:

| Input | Data date | Calendars | Resources | Baseline | Relationships |
|---|---|---|---|---|---|
| `gore extract.xer` | ✅ `last_recalc_date` = 2026-01-31 | ✅ 7 calendars | ✅ 445 of 1,952 tasks (22.8%) | ❌ single project, no baseline | ✅ 7,736 typed |
| `P6_Extract.csv` | ❌ | ❌ | ❌ no resource column | ❌ | ✅ Details columns |
| `Schedule export.csv` | ❌ | ❌ | ❌ | ❌ | ✅ Details columns |
| `*.xlsx` (raw dialect) | ❌ | ❌ | ❌ | ⚠️ `var_start_date` / `var_end_date` variance fields only | ✅ `pred_details` |

Two consequences worth stating plainly. **DCMA 10 (Resources) is not assessable from any CSV
export** — no resource or cost column exists in any of them. And the XLSX variance fields imply a
baseline exists inside P6 but is not being exported, which is what §14.2 resolves.

### 6.3 Required metadata

The current parser captures none of this, which is the root cause of the defensibility problems
in §7.1. Each is read from the XER where present, and otherwise **prompted for explicitly at
upload**. None may ever be inferred.

1. **Data date (status date).** Mandatory; upload is rejected without it. From XER
   `PROJECT.last_recalc_date`.
2. **Project must-finish / contract finish date.** Required for CPLI (DCMA 13). From XER
   `PROJECT.scd_end_date` or `plan_end_date`; note these differ (2028-04-30 vs 2028-12-22 in the
   reference project), so **which field was used must be recorded and printed**.
3. **Calendars.** Per §7.4.
4. **Baseline.** A separate baseline XER, ingested as a first-class object (§14.2).

### 6.4 Normalisation pipeline

Ordered, each step pure and independently testable:

1. Read → raw frame
2. Resolve columns via alias table → fail loudly on unresolvable required columns
3. Coerce dtypes — dates with an **explicit format list** (never bare `to_datetime`, which
   currently falls back to per-element `dateutil` parsing and costs ~150 ms), numerics with
   `errors="coerce"` and a recorded coercion-failure count
4. Parse relationships → typed `Relationship` records
5. Derive flags — `is_milestone`, `is_complete`, `has_predecessor`, `has_successor`,
   `constraint_category`
6. Decompose WBS → level columns
7. Validate → `IngestReport` with errors, warnings, and per-column coercion statistics

The `IngestReport` is persisted and surfaced in both the UI and the DOCX methodology appendix.
A schedule where 12% of `Total Float` values failed numeric coercion produces a materially
different assessment, and the reader must be told.

---

## 7. DCMA 14-Point specification

### 7.1 Defensibility: the three structural failures being corrected

**Failure 1 — the fabricated data date.** `dcma_analyzer.py:1099` reads
`schedule_data.get('data_date')`, which the parser never populates, and silently falls back to
`self.df['Start'].min()` — the earliest start date in the schedule. DCMA 9 tests forecast dates
before the data date and actual dates after it. Anchored to the earliest start, that test is not
merely inaccurate; it is structurally incapable of detecting the condition it names. **The data
date is now mandatory input.**

**Failure 2 — no baseline.** BEI compares work completed against work baselined. With no baseline
ingested, the current BEI is not a baseline execution index. It must be `NOT_ASSESSABLE` until a
baseline exists.

**Failure 3 — approximation presented as measurement.** `_calculate_cpli()` carries the comment
*"Simplified CPLI calculation. In a full implementation, this would identify the actual critical
path"* — and its output is then printed as "CPLI" beside a DCMA target. Either compute it from
declared inputs or report `NOT_ASSESSABLE`. An approximation labelled as the real metric is the
most damaging thing a compliance tool can do.

### 7.2 Assessability classes

Honest classification of what a static export can support:

- **Class A — computable from a single export** (checks 1–10 and 13), given the data date, and for
  checks 6, 8 and 13 a resolved calendar basis (§7.4)
- **Class B — requires an ingested baseline** (checks 11, 14) — resolved by §14.2
- **Class C — requires CPM recalculation** (check 12) — resolved by §14.3

Class C deserves emphasis. The **Critical Path Test** injects a large delay (conventionally 600
days) into a remaining activity and verifies the project finish moves accordingly, proving the
network is logically sound. This requires a scheduling engine to recalculate the network — it
cannot be derived from a static export by any means. The specification therefore treats DCMA 12
as **manual attestation**: the UI provides a structured input where an analyst records the test
outcome, date performed, and who performed it; the report prints it as attested, with attribution,
never as computed. Silently omitting it or fabricating a result are both unacceptable.

### 7.3 The checks

Thresholds are DCMA published defaults. All are configurable in `ruleset.py`; any deviation from
default is stamped into the analysis and **printed in the report's methodology appendix**.

| # | Check | Threshold | Denominator | Class | Notes |
|---|---|---|---|---|---|
| 1 | Logic | ≤ 5% | Incomplete activities | A | Missing predecessor and/or successor. Reported with the four-way breakdown of §2.3. |
| 2 | Leads (negative lag) | 0 | All relationships | A | `NOT_ASSESSABLE` without Details columns. |
| 3 | Lags | ≤ 5% | All relationships | A | `NOT_ASSESSABLE` without Details columns. |
| 4 | Relationship Types | FS ≥ 90% | All relationships | A | Replaces the current non-standard "SS/FF ≤10%" check. |
| 5 | Hard Constraints | ≤ 5% | Incomplete activities | A | Current code uses 10%. Corrected to the DCMA default. |
| 6 | High Float | ≤ 5% | Incomplete, non-milestone | A | TF > 44 **working** days; calendar basis per §7.4. Exclusions per §2.3. |
| 7 | Negative Float | 0 | Incomplete activities | A | TF < 0. |
| 8 | High Duration | ≤ 5% | Incomplete, non-milestone | A | Remaining duration > 44 **working** days; calendar basis per §7.4. |
| 9 | Invalid Dates | 0 | All activities | A | No forecast dates before data date; no actual dates after it. **Requires data date.** |
| 10 | Resources | 100% | Incomplete, duration > 0 | A | **XER only in practice** — no CSV/XLSX export carries resource data (§6.2), so `NOT_ASSESSABLE` on those paths. |
| 11 | Missed Tasks | ≤ 5% | Baseline tasks due by data date | B | Requires baseline. |
| 12 | Critical Path Test | Pass | — | C | Manual attestation. See §7.2. |
| 13 | CPLI | ≥ 0.95 | — | A* | `(critical path length + total float) / critical path length`, where length runs from data date to project finish. Requires data date **and** must-finish date. |
| 14 | BEI | ≥ 0.95 | Baseline tasks due by data date | B | Requires baseline. |

### 7.4 Calendar and working-day basis

The 44-day thresholds in checks 6 and 8, and the critical path length in check 13, are all
expressed in **working days**. Comparing a calendar-day duration against a working-day threshold is
a silent 5/7ths error, and the reference project shows this is not hypothetical: its activities are
spread across **seven calendars**, including 5-day, 6-day and 7-day workweeks.

Resolution order, per activity:

1. **XER ingested** — use the activity's assigned calendar (`TASK.clndr_id` → `CALENDAR`), including
   its hours-per-day and holiday exceptions. Exact.
2. **CSV/XLSX ingested** — apply a **declared project-default calendar**, selected by the analyst at
   upload and defaulting to 5×8h. The assumption is recorded on the analysis and **printed in the
   report's methodology appendix**.

The report always states which basis was used. Where the fallback applied, it says so, because the
resulting figures carry a known and quantifiable error.

For the reference project the fallback error is small but real: 98.2% of activities sit on 5-day
calendars (82.0% `GORe_5x8h_SH`, 8.4% Implenia, 7.8% Standard 5-Day), while 1.7% sit on 6-day or
7-day calendars and would be misclassified by a flat 5-day assumption. Small enough to be usable;
large enough that it must be disclosed rather than hidden.

Hour-denominated fields in the raw XLSX dialect (`total_float_hr_cnt`, `total_drtn_hr_cnt`) are
converted to days using the resolved calendar's hours-per-day, never a hardcoded 8.

---

## 8. Schedule health assessment

### 8.1 Why the current score is withdrawn

`_calculate_health_score()` starts at 100 and applies deductions that cannot be defended:

- `-10 points per negative lag, capped at -30` — an absolute count, unnormalised. A 500-activity
  schedule with 3 leads and a 6,000-activity schedule with 300 leads receive the identical penalty.
- `-5 points per missing-logic activity, capped at -25` — saturates at five activities. Every
  schedule beyond trivial size takes the full deduction, so the term carries no information.
- `+5 bonus for good CPLI` — a score that can exceed its own deduction baseline is not a scale.
- Count-based and percentage-based terms are mixed with no stated rationale, and the weights
  appear nowhere in any document.

No analyst can defend this in a schedule review, because there is nothing to defend — the numbers
have no derivation.

### 8.2 The replacement

**Primary metric — DCMA Compliance.** The headline figure is a fraction, not a score:

> **DCMA Compliance: 9 of 12 applicable checks passed** (2 failed, 1 not assessable, 2 excluded)

This is the industry-standard way the assessment is reported, requires no invented weighting,
and is directly auditable. Checks that are `NOT_ASSESSABLE` are **removed from the denominator**
and listed explicitly — never counted as passes.

**Secondary metric — Weighted Quality Index (0–100), optional and clearly subordinate.** Where a
single trendable number is needed, it is computed under published rules:

1. Each check yields a normalised sub-score in `[0, 1]`. Percentage checks use a declared linear
   ramp from threshold to a declared failure bound (e.g. DCMA 6: 0% → 1.0, 5% → 1.0, 20% → 0.0).
   Binary checks yield 0 or 1.
2. Sub-scores combine as a **weighted mean over assessable checks only**. Weights are declared in
   `ruleset.py`, printed in the report appendix, and sum to 1.0 across the full set.
3. Size-independent by construction — every input is a ratio, never a raw count.
4. Bounded `[0, 100]`. No bonuses.
5. The report prints the full arithmetic: each check's raw value, sub-score, weight, contribution.

Rules governing both metrics:

- **`NOT_ASSESSABLE` is never silently a pass.** It is a distinct, visible state everywhere.
- **Every metric declares its denominator** in the UI and the report.
- **Every result links to its evidence** — the activities that drove it.
- **Deterministic and versioned.** `ruleset_version` and `engine_version` stamp every analysis and
  every report. A report from six months ago can be reproduced exactly.
- **Bands are labels, not conclusions.** If banding is shown, the numeric value and the
  pass/fail fraction appear alongside it.

---

## 9. User interface

Streamlit is retained. The problems in the current UI are misuse, not framework limits.

### 9.1 Rerun discipline

The governing fact: **`st.tabs` renders every tab body on every rerun.** Seven tabs of charts
currently execute on each keystroke in a search box.

- Wrap each tab body in **`@st.fragment`** so a widget interaction reruns only its own fragment.
  This is now justified by measurement: after the pandas work in `f79d5a6`, the residual ~0.37 s
  interaction cost is dominated by Plotly figure construction and Streamlit serialisation, which
  fragments are the correct tool for.
- **`@st.cache_data`** on the analysis pipeline, keyed on `(sha256, ruleset_version)` — both
  hashable scalars. Never pass a DataFrame or dict as a cache key. `max_entries=8`, no TTL:
  inputs are immutable and content-addressed, so entries can never go stale.
- **`@st.cache_resource`** for the SQLAlchemy engine only. It is shared across all user sessions,
  so it must hold no per-user state — the failure the current `DatabaseManager` invites.
- Derived frames are computed once per run and passed down, never rebuilt per tab.

### 9.2 Data display

- **Server-side pagination.** Activity tables render 100 rows per page from Parquet, with filtering
  and sorting pushed into the query. A 6,345-row `st.dataframe` is never constructed.
- **No eager `to_csv`.** Exports generate inside a callback on click, not on every rerun.
- Charts are capped at a declared number of series, with the cap stated when it binds.

### 9.3 Pages

| Page | Purpose |
|---|---|
| Upload | File, project, **data date (mandatory)**, must-finish date, optional baseline. Shows `IngestReport` before analysis is offered. |
| Assessment | DCMA scorecard: 14 rows, status, value, threshold, denominator. Drill-down to evidence. |
| Detail | Per-check evidence with WBS slicing. |
| Trend | Version-over-version comparison, driven by SQL over `check_result`. |
| Report | DOCX generation and download. |
| Admin | Users, projects, ruleset configuration, audit log. |

### 9.4 Authentication

Real authentication replaces the hardcoded dictionary: `bcrypt`/`argon2` password hashing, users in
Postgres, roles (Admin / Analyst / Viewer), project-scoped access, and every mutation written to
`audit_event`. No credentials in source, ever.

---

## 10. DOCX reporting

`python-docx`. The current generator's structure is sound and its section layout is largely
retained; what changes is that the document must now be **self-justifying**.

Mandatory sections:

1. **Cover** — project, schedule version, data date, baseline identity, ruleset version,
   generation timestamp, author.
2. **Executive summary** — compliance fraction, the failed checks in severity order, and the
   assessment's stated limitations.
3. **DCMA scorecard** — one table, 14 rows: check, status, measured value, threshold, denominator.
4. **Per-check detail** — for each failure: what the check tests, what was measured, why it matters,
   the recommended corrective action, and a capped evidence table of driving activities.
5. **WBS breakdown** — compliance by WBS level 1 and 2.
6. **Methodology appendix — mandatory, non-optional.** Every threshold with its configured value;
   any deviation from DCMA defaults flagged explicitly; all exclusion rules; all denominators; the
   **calendar basis** (per-activity from XER, or the declared default, per §7.4); **which P6 finish
   field fed CPLI** (§6.3); the source format and file SHA-256; the ingest report including
   per-column coercion failures; the baseline identity where one was used; the data retention
   statement (§14.5); and the ruleset and engine versions.
7. **Limitations** — every `NOT_ASSESSABLE` check with its specific reason, and DCMA 12's
   attestation status with attributed name and date, flagged if stale relative to the data date.

Sections 6 and 7 are what make the document defensible in a review. A report that prints results
without printing the rules that produced them cannot be audited, and this is precisely the gap in
the current output.

Formatting: numbered headings, TOC field, header/footer with page numbering, landscape orientation
for wide tables, status conveyed by both colour **and** text so it survives monochrome printing.

---

## 11. Testing and validation

**Revised.** `main` now carries a real 12-file pytest suite (223 tests, all passing) with
`conftest.py`, `pytest.ini` and `requirements-dev.txt`. That suite is an asset to be **extended,
not replaced**. Two cautions when doing so:

- `tests/test_health_score.py` pins the current scoring scheme. Withdrawing it per §8 will require
  deliberately rewriting those tests, and that change should be reviewed as a behaviour change, not
  slipped through as a refactor.
- `tests/test_parser.py` on `main` is a real suite, not the broken root script of the same name
  that was removed.

Additions required on top of the existing suite:

| Layer | Requirement |
|---|---|
| Rule unit tests | Every check: pass case, fail case, boundary at threshold, and **missing-input case asserting `NOT_ASSESSABLE`**. The last is non-negotiable — it is the regression guard for the silent-default class of bug. |
| Golden-file tests | Reference schedules with hand-verified expected results, committed. Any change to a computed value must be an explicit, reviewed golden-file update. |
| Property tests | Invariants via Hypothesis: percentages in `[0,100]`; numerator ≤ denominator; compliance fraction denominators equal to assessable-check count. |
| Ingest tests | Every supported export dialect, including the `WBS` vs `WBS Code` divergence that currently causes silent degradation. |
| UI smoke tests | `streamlit.testing.v1.AppTest` — every page renders, survives a widget rerun, and keeps session state isolated across two sessions. This harness is already proven and should be carried over directly. |
| Performance regression | Asserts the budgets in §12 on a 6,345-activity fixture. |

CI gates: `ruff`, `mypy --strict` on `core/`, import-linter for the layer rule, pytest with
coverage ≥ 85% on `core/`.

---

## 12. Non-functional requirements

Budgets are set against the measured post-optimisation baseline, on the 6,345-activity reference
export. The rebuild may not regress against work already banked.

| Metric | Budget | Current measured |
|---|---|---|
| Ingest + normalise | ≤ 0.5 s | 0.27 s |
| Full DCMA assessment | ≤ 0.6 s | 0.46 s |
| Page interaction (p95) | ≤ 0.2 s | 0.37 s (fragments required) |
| DOCX generation | ≤ 2.0 s | 0.10 s |
| Session state per user | ≤ 1 MB | 3.77 MB per upload, unbounded |
| Scaling | Linear to 50,000 activities | Linear at ~0.07 ms/activity |

Concurrency: 10 simultaneous users without lock contention or cross-session leakage.

---

## 13. Repository hygiene

> **Revised.** The original plan here was to empty the application tree on a `rebuild/v2` branch.
> That plan is **withdrawn** in light of §3.1: it would delete a working SQLite backend, a sound
> PBKDF2 auth implementation, a 223-test suite and a design system. The hygiene actions below are
> safe and should proceed regardless of the §16 delivery decision.

### 13.1 Immediate, uncontroversial

1. ✅ **Done.** Remove `archive/dev_scripts/` (18 tracked files) — the old ad-hoc scripts,
   superseded by the `tests/` suite. Recoverable from history if ever needed.
2. ✅ **Already done on `main`.** `.gitignore` covers `*.db`, `.coverage`, `instance/`, `input/`,
   `Schedule extract/` and `*.xer`, with a deliberate `!data/sample_schedule.csv` exception.
   Added by the production-readiness work.
3. ✅ **Already correct.** The client schedule data and PDFs under `input/` and `Schedule extract/`
   are untracked and ignored. They must remain local-only. Note `data/Schedule export.csv` is a
   deliberate exception and is real client data — see §13.2.
4. ✅ **Already done on `main`.** `PRAGMA journal_mode = WAL` is set in `db_manager.py`.

Nothing else stale remains tracked: `instance/`, `.coverage` and `*.db` are all untracked already.

### 13.2 Client data already in git history — open issue

`data/Schedule export.csv` is a **real project schedule** — 1,261 activities, recognisable
commissioning scope — and it is committed in git history, not merely present in the working tree.
Removing it from tracking stops it propagating forward but does **not** remove it from history.

Given §14.5 treats schedules as client data warranting encryption at rest and access auditing, a
real client schedule sitting in a git history that any repository collaborator can `git log -p`
is inconsistent with that stance.

Options, in ascending cost:

| Option | Effect | Cost |
|---|---|---|
| Leave as-is, document | No change. Exposure limited to repo collaborators. | Zero |
| Untrack + gitignore | Stops forward propagation; history retains it. | Trivial |
| `git-filter-repo` purge | Fully removes it from all commits. | Rewrites every SHA; breaks clones and PR references; everyone re-clones |

**Deferred by decision on 17 August 2026** — flagged here, to be resolved separately. The repository
is private, which bounds the exposure but does not eliminate it.

### 13.3 Validation when the rule engine changes

Any change to the DCMA rules must be validated against the four reference exports, with every
divergence explained and recorded as either a corrected defect or an intentional change. Expected
divergences: DCMA 5 threshold 10% → 5%; DCMA 4 replaced by Relationship Types; DCMA 9 corrected by
a real data date; BEI and Missed Tasks becoming `NOT_ASSESSABLE` without a baseline. The
old-vs-new deep-diff harness used for the performance work is the right tool and should be kept.

Phasing, revised for the §14 decisions:

- **Phase 1** — `core/`: **XER + CSV + XLSX ingest** (both XLSX dialects), calendar resolution,
  all Class A checks, compliance scoring, full test suite. No UI.
- **Phase 2** — persistence (Postgres, migrations, retention controls per §14.5), authentication,
  Streamlit UI.
- **Phase 3** — DOCX reporting including the methodology and limitations appendices, and the
  DCMA 12 attestation form.
- **Phase 4** — baseline ingest, Class B checks (11, 14), trend analysis.
- **Future** — CPM engine, retiring the §14.3 attestation and making CPLI exact.

XER ingest is Phase 1, not Phase 4: §14.1 and §14.2 both depend on it, and without it no
assessment is fully defendable.

---

## 14. Decisions taken

All five open items were resolved on 17 August 2026 against the export evidence in §6.2. Recorded
here because each has downstream consequences the build must honour.

### 14.1 Calendars — XER calendars, declared fallback

Per-activity calendars from the XER; a declared project-default calendar for CSV/XLSX, printed as
an assumption. Specified in §7.4.

**Consequence:** XER ingest moves from Phase 2 to Phase 1.

### 14.2 Baseline — request a baseline XER export

A separate baseline XER is ingested as a first-class object (`baseline` table, §5.3), making DCMA 11
and 14 fully computable rather than approximated. The XLSX variance-field proxy was rejected: it is
a derived approximation, which is the exact pattern §7.1 exists to eliminate.

**Consequence:** a one-time change to the planning team's export procedure — baselines must be
exported alongside the current schedule. Until a project supplies one, checks 11 and 14 report
`NOT_ASSESSABLE` and leave the compliance denominator. **This is a dependency on people, not code,
and is the single most likely thing to delay full 14-point coverage.** It should be agreed with the
planning team before Phase 1 completes.

### 14.3 DCMA 12 — manual attestation

The analyst performs the 600-day critical path test in P6 and records the outcome through a
structured form: activity tested, delay applied, observed finish shift, outcome, notes, who and
when. Persisted to `attestation` (§5.3). The report prints it as **attested, with attribution and
date** — never as computed.

A CPM engine was considered and deferred. It remains the eventual correct answer, since it would
also make CPLI exact rather than input-dependent and eliminate Class C entirely; the XER's 7,736
typed relationships and full calendar set make it genuinely feasible. Recorded as a candidate for a
future phase, not v2.0.

**Consequence:** an attestation that is stale relative to the analysis must be shown as stale. The
UI flags any attestation whose `attested_at` precedes the upload's `data_date`.

### 14.4 Thresholds — DCMA published defaults

The defaults in §7.3 govern. Two deliberate corrections to current behaviour:

- **Hard constraints: 10% → 5%.** Schedules previously assessed as passing may now fail.
- **"SS/FF ≤ 10%" is removed**, replaced by the actual DCMA 4, Relationship Types (FS ≥ 90%).

Per-project overrides are permitted but are stamped into the analysis and printed in the
methodology appendix. Defaults are locked; overriding is a visible act.

**Consequence:** §13.5's old-vs-new validation must expect these divergences, and any client
holding a prior report should be told the threshold changed rather than the schedule degrading.

### 14.5 Retention — originals and results retained indefinitely

Source files, normalised Parquet, and all analysis results are retained without expiry, so any
historical report can be reproduced byte-for-byte from its source.

This is the strongest position for auditability and the weakest for data minimisation. Since the
stored corpus is client schedule data accumulating indefinitely on a shared server, the following
controls are **requirements of this decision**, not optional hardening:

- Encryption at rest for the file store and the database.
- Object-store access scoped to the application service account only; never a world-readable path
  on the shared server.
- Project-scoped authorisation on every retrieval — a user may only fetch files belonging to
  projects they can access (§9.4).
- Every download of an original file written to `audit_event`.
- A documented deletion path for a client exercising a contractual or regulatory erasure right,
  even though no automatic expiry runs.
- Retention stated in the client-facing report appendix, so the client knows their schedule is held.

**Consequence:** storage grows without bound. Budget roughly 3–4 MB per upload (original plus
Parquet) and review annually.

---

## 15. Remaining risks

1. **Baseline export procedure (§14.2)** — organisational, not technical. Full 14-point coverage
   depends on it. Agree it before Phase 1 closes.
2. **Attestation discipline (§14.3)** — DCMA 12 is only as good as the analyst's rigour. Staleness
   flagging mitigates but does not remove this.
3. **Threshold change communication (§14.4)** — prior assessments used 10% for hard constraints.
   Re-issuing a report against the same schedule may show a new failure.
4. **DCMA 10 on CSV workflows (§6.2)** — no CSV export carries resource data, so resource coverage
   is only assessable via XER. On the reference XER, only 22.8% of tasks carry assignments, which
   will likely be a genuine failure rather than a data gap. Worth confirming with the planner that
   resource loading is expected before reporting it as a finding.
5. **Indefinite retention (§14.5)** — accepted deliberately; controls above are mandatory.
6. **Client schedule in git history (§13.2)** — deferred, not resolved.
7. **`main` moves under us.** This specification was invalidated in part within hours of drafting,
   because `main` absorbed PRs #28–30 mid-flight. Re-verify §3 against `main` before acting on this
   document.

---

## 16. Open decision: delivery approach

§3.3 changes the economics of this work. The decision below is **not yet taken**.

### Option A — targeted refactor on `main`

Keep the SQLite backend, PBKDF2 auth, 223-test suite and `src/ui/` design system. Extract a pure
`core/` package, move the DCMA rules into it behind the §4.1 uniform interface, add XER ingest and
calendar handling, fix the data date, replace the scoring, and migrate the existing pages onto the
new core.

*For:* preserves working code and a passing suite; the app stays runnable throughout; delivers the
defensibility fixes — which are the actual value — soonest.
*Against:* the layered boundary must be carved out of existing code rather than built clean, and
partially-migrated states are easy to leave half-finished.

### Option B — clean rewrite per the original §13

*For:* the §4 architecture is built correctly from the start with no legacy accommodation.
*Against:* re-derives a working database layer, a sound auth implementation, and 223 tests. Leaves
no runnable application until Phase 2 completes. Materially more expensive for the same
defensibility outcome.

### Recommendation

**Option A.** Every defect in §7.1 — the fabricated data date, the absent baseline, the CPLI
approximation — lives in `core/` logic, not in the surrounding application. None of them requires
an empty repository to fix. The layered architecture is worth having, but it is a means to
testable rules, and extraction achieves that at a fraction of the cost.

If Option A is taken, §13's phasing still applies with Phase 2 reduced to *migration* rather than
*construction*.

**Decision: Option A taken, 17 August 2026.** Implementation status and sequencing in §17.

---

## 17. Implementation status and next steps

Verified against `main` @ `bd6f0af`. This section is the working plan; update it as increments land.

### 17.1 Delivered

| Item | Where | Note |
|---|---|---|
| Real database, WAL enabled | `src/database/` | Production-readiness |
| PBKDF2-SHA256 auth | `src/auth/security.py` | Production-readiness |
| Test suite | `tests/` | 253 tests passing |
| Design system | `src/ui/` | Production-readiness |
| Row-wise pandas scans removed | `dcma_analyzer` | `analyze()` 2.65 s → 0.45 s |
| **Weighted quality index (§8.2)** | `src/analysis/health_score.py` | Largely satisfies §8: 12 components, weights summing to 100, linear ramps from threshold to a zero bound, `n/a` components excluded with weights renormalised, per-component explanation. **§8's core complaint is resolved.** |
| **`core/` package started (§4)** | `src/core/ingest/` | Layer rule holds: no Streamlit, no DB imports |
| **MS Project CSV ingest (§6.1)** | `src/core/ingest/msproject.py` | 255-char truncation recovered by predecessor inversion; summary rollups excluded |

### 17.2 Outstanding, in recommended order

**Increment 2 — the data date.** The root of all three §7.1 defects and the cheapest high-value fix.
Capture it at upload (mandatory field, §6.3), persist it on the schedule, and thread it into the
analyser. Removes the `df['Start'].min()` fallback at `dcma_analyzer.py:1155`, makes DCMA 9
meaningful, and is the precondition for CPLI.

**Increment 3 — honest CPLI and BEI.** With a data date and a must-finish date, compute CPLI
properly; without them, return `NOT_ASSESSABLE`. BEI returns `NOT_ASSESSABLE` until a baseline
exists (§14.2) rather than reporting 1.000 as it does today. Requires `NOT_ASSESSABLE` to become a
first-class status in `get_dcma_14_point_summary`, alongside the `n/a` concept `health_score.py`
already has.

**Increment 4 — threshold reconciliation (§14.4).** See the defect in §17.3. Move the scorecard to
the DCMA defaults so it agrees with the scorer, and replace the non-standard "SS/FF ≤ 10%" check
with the real DCMA 4, Relationship Types FS ≥ 90%.

**Increment 5 — XER ingest (§6.1).** Largest single unlock: supplies data date, scheduled finish,
per-activity calendars and resource assignments in one step, and is the precondition for §7.4 and
for DCMA 10 being assessable at all.

**Increment 6 — calendars (§7.4).** Per-activity calendars from XER, declared fallback for CSV,
basis printed in the report. Makes the 44-day thresholds correct rather than approximately correct.

**Increment 7 — report methodology and limitations appendices (§10.6, §10.7).** The defensibility
payload. Cheap once the preceding increments supply the metadata to print.

**Increment 8 — evidence capping (§5.4).** Not yet implemented; full populations are still embedded
in the metrics dict at ~1 MB per analysis.

**Increment 9 — baseline ingest and Class B checks (§14.2).** Gated on the export-procedure change,
which is an organisational dependency — start that conversation early.

Deferred: Parquet/content-addressed storage (§5.2), Postgres migration (§5.1), CPM engine (§14.3).

### 17.3 Defect found while reviewing status

**The scorecard and the health score disagree on hard constraints.**
`health_score.py` scores DCMA 5 against a 5% target — the DCMA default, already correct — while
`get_dcma_14_point_summary` reports and evaluates it against `'≤10%'`. A schedule with 7% hard
constraints is therefore shown as **PASS** on the 14-point scorecard while simultaneously being
penalised by the health score that sits beside it on the same page.

This is a live inconsistency in the current release, not a rebuild concern, and should be fixed in
Increment 4 or sooner. Note the fix makes the scorecard stricter, so schedules previously shown as
passing this check may begin to fail it (§14.4).
