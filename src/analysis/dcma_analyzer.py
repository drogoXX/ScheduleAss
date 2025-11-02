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
                avg_duration = durations.mean()
                median_duration = durations.median()
                min_duration = durations.min()
                max_duration = durations.max()
            else:
                avg_duration = median_duration = min_duration = max_duration = 0

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
                project_duration = (self.df['Finish'].max() - self.df['Start'].min()).days
                float_threshold = project_duration * 0.5  # 50% of project duration
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
            avg_float = self.df['Total Float'].mean()

            duration_col = 'At Completion Duration' if 'At Completion Duration' in self.df.columns else 'calculated_duration'
            if duration_col in self.df.columns:
                avg_duration = self.df[duration_col].mean()
                float_ratio = avg_float / avg_duration if avg_duration > 0 else 0

                self.metrics['float_ratio'] = {
                    'ratio': round(float_ratio, 2),
                    'avg_float': round(avg_float, 2),
                    'avg_duration': round(avg_duration, 2),
                    'target_range': [0.5, 1.5],
                    'status': 'pass' if 0.5 <= float_ratio <= 1.5 else 'warning'
                }
            else:
                self.metrics['float_ratio'] = {'ratio': 0, 'status': 'unknown'}
        else:
            self.metrics['float_ratio'] = {'ratio': 0, 'status': 'unknown'}

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
