"""
Schedule Parser for P6 and Microsoft Project CSV exports

Dispatches on the detected source format: P6 exports run the cleaning and
relationship-parsing pipeline below, while Microsoft Project exports are
translated to the same canonical frame by src.core.ingest.msproject.
"""

import csv

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import io
from src.config import settings
from src.core.ingest import MSProjectCsvReader, SourceFormat, detect_format
from src.logging_config import get_logger
from src.parsers.wbs_parser import WBSParser

logger = get_logger("parser")


class ScheduleParser:
    """Parses P6 schedule CSV exports"""

    # Expected column names (flexible matching)
    REQUIRED_COLUMNS = [
        'Activity ID',
        'Activity Name',
        'Activity Status',
        'Start',
        'Finish',
        'Total Float',
        'Duration Type'
    ]

    OPTIONAL_COLUMNS = [
        'WBS Code',
        'At Completion Duration',
        'Free Float',
        'Predecessors',
        'Predecessor Details',
        'Successors',
        'Successor Details',
        'Primary Constraint',
        'Activity Type',
        'Resource Names'
    ]

    def __init__(self):
        """Initialize the parser"""
        self.errors = []
        self.warnings = []
        self.wbs_parser = WBSParser()

    def parse_csv(self, file_content: bytes, file_name: str) -> Dict:
        """
        Parse CSV file and return structured schedule data

        Args:
            file_content: Raw file bytes
            file_name: Name of the uploaded file

        Returns:
            Dictionary containing parsed schedule data and metadata
        """
        self.errors = []
        self.warnings = []

        try:
            source_format = detect_format(file_content, file_name)

            if source_format is SourceFormat.MSPROJECT_CSV:
                # The MS Project reader emits a canonical frame with relationships
                # and dates already parsed, so the P6 cleaning path is skipped -
                # _clean_data() stringifies object columns and would destroy the
                # predecessor_list / successor_list structures.
                df = self._read_msproject(file_content)
                if df is None:
                    return {
                        'success': False,
                        'errors': self.errors,
                        'warnings': self.warnings,
                    }
            else:
                df = self._read_csv(file_content)

                if df is None:
                    return {
                        'success': False,
                        'errors': self.errors,
                        'warnings': self.warnings,
                    }

                # Validate columns
                validation_result = self._validate_columns(df)
                if not validation_result['valid']:
                    return {
                        'success': False,
                        'errors': validation_result['errors'],
                        'warnings': validation_result['warnings']
                    }

                # Clean and standardize data
                df = self._clean_data(df)

                # Parse relationships
                df = self._parse_relationships(df)

                # Parse dates
                df = self._parse_dates(df)

            # Calculate derived fields
            df = self._calculate_derived_fields(df)

            # Parse WBS structure (if WBS Code column exists)
            df = self._parse_wbs_structure(df)

            # Convert to dictionary format
            schedule_data = {
                'success': True,
                'file_name': file_name,
                'source_format': source_format.value,
                'upload_date': datetime.now().isoformat(),
                'total_activities': len(df),
                'activities': df.to_dict('records'),
                'metadata': self._extract_metadata(df),
                'warnings': self.warnings
            }

            return schedule_data

        except Exception as e:
            logger.exception("Unhandled error parsing %r", file_name)
            return {
                'success': False,
                'errors': [f"Failed to parse CSV file: {str(e)}"],
                'warnings': self.warnings
            }

    def _read_msproject(self, file_content: bytes) -> Optional[pd.DataFrame]:
        """Read a Microsoft Project CSV export into the canonical frame.

        Returns None and populates self.errors if the export cannot be translated.
        """
        translation = MSProjectCsvReader().read(file_content)

        for warning in translation.warnings:
            if warning not in self.warnings:
                self.warnings.append(warning)

        if not translation.ok:
            self.errors.extend(translation.errors)
            return None

        logger.info(
            "MS Project export translated: %d activities, %d summary rows, "
            "%d truncated cells, %d edges recovered by inversion",
            len(translation.frame), translation.summary_task_count,
            translation.truncated_cells, translation.recovered_edges,
        )
        return translation.frame

    # Encodings tried in order. P6 on Windows commonly exports cp1252, and
    # Excel round-trips often add a UTF-8 BOM.
    _ENCODINGS = ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1')

    def _read_csv(self, file_content: bytes) -> Optional[pd.DataFrame]:
        """
        Read raw bytes into a DataFrame, enforcing size limits and tolerating
        the encodings P6 actually produces.

        Returns None and populates self.errors when the input is unusable.
        """
        if not file_content:
            self.errors.append("The uploaded file is empty.")
            return None

        size = len(file_content)
        if size > settings.max_upload_bytes:
            self.errors.append(
                f"File is {size / 1024 / 1024:.1f} MB, which exceeds the "
                f"{settings.MAX_UPLOAD_MB} MB limit."
            )
            return None

        text: Optional[str] = None
        last_error: Optional[Exception] = None
        for encoding in self._ENCODINGS:
            try:
                text = file_content.decode(encoding)
                if encoding != self._ENCODINGS[0]:
                    self.warnings.append(f"File was read using '{encoding}' encoding.")
                break
            except UnicodeDecodeError as exc:
                last_error = exc
                continue

        if text is None:
            self.errors.append(
                f"Could not decode the file as text (tried "
                f"{', '.join(self._ENCODINGS)}). Re-export it as UTF-8 CSV. "
                f"Details: {last_error}"
            )
            return None

        # Duplicate headers must be caught on the raw header line: pandas
        # silently renames the second occurrence (e.g. 'Total Float.1'), so by
        # the time we have a DataFrame the collision is no longer visible and
        # one of the two columns would be ignored without explanation.
        duplicates = self._duplicate_headers(text)
        if duplicates:
            self.errors.append(
                f"The file has duplicate column headers: {', '.join(duplicates)}. "
                f"Re-export with unique column names."
            )
            return None

        try:
            df = pd.read_csv(io.StringIO(text))
        except pd.errors.EmptyDataError:
            self.errors.append("The uploaded file contains no data.")
            return None
        except pd.errors.ParserError as exc:
            self.errors.append(
                f"The file is not valid CSV and could not be read: {exc}"
            )
            return None

        if df.empty:
            self.errors.append("The file contains column headers but no activity rows.")
            return None

        if len(df) > settings.MAX_ACTIVITIES:
            self.errors.append(
                f"The schedule has {len(df):,} activities, which exceeds the "
                f"supported maximum of {settings.MAX_ACTIVITIES:,}."
            )
            return None

        # Drop unnamed padding columns that trailing commas in P6 exports create.
        unnamed = [c for c in df.columns if str(c).startswith("Unnamed:")]
        if unnamed:
            df = df.drop(columns=unnamed)

        return df

    @staticmethod
    def _duplicate_headers(text: str) -> List[str]:
        """Return any column names that appear more than once in the header row."""
        lines = text.splitlines()
        if not lines:
            return []

        try:
            header = next(csv.reader([lines[0]]))
        except (StopIteration, csv.Error):
            return []

        seen: Dict[str, int] = {}
        for name in (h.strip() for h in header):
            if name:
                seen[name] = seen.get(name, 0) + 1
        return sorted(name for name, count in seen.items() if count > 1)

    def _validate_columns(self, df: pd.DataFrame) -> Dict:
        """Validate that required columns are present"""
        df_columns = df.columns.tolist()
        missing_columns = []

        # Helper function to normalize column name for matching
        def normalize_for_matching(col_name):
            """Normalize column name by removing P6 unit suffixes"""
            normalized = col_name.strip()
            # Remove P6 suffixes: (d), (h), (%), etc.
            normalized = re.sub(r'\s*\([dhwmy%]+\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(days?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(hours?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(weeks?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(months?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(years?\)\s*$', '', normalized, flags=re.IGNORECASE)
            return normalized.strip()

        for req_col in self.REQUIRED_COLUMNS:
            if req_col not in df_columns:
                # Try case-insensitive match and normalized match (without P6 suffixes)
                found = False
                for col in df_columns:
                    # Exact case-insensitive match
                    if col.lower() == req_col.lower():
                        found = True
                        break
                    # Normalized match (e.g., "Total Float(d)" matches "Total Float")
                    if normalize_for_matching(col).lower() == req_col.lower():
                        found = True
                        break
                if not found:
                    missing_columns.append(req_col)

        if missing_columns:
            return {
                'valid': False,
                'errors': [f"Missing required columns: {', '.join(missing_columns)}"],
                'warnings': []
            }

        return {'valid': True, 'errors': [], 'warnings': []}

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize data"""
        # Strip whitespace from column names
        df.columns = df.columns.str.strip()

        # Normalize P6 column names by removing unit suffixes
        # P6 often adds suffixes like "(d)" for days, "(h)" for hours, "(%)" for percentages
        # Example: "At Completion Duration(d)" → "At Completion Duration"
        normalized_columns = {}
        for col in df.columns:
            # Remove common P6 suffixes while preserving the column name
            normalized = col
            # Remove suffixes: (d), (h), (%), (wk), (mo), (yr)
            import re
            normalized = re.sub(r'\s*\([dhwmy%]+\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(days?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(hours?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(weeks?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(months?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized = re.sub(r'\s*\(years?\)\s*$', '', normalized, flags=re.IGNORECASE)
            normalized_columns[col] = normalized.strip()

        # Rename columns with normalized names
        df = df.rename(columns=normalized_columns)

        # Log if any columns were renamed
        renamed = [(old, new) for old, new in normalized_columns.items() if old != new]
        if renamed:
            for old_name, new_name in renamed:
                self.warnings.append(f"Normalized column name: '{old_name}' → '{new_name}'")

        # Strip whitespace from string columns
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()

        # Replace 'nan' strings with actual NaN
        df = df.replace('nan', np.nan)
        df = df.replace('None', np.nan)
        df = df.replace('', np.nan)

        # Ensure numeric columns
        numeric_columns = ['Total Float', 'Free Float', 'At Completion Duration']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    # Matches the leading numeric day/month pair of a slash/dash/dot date.
    _NUMERIC_DATE_RE = re.compile(r'^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})')
    # Year-first (ISO 8601) dates, which are never day/month ambiguous.
    _ISO_DATE_RE = re.compile(r'^\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}')

    DATE_COLUMNS = ['Start', 'Finish']

    def _has_iso_dates(self, df: pd.DataFrame) -> bool:
        """
        True when dates are year-first (e.g. 2025-04-03) and no ambiguous
        numeric dates are present.

        This must be checked before applying any day-first preference: pandas
        honours ``dayfirst`` for year-first strings too, so parsing an ISO date
        with dayfirst=True reads 2025-04-03 as 4 March.
        """
        iso_seen = False
        for col in self.DATE_COLUMNS:
            if col not in df.columns:
                continue
            for value in df[col].dropna().astype(str):
                if self._NUMERIC_DATE_RE.match(value):
                    return False
                if self._ISO_DATE_RE.match(value):
                    iso_seen = True
        return iso_seen

    def _detect_date_order(self, df: pd.DataFrame) -> str:
        """
        Determine whether numeric dates are day-first (dd/mm/yyyy) or
        month-first (mm/dd/yyyy).

        P6 exports the host machine's locale format with no indication of which
        it used. Left to itself, pandas infers the format from the first
        non-null value only: if that value happens to be ambiguous (e.g.
        03/04/2025) it locks in month-first for the whole column, silently
        shifting dates by months and turning genuine day-first values such as
        29/08/2025 into NaT.

        Detection uses every date in the file: a first component above 12 can
        only be a day, a second component above 12 can only be a month.

        Returns 'day', 'month', 'conflict' (both seen - data is inconsistent),
        or 'ambiguous' (no value is decisive).
        """
        first_over_12 = 0
        second_over_12 = 0

        for col in self.DATE_COLUMNS:
            if col not in df.columns:
                continue
            for value in df[col].dropna().astype(str):
                match = self._NUMERIC_DATE_RE.match(value)
                if not match:
                    continue
                first, second = int(match.group(1)), int(match.group(2))
                if first > 12:
                    first_over_12 += 1
                if second > 12:
                    second_over_12 += 1

        if first_over_12 and second_over_12:
            return 'conflict'
        if first_over_12:
            return 'day'
        if second_over_12:
            return 'month'
        return 'ambiguous'

    def _parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parse date columns using a single, explicitly determined day/month
        order for the whole file, and report values that could not be parsed.
        """
        # Year-first dates are unambiguous, and applying a day/month preference
        # to them actively corrupts the result, so they short-circuit both
        # detection and configuration.
        if self._has_iso_dates(df):
            return self._apply_date_parsing(df, dayfirst=False)

        configured = settings.DATE_ORDER
        if configured in ('day', 'dayfirst', 'dmy'):
            order, source = 'day', 'configuration'
        elif configured in ('month', 'monthfirst', 'mdy'):
            order, source = 'month', 'configuration'
        else:
            order, source = self._detect_date_order(df), 'detection'

        if order == 'conflict':
            self.warnings.append(
                "Dates are inconsistent: the file contains both day-first "
                "(e.g. 29/08/2025) and month-first (e.g. 08/29/2025) values. "
                "Parsing as day-first; verify the schedule dates in the results, "
                "or re-export with an unambiguous date format (YYYY-MM-DD)."
            )
            dayfirst = True
        elif order == 'ambiguous':
            # No value in the file distinguishes the two orders. Any choice is a
            # guess, so state it rather than let it pass silently.
            self.warnings.append(
                "Date format is ambiguous: every date in this file could be read "
                "as either day-first or month-first. Assuming day-first "
                "(dd/mm/yyyy). Set APP_DATE_ORDER=month if this schedule was "
                "exported with US-style dates."
            )
            dayfirst = True
        else:
            dayfirst = (order == 'day')
            if source == 'detection':
                self.warnings.append(
                    f"Detected {'day-first (dd/mm/yyyy)' if dayfirst else 'month-first (mm/dd/yyyy)'} "
                    f"date format."
                )

        return self._apply_date_parsing(df, dayfirst=dayfirst)

    def _apply_date_parsing(self, df: pd.DataFrame, *, dayfirst: bool) -> pd.DataFrame:
        """Convert the date columns using a fixed order, reporting bad values."""
        for col in self.DATE_COLUMNS:
            if col not in df.columns:
                continue

            original = df[col]
            parsed = pd.to_datetime(original, errors='coerce', dayfirst=dayfirst)

            # Values that were present but could not be interpreted are data
            # quality problems the user needs to know about - previously they
            # became NaT with no indication.
            unparsed = original.notna() & parsed.isna()
            unparsed_count = int(unparsed.sum())
            if unparsed_count:
                examples = original[unparsed].astype(str).unique()[:3]
                self.warnings.append(
                    f"{unparsed_count} value(s) in '{col}' could not be read as a "
                    f"date and were left empty (e.g. {', '.join(examples)})."
                )

            df[col] = parsed

        return df

    def _parse_relationships(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse predecessor and successor relationships"""

        # Parse Predecessors - prioritize "Predecessor Details" which has full relationship notation
        if 'Predecessor Details' in df.columns:
            df['predecessor_list'] = df['Predecessor Details'].apply(
                lambda x: self._parse_relationship_string(x, expect_full_format=True) if pd.notna(x) else []
            )
        elif 'Predecessors' in df.columns:
            # Fallback to simple Predecessors column (Activity IDs only, default to FS with 0 lag)
            df['predecessor_list'] = df['Predecessors'].apply(
                lambda x: self._parse_relationship_string(x, expect_full_format=False) if pd.notna(x) else []
            )
            self.warnings.append("⚠️  Using 'Predecessors' column (Activity IDs only, no relationship types or lags). Relationship metrics may not be accurate. Recommend using 'Predecessor Details' column for full relationship information (format: 'ActivityID: Type Lag', e.g., 'A100: FF 10').")
        else:
            df['predecessor_list'] = [[] for _ in range(len(df))]
            self.warnings.append("⚠️  CRITICAL: No 'Predecessor Details' or 'Predecessors' column found. Logic Quality Metrics and Relationship Types will show NO DATA. Please ensure your P6 export includes predecessor relationship information.")

        # Parse Successors - prioritize "Successor Details" which has full relationship notation
        if 'Successor Details' in df.columns:
            df['successor_list'] = df['Successor Details'].apply(
                lambda x: self._parse_relationship_string(x, expect_full_format=True) if pd.notna(x) else []
            )
        elif 'Successors' in df.columns:
            # Fallback to simple Successors column (Activity IDs only, default to FS with 0 lag)
            df['successor_list'] = df['Successors'].apply(
                lambda x: self._parse_relationship_string(x, expect_full_format=False) if pd.notna(x) else []
            )
            self.warnings.append("⚠️  Using 'Successors' column (Activity IDs only, no relationship types or lags). Recommend using 'Successor Details' column for full relationship information.")
        else:
            df['successor_list'] = [[] for _ in range(len(df))]
            self.warnings.append("⚠️  No 'Successor Details' or 'Successors' column found. Successor data will not be available.")

        return df

    def _parse_relationship_string(self, rel_string: str, expect_full_format: bool = True) -> List[Dict]:
        """
        Parse relationship string into structured format

        Args:
            rel_string: The relationship string to parse
            expect_full_format: If True, expects "ActivityID: Type Lag" format (from Detail columns)
                              If False, accepts "ActivityID" only (from simple columns)

        Examples:
            Full format: 'A21740: FF 10, A21750: FS, A21760: FS -5'
            Simple format: 'A21740, A21750, A21760'

        Returns:
            List of relationship dictionaries with 'activity', 'type', and 'lag' keys
        """
        relationships = []

        if not rel_string or pd.isna(rel_string) or str(rel_string).lower() == 'nan':
            return relationships

        # Split by comma for multiple relationships
        parts = str(rel_string).split(',')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Try to match full format: ActivityID: Type Lag
            # Examples: "A21740: FF 10", "A21750: FS", "A21760: FS -5"
            # Pattern explanation:
            # - ([A-Za-z0-9_-]+): Activity ID (letters, numbers, underscores, hyphens)
            # - \s*:\s*: Colon with optional whitespace
            # - ([A-Z]{2}): Relationship type (exactly 2 uppercase letters: FS, FF, SS, SF)
            # - \s*([-]?\d+)?: Optional lag (negative or positive integer)
            match = re.match(r'([A-Za-z0-9_-]+)\s*:\s*([A-Z]{2})\s*([-]?\d+)?', part)

            if match:
                activity_id = match.group(1)
                rel_type = match.group(2)
                lag = int(match.group(3)) if match.group(3) else 0

                relationships.append({
                    'activity': activity_id,
                    'type': rel_type,
                    'lag': lag
                })
            elif not expect_full_format:
                # Fallback for simple format (Activity ID only)
                # Only use this for simple "Predecessors"/"Successors" columns
                simple_match = re.match(r'([A-Za-z0-9_-]+)', part)
                if simple_match:
                    relationships.append({
                        'activity': simple_match.group(1),
                        'type': 'FS',  # Default to Finish-to-Start
                        'lag': 0
                    })
            else:
                # If we expect full format but didn't match, log a warning
                self.warnings.append(f"Could not parse relationship: '{part}'. Expected format: 'ActivityID: Type Lag'")

        return relationships

    def _calculate_derived_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate derived fields"""

        # Calculate duration from dates if not provided
        if 'Start' in df.columns and 'Finish' in df.columns:
            df['calculated_duration'] = (df['Finish'] - df['Start']).dt.days

        # Determine if activity has missing logic
        df['missing_predecessor'] = df['predecessor_list'].apply(lambda x: len(x) == 0)
        df['missing_successor'] = df['successor_list'].apply(lambda x: len(x) == 0)
        df['missing_logic'] = df['missing_predecessor'] | df['missing_successor']

        # Count negative and positive lags
        df['negative_lag_count'] = df['predecessor_list'].apply(
            lambda x: sum(1 for rel in x if rel.get('lag', 0) < 0)
        )
        df['positive_lag_count'] = df['predecessor_list'].apply(
            lambda x: sum(1 for rel in x if rel.get('lag', 0) > 0)
        )

        # Check for hard constraints
        if 'Primary Constraint' in df.columns:
            hard_constraints = ['Must Start On', 'Must Finish On', 'Start On', 'Finish On',
                               'Mandatory Start', 'Mandatory Finish']
            df['has_hard_constraint'] = df['Primary Constraint'].apply(
                lambda x: str(x) in hard_constraints if pd.notna(x) else False
            )

            # Categorize ALL constraint types
            def categorize_constraint(constraint):
                """Categorize constraint into Hard, Flexible, or Schedule-Driven"""
                if pd.isna(constraint):
                    return 'None'

                constraint_str = str(constraint).strip()

                # Hard constraints - specific date required
                hard = ['Must Start On', 'Must Finish On', 'Start On', 'Finish On',
                       'Mandatory Start', 'Mandatory Finish']
                if constraint_str in hard:
                    return 'Hard'

                # Flexible constraints - date boundaries
                flexible = ['Start On or After', 'Start On or Before',
                           'Finish On or After', 'Finish On or Before']
                if constraint_str in flexible:
                    return 'Flexible'

                # Schedule-driven - ALAP, ASAP
                schedule_driven = ['As Late As Possible', 'As Soon As Possible']
                if constraint_str in schedule_driven:
                    return 'Schedule-Driven'

                # Other/Unknown
                return 'Other'

            df['constraint_category'] = df['Primary Constraint'].apply(categorize_constraint)

            # Flag activities with ANY constraint (excluding None)
            df['has_any_constraint'] = df['constraint_category'] != 'None'
        else:
            df['has_hard_constraint'] = False
            df['constraint_category'] = 'None'
            df['has_any_constraint'] = False

        # Identify long duration activities (>20 days)
        if 'At Completion Duration' in df.columns:
            df['is_long_duration'] = df['At Completion Duration'] > 20
        elif 'calculated_duration' in df.columns:
            df['is_long_duration'] = df['calculated_duration'] > 20
        else:
            df['is_long_duration'] = False

        return df

    def _parse_wbs_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parse WBS Code hierarchy into separate level columns

        Args:
            df: DataFrame with WBS Code column

        Returns:
            DataFrame with added WBS level columns
        """
        if 'WBS Code' not in df.columns:
            # No WBS column, add empty columns for consistency
            df['wbs_full'] = None
            df['wbs_depth'] = 0
            for i in range(6):
                df[f'wbs_level_{i}'] = None
            self.warnings.append("WBS Code column not found - WBS analysis will not be available")
            return df

        # Use WBS parser to parse all codes
        df = self.wbs_parser.parse_wbs_dataframe(df, 'WBS Code')

        # Get validation warnings
        wbs_warnings = self.wbs_parser.validate_wbs_structure(df)
        for warning in wbs_warnings:
            if warning not in self.warnings:
                self.warnings.append(warning)

        # NOTE: build_wbs_hierarchy() is deliberately NOT called here. It only sets
        # wbs_parser.wbs_hierarchy, which nothing reads, and this ScheduleParser is
        # discarded once parse_csv() returns - so the result was unreachable. The call
        # cost ~0.36s per upload on a 6,300-activity schedule (it scans via iterrows).
        # Call it explicitly from the caller if the hierarchy is ever actually needed.

        return df

    def _extract_metadata(self, df: pd.DataFrame) -> Dict:
        """Extract metadata about the schedule"""
        metadata = {
            'total_activities': len(df),
            'activity_statuses': df['Activity Status'].value_counts().to_dict() if 'Activity Status' in df.columns else {},
            'date_range': {
                'start': df['Start'].min().isoformat() if 'Start' in df.columns and not df['Start'].isna().all() else None,
                'finish': df['Finish'].max().isoformat() if 'Finish' in df.columns and not df['Finish'].isna().all() else None
            },
            'has_wbs': 'WBS Code' in df.columns,
            'has_resources': 'Resource Names' in df.columns,
            'activities_with_missing_logic': int(df['missing_logic'].sum()) if 'missing_logic' in df.columns else 0,
            'activities_with_hard_constraints': int(df['has_hard_constraint'].sum()) if 'has_hard_constraint' in df.columns else 0
        }

        return metadata

    def validate_schedule_data(self, schedule_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate parsed schedule data
        Returns (is_valid, list_of_errors)
        """
        errors = []

        if not schedule_data.get('success', False):
            return False, schedule_data.get('errors', ['Unknown parsing error'])

        if schedule_data.get('total_activities', 0) == 0:
            errors.append("Schedule contains no activities")

        if not schedule_data.get('activities'):
            errors.append("No activity data found")

        return len(errors) == 0, errors
