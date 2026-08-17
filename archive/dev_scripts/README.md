# Archived development scripts

These are the ad-hoc, print-based scripts that were used to investigate parser
and analysis behaviour during initial development. They lived in the repository
root, where they were mistaken for a test suite: they contain almost no
assertions, are not collected by pytest, and several depend on files or
application state that no longer exist.

They are kept here for reference only. **They are not part of the test suite and
are not run by CI.**

The behaviour they explored is now covered by real, asserting tests in
[`tests/`](../../tests):

| Archived script | Covered by |
| --- | --- |
| `test_parser.py`, `test_complex_parsing.py`, `test_regex.py`, `test_csv_column_names.py` | `tests/test_parser.py` |
| `test_duration_*.py`, `test_negative_durations.py` | `tests/test_parser.py`, `tests/test_analysis.py` |
| `test_constraints.py` | `tests/test_parser.py::TestConstraints` |
| `test_float_analysis.py`, `test_missing_logic_breakdown.py` | `tests/test_analysis.py` |
| `test_wbs_*.py` | `tests/test_parser.py`, `tests/test_analysis.py` |
| `test_session_state_simulation.py` | `tests/test_database.py`, `tests/test_integration.py` |
| `debug_data_flow.py`, `verify_csv.py` | `tests/test_integration.py` |

Run the real suite with:

```bash
python -m pytest
```
