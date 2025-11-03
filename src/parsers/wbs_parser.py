"""
WBS (Work Breakdown Structure) Parser
Parses hierarchical WBS codes with period (.) delimiters
"""

from typing import Dict, List, Optional
import pandas as pd


class WBSParser:
    """Parse and analyze hierarchical WBS codes"""

    def __init__(self):
        """Initialize WBS parser"""
        self.max_depth = 0
        self.wbs_hierarchy = {}

    def parse_wbs_code(self, wbs_code: str) -> Dict:
        """
        Parse a single WBS code into hierarchical levels

        Args:
            wbs_code: WBS code string (e.g., "Project.Phase.Area.Detail")

        Returns:
            Dictionary with parsed levels and metadata
        """
        if pd.isna(wbs_code) or not wbs_code or str(wbs_code).strip() == '':
            return {
                'wbs_full': None,
                'wbs_depth': 0,
                'wbs_level_0': None,
                'wbs_level_1': None,
                'wbs_level_2': None,
                'wbs_level_3': None,
                'wbs_level_4': None,
                'wbs_level_5': None
            }

        # Convert to string and strip whitespace
        wbs_str = str(wbs_code).strip()

        # Split by period (.) to get hierarchical levels
        levels = wbs_str.split('.')

        # Build result dictionary
        result = {
            'wbs_full': wbs_str,
            'wbs_depth': len(levels)
        }

        # Store each level (up to 6 levels: 0-5)
        for i in range(6):
            level_key = f'wbs_level_{i}'
            if i < len(levels):
                result[level_key] = levels[i].strip()
            else:
                result[level_key] = None

        # Update max depth
        if len(levels) > self.max_depth:
            self.max_depth = len(levels)

        return result

    def parse_wbs_dataframe(self, df: pd.DataFrame, wbs_column: str = 'WBS Code') -> pd.DataFrame:
        """
        Parse WBS codes for an entire dataframe

        Args:
            df: DataFrame with WBS Code column
            wbs_column: Name of the WBS column

        Returns:
            DataFrame with added WBS level columns
        """
        if wbs_column not in df.columns:
            # No WBS column, return dataframe unchanged
            return df

        # Reset max depth
        self.max_depth = 0

        # Parse each WBS code
        parsed_wbs = df[wbs_column].apply(self.parse_wbs_code)

        # Convert list of dicts to DataFrame
        wbs_df = pd.DataFrame(parsed_wbs.tolist())

        # Add parsed columns to original dataframe
        for col in wbs_df.columns:
            df[col] = wbs_df[col]

        return df

    def get_wbs_summary(self, short_format: str) -> str:
        """
        Get a shortened WBS code for display

        Args:
            short_format: 'short' (last 3-4 levels), 'medium' (levels 1-2), 'context' (breadcrumb)

        Returns:
            Formatted WBS string
        """
        # This would be called with specific WBS code, but for now return placeholder
        return short_format

    def build_wbs_hierarchy(self, df: pd.DataFrame) -> Dict:
        """
        Build a hierarchical dictionary of WBS structure

        Args:
            df: DataFrame with parsed WBS levels

        Returns:
            Nested dictionary representing WBS tree
        """
        hierarchy = {}

        if 'wbs_level_0' not in df.columns:
            return hierarchy

        # Build tree structure
        for _, row in df.iterrows():
            current_level = hierarchy

            # Traverse through WBS levels
            for i in range(self.max_depth):
                level_key = f'wbs_level_{i}'
                if level_key not in row or pd.isna(row[level_key]):
                    break

                wbs_value = row[level_key]
                if wbs_value not in current_level:
                    current_level[wbs_value] = {
                        'children': {},
                        'activity_count': 0,
                        'level': i
                    }

                current_level[wbs_value]['activity_count'] += 1
                current_level = current_level[wbs_value]['children']

        self.wbs_hierarchy = hierarchy
        return hierarchy

    def get_wbs_breadcrumb(self, wbs_full: str) -> str:
        """
        Get WBS breadcrumb format for display

        Args:
            wbs_full: Full WBS code

        Returns:
            Breadcrumb string (e.g., "Level0 > Level1 > Level2")
        """
        if pd.isna(wbs_full) or not wbs_full:
            return "No WBS"

        levels = str(wbs_full).split('.')
        return ' > '.join(levels)

    def get_wbs_short_name(self, wbs_full: str, num_levels: int = 3) -> str:
        """
        Get shortened WBS name showing last N levels

        Args:
            wbs_full: Full WBS code
            num_levels: Number of trailing levels to show

        Returns:
            Shortened WBS string
        """
        if pd.isna(wbs_full) or not wbs_full:
            return "No WBS"

        levels = str(wbs_full).split('.')
        if len(levels) <= num_levels:
            return wbs_full

        return '.'.join(levels[-num_levels:])

    def validate_wbs_structure(self, df: pd.DataFrame) -> List[str]:
        """
        Validate WBS structure and return warnings

        Args:
            df: DataFrame with WBS Code column

        Returns:
            List of validation warning messages
        """
        warnings = []

        if 'WBS Code' not in df.columns:
            warnings.append("WBS Code column not found in schedule data")
            return warnings

        # Check for missing WBS codes
        missing_count = df['WBS Code'].isna().sum()
        if missing_count > 0:
            pct = (missing_count / len(df)) * 100
            warnings.append(f"{missing_count} activities ({pct:.1f}%) have missing WBS codes")

        # Check for inconsistent depth
        if 'wbs_depth' in df.columns:
            depths = df['wbs_depth'].value_counts()
            if len(depths) > 3:
                warnings.append(f"WBS depth varies significantly: {dict(depths.head(5))}")

        # Check for very short WBS codes (might indicate issues)
        if 'wbs_depth' in df.columns:
            shallow = (df['wbs_depth'] < 2).sum()
            if shallow > 0 and shallow < len(df):
                warnings.append(f"{shallow} activities have shallow WBS codes (depth < 2)")

        return warnings

    def get_wbs_level_summary(self, df: pd.DataFrame, level: int) -> pd.DataFrame:
        """
        Get summary statistics for a specific WBS level

        Args:
            df: DataFrame with parsed WBS data
            level: WBS level number (0, 1, 2, etc.)

        Returns:
            DataFrame with summary statistics per WBS area at that level
        """
        level_col = f'wbs_level_{level}'

        if level_col not in df.columns:
            return pd.DataFrame()

        # Group by WBS level and calculate statistics
        summary = df.groupby(level_col).agg({
            'Activity ID': 'count',  # Activity count
            'Total Float': ['mean', 'median', 'min', 'max'] if 'Total Float' in df.columns else 'count',
            'At Completion Duration': 'mean' if 'At Completion Duration' in df.columns else 'count'
        }).round(2)

        summary.columns = ['_'.join(col).strip('_') for col in summary.columns.values]
        summary = summary.reset_index()
        summary = summary.rename(columns={'Activity ID_count': 'activity_count'})

        return summary
