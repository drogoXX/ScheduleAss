"""
Schedule Metrics Calculator
Calculates CPLI, BEI, and overall schedule health score
"""

import pandas as pd
import numpy as np
from typing import Dict

from src.analysis import health_score


class MetricsCalculator:
    """Calculates advanced schedule performance metrics"""

    def __init__(self, schedule_data: Dict, dcma_metrics: Dict):
        """
        Initialize calculator

        Args:
            schedule_data: Parsed schedule data
            dcma_metrics: DCMA analysis metrics
        """
        self.schedule_data = schedule_data
        self.dcma_metrics = dcma_metrics
        self.df = pd.DataFrame(schedule_data['activities'])

    def calculate_all_metrics(self) -> Dict:
        """Calculate all performance metrics"""
        metrics = {}

        # Calculate CPLI (Critical Path Length Index)
        metrics['cpli'] = self._calculate_cpli()

        # Calculate BEI (Baseline Execution Index)
        metrics['bei'] = self._calculate_bei()

        # Calculate Schedule Health Score. CPLI and BEI feed into it, so they
        # are passed in rather than recomputed.
        metrics['health_score'] = self._calculate_health_score(
            cpli_value=metrics['cpli'].get('value'),
            bei_value=metrics['bei'].get('value'),
        )

        # Calculate overall statistics
        metrics['statistics'] = self._calculate_statistics()

        return metrics

    def _calculate_cpli(self) -> Dict:
        """
        Calculate Critical Path Length Index
        CPLI = (Critical Path Duration + Total Float) / Critical Path Duration
        Target: ≥ 0.95
        """
        # Simplified CPLI calculation
        # In a full implementation, this would identify the actual critical path
        # For now, we'll use minimum float activities as critical path approximation

        if 'Total Float' not in self.df.columns:
            return {
                'value': 0,
                'status': 'unknown',
                'target': 0.95,
                'description': 'Unable to calculate CPLI - Total Float not available'
            }

        # Find critical or near-critical activities (float <= 5)
        critical_activities = self.df[self.df['Total Float'] <= 5]

        if len(critical_activities) == 0:
            return {
                'value': 0,
                'status': 'unknown',
                'target': 0.95,
                'description': 'No critical path identified'
            }

        # Calculate critical path duration (sum of critical activities)
        duration_col = 'At Completion Duration' if 'At Completion Duration' in self.df.columns else 'calculated_duration'

        if duration_col not in self.df.columns:
            return {
                'value': 0,
                'status': 'unknown',
                'target': 0.95,
                'description': 'Duration data not available'
            }

        # Estimate critical path length. Fall back to summing critical activity
        # durations when the schedule has no usable dates.
        critical_path_duration = 0
        if 'Start' in self.df.columns and 'Finish' in self.df.columns:
            earliest = pd.to_datetime(self.df['Start'], errors='coerce').min()
            latest = pd.to_datetime(self.df['Finish'], errors='coerce').max()
            if pd.notna(earliest) and pd.notna(latest):
                critical_path_duration = (latest - earliest).days

        if not critical_path_duration or critical_path_duration <= 0:
            critical_path_duration = pd.to_numeric(
                critical_activities[duration_col], errors='coerce').sum()

        if pd.isna(critical_path_duration):
            critical_path_duration = 0

        # Average total float
        avg_total_float = self.df['Total Float'].mean()
        if pd.isna(avg_total_float):
            avg_total_float = 0.0

        # Calculate CPLI
        if critical_path_duration > 0:
            cpli = (critical_path_duration + avg_total_float) / critical_path_duration
        else:
            cpli = 0

        # Determine status
        if cpli >= 0.95:
            status = 'pass'
        elif cpli >= 0.90:
            status = 'warning'
        else:
            status = 'fail'

        return {
            'value': round(cpli, 3),
            'critical_path_duration': int(critical_path_duration),
            'avg_total_float': round(avg_total_float, 2),
            'status': status,
            'target': 0.95,
            'description': 'Critical Path Length Index measures schedule compression risk'
        }

    def _calculate_bei(self) -> Dict:
        """
        Calculate Baseline Execution Index
        BEI = Completed Tasks / Planned Completed Tasks
        Target: ≥ 0.95
        """
        if 'Activity Status' not in self.df.columns:
            return {
                'value': 0,
                'status': 'unknown',
                'target': 0.95,
                'description': 'Unable to calculate BEI - Activity Status not available'
            }

        # Count activities by status
        status_counts = self.df['Activity Status'].value_counts().to_dict()

        completed = status_counts.get('Completed', 0)
        in_progress = status_counts.get('In Progress', 0)
        not_started = status_counts.get('Not Started', 0)

        # Planned completed = total activities that should be done by now
        # For simplification, assume all non "Not Started" should be completed
        planned_completed = completed + in_progress

        if planned_completed == 0:
            return {
                'value': 1.0,
                'completed': completed,
                'planned': planned_completed,
                'status': 'pass',
                'target': 0.95,
                'description': 'No activities planned for completion yet'
            }

        bei = completed / planned_completed

        # Determine status
        if bei >= 0.95:
            status = 'pass'
        elif bei >= 0.90:
            status = 'warning'
        else:
            status = 'fail'

        return {
            'value': round(bei, 3),
            'completed': completed,
            'planned': planned_completed,
            'in_progress': in_progress,
            'not_started': not_started,
            'status': status,
            'target': 0.95,
            'description': 'Baseline Execution Index measures schedule adherence'
        }

    def _calculate_health_score(self, cpli_value=None, bei_value=None) -> Dict:
        """
        Calculate the overall schedule health score (0-100).

        Delegates to src.analysis.health_score, where the DCMA thresholds and
        the weighting are defined and documented in one place. See that module
        for the rationale behind each weight.
        """
        return health_score.calculate(
            dcma_metrics=self.dcma_metrics,
            total_activities=len(self.df),
            cpli_value=cpli_value,
            bei_value=bei_value,
        )

    def _calculate_statistics(self) -> Dict:
        """Calculate general schedule statistics"""
        stats = {
            'total_activities': len(self.df),
            'total_relationships': self.dcma_metrics.get('relationship_types', {}).get('total', 0),
            'total_milestones': self.dcma_metrics.get('milestones', {}).get('count', 0)
        }

        # Date range
        if 'Start' in self.df.columns and 'Finish' in self.df.columns:
            stats['project_start'] = self.df['Start'].min().strftime('%Y-%m-%d') if pd.notna(self.df['Start'].min()) else None
            stats['project_finish'] = self.df['Finish'].max().strftime('%Y-%m-%d') if pd.notna(self.df['Finish'].max()) else None

            if stats['project_start'] and stats['project_finish']:
                duration = (pd.to_datetime(stats['project_finish']) - pd.to_datetime(stats['project_start'])).days
                stats['project_duration_days'] = duration
                stats['project_duration_months'] = round(duration / 30, 1)

        # Activity status breakdown
        if 'Activity Status' in self.df.columns:
            status_counts = self.df['Activity Status'].value_counts().to_dict()
            stats['status_breakdown'] = status_counts

        # Critical activities (float <= 5)
        if 'Total Float' in self.df.columns:
            critical_count = len(self.df[self.df['Total Float'] <= 5])
            stats['critical_activities'] = critical_count
            stats['critical_percentage'] = round((critical_count / len(self.df) * 100), 2)

        return stats
