"""
Schedule Parser for P6 CSV exports
Parses and validates Primavera P6 schedule data
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import io


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
            # Read CSV into DataFrame
            df = pd.read_csv(io.BytesIO(file_content))

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

            # Convert to dictionary format
            schedule_data = {
                'success': True,
                'file_name': file_name,
                'upload_date': datetime.now().isoformat(),
                'total_activities': len(df),
                'activities': df.to_dict('records'),
                'metadata': self._extract_metadata(df),
                'warnings': self.warnings
            }

            return schedule_data

        except Exception as e:
            return {
                'success': False,
                'errors': [f"Failed to parse CSV file: {str(e)}"],
                'warnings': self.warnings
            }

    def _validate_columns(self, df: pd.DataFrame) -> Dict:
        """Validate that required columns are present"""
        df_columns = df.columns.tolist()
        missing_columns = []

        for req_col in self.REQUIRED_COLUMNS:
            if req_col not in df_columns:
                # Try case-insensitive match
                found = False
                for col in df_columns:
                    if col.lower() == req_col.lower():
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

    def _parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse date columns"""
        date_columns = ['Start', 'Finish']

        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

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
