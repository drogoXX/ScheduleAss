"""Pure analysis core.

Modules under `src.core` must not import Streamlit, touch the database, or perform
any I/O beyond being handed bytes. This is what makes the ingestion and DCMA rules
unit-testable and runnable outside the app. See docs/TECHNICAL_SPECIFICATION_v2.md §4.
"""
