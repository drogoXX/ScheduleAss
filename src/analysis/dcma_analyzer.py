"""
DCMA 14-Point Schedule Assessment Analyzer
Implements industry-standard schedule quality metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime


class DCMAAnalyzer:
    """
    Analyzes schedules based on DCMA 14-Point Assessment
    and GAO Schedule Assessment Guide best practices
    """

    def __init__(self, schedule_data: Dict):
        """
        Initialize analyzer with schedule data

        Args:
            schedule_data: Parsed schedule data from ScheduleParser
        """
        self.schedule_data = schedule_data
        self.df = pd.DataFrame(schedule_data['activities'])
        self.metrics = {}
        self.issues = []
        self.warnings = []

    def analyze(self) -> Dict:
        """
        Run complete DCMA analysis
        Returns comprehensive metrics dictionary
        """
        # Logic and Network Integrity
        self._analyze_negative_lags()
        self._analyze_positive_lags()
        self._analyze_hard_constraints()
        self._analyze_missing_logic()
        self._analyze_open_ends()

        # Duration Analysis
        self._analyze_long_durations()
        self._analyze_average_duration()

        # Float Analysis
        self._analyze_high_float()
        self._analyze_float_ratio()
        self._analyze_comprehensive_float()  # NEW - Comprehensive float analysis with all KPIs

        # Activity Distribution
        self._analyze_activity_distribution()

        # Resource Analysis
        self._analyze_resource_assignment()

        # Milestone Validation
        self._analyze_milestones()

        # Activity Types
        self._analyze_activity_types()

        # Relationship Types
        self._analyze_relationship_types()

        # Status Analysis
        self._analyze_activity_status()

        return {
            'metrics': self.metrics,
            'issues': self.issues
        }

    def _analyze_negative_lags(self):
        """Analyze negative lags (leads)"""
        negative_lags = []

        for idx, row in self.df.iterrows():
            predecessors = row.get('predecessor_list', [])
            for pred in predecessors:
                if pred.get('lag', 0) < 0:
                    negative_lags.append({
                        'activity_id': row['Activity ID'],
                        'activity_name': row['Activity Name'],
                        'predecessor': pred['activity'],
                        'relationship_type': pred['type'],
                        'lag': pred['lag']
                    })

        self.metrics['negative_lags'] = {
            'count': len(negative_lags),
            'activities': negative_lags,
            'target': 0,
            'status': 'pass' if len(negative_lags) == 0 else 'fail'
        }

        if len(negative_lags) > 0:
            self.issues.append({
                'category': 'Logic Quality',
                'severity': 'high',
                'title': f'Negative Lags Detected: {len(negative_lags)}',
                'description': 'Negative lags (leads) indicate activities starting before predecessors finish, which may indicate schedule compression or logic errors.',
                'count': len(negative_lags),
                'recommendation': 'Review and eliminate negative lags. Consider using appropriate relationship types (FS, FF, SS, SF) instead of leads.',
                'affected_activities': [nl['activity_id'] for nl in negative_lags]
            })

    def _analyze_positive_lags(self):
        """Analyze positive lags"""
        positive_lags = []
        total_relationships = 0

        for idx, row in self.df.iterrows():
            predecessors = row.get('predecessor_list', [])
            total_relationships += len(predecessors)

            for pred in predecessors:
                if pred.get('lag', 0) > 0:
                    positive_lags.append({
                        'activity_id': row['Activity ID'],
                        'activity_name': row['Activity Name'],
                        'predecessor': pred['activity'],
                        'relationship_type': pred['type'],
                        'lag': pred['lag']
                    })

        percentage = (len(positive_lags) / total_relationships * 100) if total_relationships > 0 else 0

        self.metrics['positive_lags'] = {
            'count': len(positive_lags),
            'total_relationships': total_relationships,
            'percentage': round(percentage, 2),
            'activities': positive_lags,
            'target': 5.0,
            'status': 'pass' if percentage <= 5.0 else 'warning'
        }

        if percentage > 5.0:
            self.issues.append({
                'category': 'Logic Quality',
                'severity': 'medium',
                'title': f'Excessive Positive Lags: {percentage:.1f}%',
                'description': f'Found {len(positive_lags)} positive lags ({percentage:.1f}% of relationships). Target is ≤5%.',
                'count': len(positive_lags),
                'recommendation': 'Review positive lags to ensure they represent actual waiting time. Consider creating separate activities for waiting periods.',
                'affected_activities': [pl['activity_id'] for pl in positive_lags]
            })

    def _analyze_hard_constraints(self):
        """Analyze constraints - ALL types including ALAP"""
        total_activities = len(self.df)

        # Initialize constraint tracking
        constraints_by_category = {
            'Hard': [],
            'Flexible': [],
            'Schedule-Driven': [],
            'Other': []
        }
        all_constrained_activities = []

        if 'constraint_category' in self.df.columns:
            # Get all activities with ANY constraint (not 'None')
            constrained = self.df[self.df['has_any_constraint'] == True]

            for idx, row in constrained.iterrows():
                constraint_info = {
                    'activity_id': row['Activity ID'],
                    'activity_name': row['Activity Name'],
                    'constraint_type': row.get('Primary Constraint', 'Unknown'),
                    'category': row.get('constraint_category', 'Unknown')
                }

                all_constrained_activities.append(constraint_info)

                # Categorize by type
                category = row.get('constraint_category', 'Other')
                if category in constraints_by_category:
                    constraints_by_category[category].append(constraint_info)

        # Calculate percentages
        total_constrained = len(all_constrained_activities)
        total_percentage = (total_constrained / total_activities * 100) if total_activities > 0 else 0

        hard_count = len(constraints_by_category['Hard'])
        hard_percentage = (hard_count / total_activities * 100) if total_activities > 0 else 0

        flexible_count = len(constraints_by_category['Flexible'])
        flexible_percentage = (flexible_count / total_activities * 100) if total_activities > 0 else 0

        schedule_driven_count = len(constraints_by_category['Schedule-Driven'])
        schedule_driven_percentage = (schedule_driven_count / total_activities * 100) if total_activities > 0 else 0

        # Store comprehensive metrics
        self.metrics['constraints'] = {
            'total_count': total_constrained,
            'total_percentage': round(total_percentage, 2),
            'by_category': {
                'Hard': {
                    'count': hard_count,
                    'percentage': round(hard_percentage, 2),
                    'activities': constraints_by_category['Hard']
                },
                'Flexible': {
                    'count': flexible_count,
                    'percentage': round(flexible_percentage, 2),
                    'activities': constraints_by_category['Flexible']
                },
                'Schedule-Driven': {
                    'count': schedule_driven_count,
                    'percentage': round(schedule_driven_percentage, 2),
                    'activities': constraints_by_category['Schedule-Driven']
                },
                'Other': {
                    'count': len(constraints_by_category['Other']),
                    'percentage': round((len(constraints_by_category['Other']) / total_activities * 100), 2) if total_activities > 0 else 0,
                    'activities': constraints_by_category['Other']
                }
            },
            'all_activities': all_constrained_activities,
            'total_activities': total_activities,
            'guidance': 'Constraints should be minimized and duly justified',
            'status': 'warning' if total_percentage > 20 else 'pass'
        }

        # Keep legacy hard_constraints metric for compatibility
        self.metrics['hard_constraints'] = {
            'count': hard_count,
            'total_activities': total_activities,
            'percentage': round(hard_percentage, 2),
            'activities': constraints_by_category['Hard'],
            'target': 10.0,
            'status': 'pass' if hard_percentage <= 10.0 else 'fail'
        }

        # Create issues for excessive constraints
        # Hard constraints should be minimal
        if hard_percentage > 10.0:
            self.issues.append({
                'category': 'Schedule Flexibility',
                'severity': 'high',
                'title': f'Excessive Hard Constraints: {hard_percentage:.1f}%',
                'description': f'Found {hard_count} hard date constraints ({hard_percentage:.1f}% of activities). Hard constraints (Must/On dates) significantly reduce schedule flexibility and should be minimized.',
                'count': hard_count,
                'recommendation': 'Review and remove unnecessary hard date constraints. Use logic-driven scheduling instead. Each constraint should be duly justified by contractual or regulatory requirements.',
                'affected_activities': [c['activity_id'] for c in constraints_by_category['Hard']]
            })

        # Flexible constraints warning
        if flexible_percentage > 15.0:
            self.issues.append({
                'category': 'Schedule Flexibility',
                'severity': 'medium',
                'title': f'High Flexible Constraints: {flexible_percentage:.1f}%',
                'description': f'Found {flexible_count} flexible date constraints ({flexible_percentage:.1f}% of activities). These "On or Before/After" constraints limit scheduling flexibility.',
                'count': flexible_count,
                'recommendation': 'Review flexible constraints and remove those that are not duly justified. Consider using logic relationships instead.',
                'affected_activities': [c['activity_id'] for c in constraints_by_category['Flexible']]
            })

        # Schedule-driven informational (if very high)
        if schedule_driven_percentage > 50.0:
            self.issues.append({
                'category': 'Schedule Setup',
                'severity': 'low',
                'title': f'High Schedule-Driven Constraints: {schedule_driven_percentage:.1f}%',
                'description': f'Found {schedule_driven_count} schedule-driven constraints ({schedule_driven_percentage:.1f}% of activities). While ALAP/ASAP are not date constraints, high usage may indicate over-reliance on these settings.',
                'count': schedule_driven_count,
                'recommendation': 'Review schedule-driven constraints. Consider if activities should be unconstrained to allow more schedule flexibility.',
                'affected_activities': [c['activity_id'] for c in constraints_by_category['Schedule-Driven']]
            })

    def _analyze_missing_logic(self):
        """Analyze activities with missing predecessors or successors"""
        missing_logic = []

        if 'missing_logic' in self.df.columns:
            missing = self.df[self.df['missing_logic'] == True]

            for idx, row in missing.iterrows():
                missing_logic.append({
                    'activity_id': row['Activity ID'],
                    'activity_name': row['Activity Name'],
                    'missing_predecessor': row.get('missing_predecessor', False),
                    'missing_successor': row.get('missing_successor', False),
                    'status': row.get('Activity Status', 'Unknown')
                })

        self.metrics['missing_logic'] = {
            'count': len(missing_logic),
            'activities': missing_logic,
            'target': 0,
            'status': 'fail' if len(missing_logic) > 0 else 'pass'
        }

        if len(missing_logic) > 0:
            self.issues.append({
                'category': 'Logic Completeness',
                'severity': 'high',
                'title': f'Missing Logic: {len(missing_logic)} activities',
                'description': 'Activities without predecessors or successors indicate incomplete schedule logic.',
                'count': len(missing_logic),
                'recommendation': 'Add logical relationships to all activities. Every activity (except start/finish milestones) should have both predecessors and successors.',
                'affected_activities': [ml['activity_id'] for ml in missing_logic]
            })

    def _analyze_open_ends(self):
        """Analyze open-ended activities"""
        open_starts = []
        open_finishes = []

        for idx, row in self.df.iterrows():
            if row.get('missing_predecessor', False):
                open_starts.append(row['Activity ID'])
            if row.get('missing_successor', False):
                open_finishes.append(row['Activity ID'])

        self.metrics['open_ends'] = {
            'open_starts': len(open_starts),
            'open_finishes': len(open_finishes),
            'total_open_ends': len(set(open_starts + open_finishes)),
            'activities': {
                'open_starts': open_starts,
                'open_finishes': open_finishes
            }
        }

    def _analyze_long_durations(self):
        """Analyze activities with long durations"""
        long_activities = []
        very_long_activities = []

        # Use At Completion Duration (P6 work days) - REQUIRED
        duration_col = 'At Completion Duration'

        if duration_col in self.df.columns:
            # Filter out milestones - they have duration = 0 by nature
            # Check Activity Type for milestone indicators
            non_milestone_df = self.df.copy()
            if 'Activity Type' in self.df.columns:
                # Exclude activities where Activity Type contains "Milestone" (case insensitive)
                non_milestone_df = self.df[~self.df['Activity Type'].str.contains('Milestone', case=False, na=False)]

            for idx, row in non_milestone_df.iterrows():
                duration = row.get(duration_col, 0)
                if pd.notna(duration) and duration > 0:  # Exclude zero-duration activities
                    if duration > 150:  # ~5 months
                        very_long_activities.append({
                            'activity_id': row['Activity ID'],
                            'activity_name': row['Activity Name'],
                            'duration': int(duration)
                        })
                    elif duration > 20:
                        long_activities.append({
                            'activity_id': row['Activity ID'],
                            'activity_name': row['Activity Name'],
                            'duration': int(duration)
                        })

        self.metrics['long_durations'] = {
            'count_over_20_days': len(long_activities) + len(very_long_activities),
            'count_over_5_months': len(very_long_activities),
            'activities_20_days': long_activities,
            'activities_5_months': very_long_activities
        }

        if len(very_long_activities) > 0:
            self.issues.append({
                'category': 'Schedule Granularity',
                'severity': 'medium',
                'title': f'Very Long Duration Activities: {len(very_long_activities)}',
                'description': f'Found {len(very_long_activities)} activities exceeding 5 months duration (excluding milestones).',
                'count': len(very_long_activities),
                'recommendation': 'Break down long duration activities into smaller, manageable tasks (target: 10-20 days).',
                'affected_activities': [vla['activity_id'] for vla in very_long_activities]
            })

    def _analyze_average_duration(self):
        """Calculate average activity duration using At Completion Duration from P6"""
        # Use At Completion Duration (P6 work days) - REQUIRED
        duration_col = 'At Completion Duration'

        if duration_col in self.df.columns:
            # Filter out milestones - they have duration = 0 by nature
            # Check Activity Type for milestone indicators
            non_milestone_df = self.df.copy()
            milestone_count = 0

            if 'Activity Type' in self.df.columns:
                # Identify milestones
                is_milestone = self.df['Activity Type'].str.contains('Milestone', case=False, na=False)
                milestone_count = is_milestone.sum()
                # Exclude milestones from analysis
                non_milestone_df = self.df[~is_milestone]

            # Get durations for non-milestone activities
            durations = non_milestone_df[duration_col].dropna()

            # Filter out zero-duration activities (shouldn't happen for non-milestones, but just in case)
            durations = durations[durations > 0]

            # Calculate statistics (no need for absolute values - P6 durations are always positive)
            if len(durations) > 0:
                avg_duration = float(durations.mean())
                median_duration = float(durations.median())
                min_duration = float(durations.min())
                max_duration = float(durations.max())
            else:
                avg_duration = median_duration = min_duration = max_duration = 0.0

            self.metrics['average_duration'] = {
                'mean': round(avg_duration, 2),
                'median': round(median_duration, 2),
                'min': round(min_duration, 2),
                'max': round(max_duration, 2),
                'target_range': [10, 20],
                'status': 'pass' if 10 <= avg_duration <= 20 else 'warning',
                'total_activities_analyzed': len(durations),
                'milestones_excluded': int(milestone_count),
                'source_column': duration_col
            }
        else:
            # At Completion Duration column not found
            self.metrics['average_duration'] = {
                'mean': 0,
                'median': 0,
                'status': 'unknown',
                'source_column': 'none',
                'error': 'At Completion Duration column not found in CSV. Ensure P6 export includes this column.'
            }
            self.warnings.append("⚠️  'At Completion Duration' column not found. Duration analysis cannot be performed. Please ensure your P6 export includes the 'At Completion Duration' or 'At Completion Duration(d)' column.")

    def _analyze_high_float(self):
        """Analyze activities with high float"""
        high_float_activities = []

        if 'Total Float' in self.df.columns:
            # Calculate project duration for threshold
            if 'Start' in self.df.columns and 'Finish' in self.df.columns:
                project_duration = int((self.df['Finish'].max() - self.df['Start'].min()).days)
                float_threshold = float(project_duration * 0.5)  # 50% of project duration
            else:
                float_threshold = 100  # Default threshold

            for idx, row in self.df.iterrows():
                total_float = row.get('Total Float', 0)
                if pd.notna(total_float) and total_float > float_threshold:
                    high_float_activities.append({
                        'activity_id': row['Activity ID'],
                        'activity_name': row['Activity Name'],
                        'total_float': int(total_float)
                    })

        self.metrics['high_float'] = {
            'count': len(high_float_activities),
            'threshold': float_threshold if 'float_threshold' in locals() else 100,
            'activities': high_float_activities
        }

    def _analyze_float_ratio(self):
        """Calculate float ratio"""
        if 'Total Float' in self.df.columns:
            avg_float = float(self.df['Total Float'].mean())

            duration_col = 'At Completion Duration' if 'At Completion Duration' in self.df.columns else 'calculated_duration'
            if duration_col in self.df.columns:
                avg_duration = float(self.df[duration_col].mean())
                float_ratio = float(avg_float / avg_duration) if avg_duration > 0 else 0.0

                self.metrics['float_ratio'] = {
                    'ratio': round(float_ratio, 2),
                    'avg_float': round(avg_float, 2),
                    'avg_duration': round(avg_duration, 2),
                    'target_range': [0.5, 1.5],
                    'status': 'pass' if 0.5 <= float_ratio <= 1.5 else 'warning'
                }
            else:
                self.metrics['float_ratio'] = {'ratio': 0.0, 'status': 'unknown'}
        else:
            self.metrics['float_ratio'] = {'ratio': 0.0, 'status': 'unknown'}

    def _analyze_comprehensive_float(self):
        """
        Comprehensive Total Float analysis with all KPIs
        Implements DCMA best practices for float analysis
        """
        if 'Total Float' not in self.df.columns:
            self.metrics['comprehensive_float'] = {
                'error': 'Total Float column not found',
                'status': 'unknown'
            }
            self.warnings.append("⚠️  'Total Float' column not found. Float analysis cannot be performed.")
            return

        # Get total float values, excluding NaN
        float_series = self.df['Total Float'].dropna()
        total_activities = len(float_series)

        if total_activities == 0:
            self.metrics['comprehensive_float'] = {
                'error': 'No Total Float data available',
                'status': 'unknown'
            }
            return

        # Calculate project duration for context
        project_duration = 0
        if 'Start' in self.df.columns and 'Finish' in self.df.columns:
            project_duration = int((self.df['Finish'].max() - self.df['Start'].min()).days)

        # KPI 1: Critical Path (float = 0)
        critical_mask = float_series == 0
        critical_count = critical_mask.sum()
        critical_pct = float((critical_count / total_activities * 100)) if total_activities > 0 else 0.0

        critical_activities = []
        if critical_count > 0:
            critical_idx = float_series[critical_mask].index
            for idx in critical_idx[:20]:  # Limit to top 20
                row = self.df.loc[idx]
                critical_activities.append({
                    'activity_id': row['Activity ID'],
                    'activity_name': row['Activity Name'],
                    'total_float': 0
                })

        # KPI 2: Near-Critical (0 < float ≤ 10)
        near_critical_mask = (float_series > 0) & (float_series <= 10)
        near_critical_count = near_critical_mask.sum()
        near_critical_pct = float((near_critical_count / total_activities * 100)) if total_activities > 0 else 0.0

        near_critical_activities = []
        if near_critical_count > 0:
            near_critical_idx = float_series[near_critical_mask].index
            for idx in near_critical_idx[:20]:
                row = self.df.loc[idx]
                near_critical_activities.append({
                    'activity_id': row['Activity ID'],
                    'activity_name': row['Activity Name'],
                    'total_float': float(row['Total Float'])
                })

        # KPI 3: Negative Float (behind schedule)
        negative_mask = float_series < 0
        negative_count = negative_mask.sum()
        negative_pct = float((negative_count / total_activities * 100)) if total_activities > 0 else 0.0

        negative_activities = []
        if negative_count > 0:
            # Sort by float (most negative first)
            negative_float = float_series[negative_mask].sort_values()
            for idx in negative_float.index[:20]:  # Top 20 worst
                row = self.df.loc[idx]
                negative_activities.append({
                    'activity_id': row['Activity ID'],
                    'activity_name': row['Activity Name'],
                    'total_float': float(row['Total Float']),
                    'wbs_code': str(row.get('WBS Code', 'N/A'))
                })

        # KPI 4: Float Ratio (Average Total Float / Average Remaining Duration)
        avg_float = float(float_series.mean())

        # For remaining duration, use At Completion Duration for not started/in progress activities
        remaining_duration = 0
        if 'At Completion Duration' in self.df.columns and 'Activity Status' in self.df.columns:
            not_complete = self.df['Activity Status'] != 'Completed'
            remaining_durations = self.df.loc[not_complete, 'At Completion Duration'].dropna()
            avg_remaining = float(remaining_durations.mean()) if len(remaining_durations) > 0 else 0.0
            float_ratio = float(avg_float / avg_remaining) if avg_remaining > 0 else 0.0
        else:
            # Fallback to using total duration
            if 'At Completion Duration' in self.df.columns:
                avg_duration = float(self.df['At Completion Duration'].mean())
                float_ratio = float(avg_float / avg_duration) if avg_duration > 0 else 0.0
                avg_remaining = avg_duration
            else:
                float_ratio = 0.0
                avg_remaining = 0.0

        # KPI 5: Statistical measures
        median_float = float(float_series.median())
        std_float = float(float_series.std())

        # KPI 6: Excessive Float (>50% of project duration)
        if project_duration > 0:
            excessive_threshold = project_duration * 0.5
            excessive_mask = float_series > excessive_threshold
            excessive_count = excessive_mask.sum()
            excessive_pct = float((excessive_count / total_activities * 100)) if total_activities > 0 else 0.0

            excessive_activities = []
            if excessive_count > 0:
                excessive_idx = float_series[excessive_mask].index
                for idx in excessive_idx[:20]:
                    row = self.df.loc[idx]
                    excessive_activities.append({
                        'activity_id': row['Activity ID'],
                        'activity_name': row['Activity Name'],
                        'total_float': float(row['Total Float'])
                    })
        else:
            excessive_count = 0
            excessive_pct = 0.0
            excessive_threshold = 0.0
            excessive_activities = []

        # KPI 7: Most negative float (worst delay)
        most_negative = float(float_series.min()) if len(float_series) > 0 else 0

        # Float Distribution for histogram
        float_distribution = {
            'negative': int(negative_count),           # < 0 (Behind)
            'critical': int(critical_count),           # = 0 (Critical)
            'near_critical': int(near_critical_count), # 1-10 (Near-critical)
            'low_risk': int(((float_series > 10) & (float_series <= 30)).sum()),  # 11-30
            'comfortable': int((float_series > 30).sum())  # > 30
        }

        # Float by WBS Code for box plot
        float_by_wbs = {}
        if 'WBS Code' in self.df.columns:
            wbs_groups = self.df.groupby('WBS Code')['Total Float'].apply(list).to_dict()
            # Limit to top 10 WBS codes by activity count
            wbs_counts = self.df['WBS Code'].value_counts().head(10)
            # Convert numpy types to native Python types for JSON serialization
            float_by_wbs = {
                str(wbs): [float(f) for f in wbs_groups.get(wbs, [])]
                for wbs in wbs_counts.index
            }

        # Store comprehensive metrics - ONLY ESSENTIAL KPIs (no chart data)
        # Chart data will be calculated on-demand in the dashboard from activities
        self.metrics['comprehensive_float'] = {
            # KPI Summary
            'total_activities': total_activities,
            'project_duration': project_duration,

            # Critical Path (KPI 1) - Numbers only
            'critical': {
                'count': int(critical_count),
                'percentage': round(critical_pct, 2),
                'status': 'warning' if critical_pct > 15 else 'pass',
                'target': '≤15%'
            },

            # Near-Critical (KPI 2) - Numbers only
            'near_critical': {
                'count': int(near_critical_count),
                'percentage': round(near_critical_pct, 2)
            },

            # Negative Float (KPI 3) - Numbers only
            'negative_float': {
                'count': int(negative_count),
                'percentage': round(negative_pct, 2),
                'status': 'fail' if negative_count > 0 else 'pass',
                'severity': 'high' if negative_count > 0 else 'none'
            },

            # Float Ratio (KPI 4)
            'float_ratio': {
                'ratio': round(float_ratio, 2),
                'avg_float': round(avg_float, 2),
                'avg_remaining_duration': round(avg_remaining, 2),
                'target_range': [0.5, 1.5],
                'status': 'pass' if 0.5 <= float_ratio <= 1.5 else 'warning'
            },

            # Statistical Measures (KPI 5)
            'statistics': {
                'mean': round(avg_float, 2),
                'median': round(median_float, 2),
                'std_dev': round(std_float, 2),
                'min': round(float(float_series.min()), 2),
                'max': round(float(float_series.max()), 2)
            },

            # Excessive Float (KPI 6) - Numbers only
            'excessive_float': {
                'count': int(excessive_count),
                'percentage': round(excessive_pct, 2),
                'threshold': round(excessive_threshold, 2),
                'status': 'warning' if excessive_count > 0 else 'pass'
            },

            # Most Negative (KPI 7)
            'most_negative': round(most_negative, 2)

            # NOTE: Chart data (distribution, float_by_wbs, activity lists) are NOT stored
            # They will be calculated on-demand in the dashboard from schedule_data['activities']
            # This keeps metrics small, fast to serialize, and prevents database bloat
        }

        # Create issues based on float analysis
        # Issue 1: Negative Float (High Priority)
        if negative_count > 0:
            self.issues.append({
                'category': 'Schedule Performance',
                'severity': 'high',
                'title': f'Negative Float: {negative_count} activities behind schedule',
                'description': f'Found {negative_count} activities ({negative_pct:.1f}%) with negative float. Most negative: {most_negative:.0f} days. These activities are behind schedule and threatening project completion.',
                'count': int(negative_count),
                'recommendation': 'Immediate action required: Review critical path, crash activities, add resources, or negotiate deadline extensions. Focus on activities with most negative float first.',
                'affected_activities': [a['activity_id'] for a in negative_activities]
            })

        # Issue 2: Excessive Critical Path
        if critical_pct > 15:
            self.issues.append({
                'category': 'Schedule Risk',
                'severity': 'medium',
                'title': f'Excessive Critical Path: {critical_pct:.1f}% of activities',
                'description': f'Found {critical_count} critical activities ({critical_pct:.1f}%). DCMA recommends ≤15% critical activities. High critical percentage indicates limited schedule flexibility.',
                'count': int(critical_count),
                'recommendation': 'Review schedule logic to add flexibility. Consider: parallel paths, reducing activity dependencies, adding float through early starts, or breaking down critical activities.',
                'affected_activities': [a['activity_id'] for a in critical_activities[:10]]
            })

        # Issue 3: Poor Float Ratio
        if float_ratio < 0.5 or float_ratio > 1.5:
            severity = 'high' if float_ratio < 0.3 or float_ratio > 2.0 else 'medium'
            if float_ratio < 0.5:
                desc = f'Float Ratio is {float_ratio:.2f}, below target range (0.5-1.5). Schedule has insufficient float relative to remaining work.'
                rec = 'Schedule is too tight. Consider: extending timeline, reducing scope, adding resources, or parallelizing work to add float.'
            else:
                desc = f'Float Ratio is {float_ratio:.2f}, above target range (0.5-1.5). Excessive float may indicate missing logic or unrealistic schedule.'
                rec = 'Review schedule logic. Excessive float often indicates: missing dependencies, incorrect constraints, or overly conservative durations.'

            self.issues.append({
                'category': 'Schedule Health',
                'severity': severity,
                'title': f'Poor Float Ratio: {float_ratio:.2f}',
                'description': desc,
                'count': 1,
                'recommendation': rec,
                'affected_activities': []
            })

        # Issue 4: Excessive Float Activities
        if excessive_count > 0 and excessive_pct > 10:
            self.issues.append({
                'category': 'Logic Quality',
                'severity': 'low',
                'title': f'Excessive Float: {excessive_count} activities with >50% project duration float',
                'description': f'Found {excessive_count} activities ({excessive_pct:.1f}%) with float exceeding {excessive_threshold:.0f} days (50% of project duration). May indicate missing logic links.',
                'count': int(excessive_count),
                'recommendation': 'Review activities with excessive float for missing predecessors/successors. Verify logic relationships are complete.',
                'affected_activities': [a['activity_id'] for a in excessive_activities[:10]]
            })

    def _analyze_activity_distribution(self):
        """Analyze activity distribution over time"""
        if 'Start' in self.df.columns and 'Finish' in self.df.columns:
            # Group by month
            self.df['start_month'] = pd.to_datetime(self.df['Start']).dt.to_period('M')
            distribution = self.df.groupby('start_month').size().to_dict()

            # Convert Period to string for JSON serialization
            distribution_str = {str(k): v for k, v in distribution.items()}

            self.metrics['activity_distribution'] = {
                'by_month': distribution_str,
                'total_months': len(distribution)
            }
        else:
            self.metrics['activity_distribution'] = {'by_month': {}, 'total_months': 0}

    def _analyze_resource_assignment(self):
        """Analyze resource assignments"""
        unassigned = []

        if 'Resource Names' in self.df.columns:
            for idx, row in self.df.iterrows():
                resources = row.get('Resource Names', '')
                if pd.isna(resources) or str(resources).strip() == '' or str(resources).lower() == 'nan':
                    unassigned.append(row['Activity ID'])

        self.metrics['resource_assignment'] = {
            'unassigned_count': len(unassigned),
            'assigned_count': len(self.df) - len(unassigned),
            'unassigned_activities': unassigned
        }

    def _analyze_milestones(self):
        """Analyze milestones"""
        milestones = []

        duration_col = 'At Completion Duration' if 'At Completion Duration' in self.df.columns else 'calculated_duration'

        if duration_col in self.df.columns:
            for idx, row in self.df.iterrows():
                duration = row.get(duration_col, 1)
                if duration == 0 or pd.isna(duration):
                    milestones.append({
                        'activity_id': row['Activity ID'],
                        'activity_name': row['Activity Name'],
                        'type': row.get('Activity Type', 'Unknown')
                    })

        self.metrics['milestones'] = {
            'count': len(milestones),
            'milestones': milestones
        }

    def _analyze_activity_types(self):
        """Analyze activity types distribution"""
        if 'Activity Type' in self.df.columns:
            type_distribution = self.df['Activity Type'].value_counts().to_dict()
        else:
            type_distribution = {}

        self.metrics['activity_types'] = {
            'distribution': type_distribution
        }

    def _analyze_relationship_types(self):
        """Analyze relationship type distribution"""
        relationship_types = {'FS': 0, 'SS': 0, 'FF': 0, 'SF': 0}
        total_relationships = 0

        for idx, row in self.df.iterrows():
            predecessors = row.get('predecessor_list', [])
            for pred in predecessors:
                rel_type = pred.get('type', 'FS')
                if rel_type in relationship_types:
                    relationship_types[rel_type] += 1
                total_relationships += 1

        # Calculate percentages
        percentages = {}
        for rel_type, count in relationship_types.items():
            percentages[rel_type] = round((count / total_relationships * 100), 2) if total_relationships > 0 else 0

        self.metrics['relationship_types'] = {
            'counts': relationship_types,
            'percentages': percentages,
            'total': total_relationships
        }

        # Check for excessive non-FS relationships
        non_fs_percentage = 100 - percentages['FS']
        if non_fs_percentage > 20:
            self.issues.append({
                'category': 'Logic Quality',
                'severity': 'low',
                'title': f'High Non-FS Relationships: {non_fs_percentage:.1f}%',
                'description': f'Found {non_fs_percentage:.1f}% non-Finish-to-Start relationships. While valid, this may indicate overly complex logic.',
                'count': total_relationships - relationship_types['FS'],
                'recommendation': 'Review SS, FF, and SF relationships to ensure they are necessary and correctly represent the work flow.'
            })

    def _analyze_activity_status(self):
        """Analyze activity status distribution"""
        if 'Activity Status' in self.df.columns:
            status_distribution = self.df['Activity Status'].value_counts().to_dict()
        else:
            status_distribution = {}

        self.metrics['activity_status'] = {
            'distribution': status_distribution,
            'total_activities': len(self.df)
        }
