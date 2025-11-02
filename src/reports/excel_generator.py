"""
Excel Detailed Analysis Report Generator
Generates comprehensive Excel workbooks with schedule analysis
"""

import pandas as pd
import io
from typing import Dict, List
from datetime import datetime


class ExcelGenerator:
    """Generates detailed analysis reports in Excel format"""

    def __init__(self, project_name: str, schedule_data: Dict, analysis_results: Dict):
        """
        Initialize Excel generator

        Args:
            project_name: Name of the project
            schedule_data: Parsed schedule data
            analysis_results: Complete analysis results
        """
        self.project_name = project_name
        self.schedule_data = schedule_data
        self.analysis_results = analysis_results

    def generate(self) -> bytes:
        """Generate the Excel report and return as bytes"""
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary Sheet
            self._create_summary_sheet(writer)

            # Issues Sheet
            self._create_issues_sheet(writer)

            # Activities Sheet
            self._create_activities_sheet(writer)

            # Logic Sheet
            self._create_logic_sheet(writer)

            # Metrics Sheet
            self._create_metrics_sheet(writer)

            # Recommendations Sheet
            self._create_recommendations_sheet(writer)

        output.seek(0)
        return output.getvalue()

    def _create_summary_sheet(self, writer):
        """Create summary metrics sheet"""
        summary_data = []

        # Project Information
        summary_data.append(['PROJECT INFORMATION', ''])
        summary_data.append(['Project Name', self.project_name])
        summary_data.append(['Analysis Date', datetime.now().strftime('%Y-%m-%d %H:%M')])
        summary_data.append(['File Name', self.schedule_data.get('file_name', 'N/A')])
        summary_data.append(['', ''])

        # Health Score
        health_score = self.analysis_results['performance_metrics']['health_score']
        summary_data.append(['SCHEDULE HEALTH', ''])
        summary_data.append(['Overall Score', f"{health_score['score']:.1f}/100"])
        summary_data.append(['Rating', health_score['rating']])
        summary_data.append(['', ''])

        # Statistics
        stats = self.analysis_results['performance_metrics']['statistics']
        summary_data.append(['SCHEDULE STATISTICS', ''])
        summary_data.append(['Total Activities', stats.get('total_activities', 0)])
        summary_data.append(['Total Relationships', stats.get('total_relationships', 0)])
        summary_data.append(['Total Milestones', stats.get('total_milestones', 0)])
        summary_data.append(['Critical Activities', stats.get('critical_activities', 0)])
        summary_data.append(['Project Start', stats.get('project_start', 'N/A')])
        summary_data.append(['Project Finish', stats.get('project_finish', 'N/A')])
        summary_data.append(['Project Duration (days)', stats.get('project_duration_days', 'N/A')])
        summary_data.append(['', ''])

        # Performance Metrics
        summary_data.append(['PERFORMANCE METRICS', ''])

        cpli = self.analysis_results['performance_metrics'].get('cpli', {})
        summary_data.append(['CPLI', cpli.get('value', 0)])
        summary_data.append(['CPLI Status', cpli.get('status', 'unknown')])
        summary_data.append(['CPLI Target', cpli.get('target', 0.95)])

        bei = self.analysis_results['performance_metrics'].get('bei', {})
        summary_data.append(['BEI', bei.get('value', 0)])
        summary_data.append(['BEI Status', bei.get('status', 'unknown')])
        summary_data.append(['BEI Target', bei.get('target', 0.95)])
        summary_data.append(['', ''])

        # DCMA Metrics
        summary_data.append(['DCMA COMPLIANCE METRICS', ''])
        dcma = self.analysis_results['dcma_metrics']

        summary_data.append(['Negative Lags', dcma.get('negative_lags', {}).get('count', 0)])
        summary_data.append(['Positive Lags %', dcma.get('positive_lags', {}).get('percentage', 0)])
        summary_data.append(['Hard Constraints %', dcma.get('hard_constraints', {}).get('percentage', 0)])
        summary_data.append(['Missing Logic', dcma.get('missing_logic', {}).get('count', 0)])
        summary_data.append(['Long Duration Activities', dcma.get('long_durations', {}).get('count_over_20_days', 0)])
        summary_data.append(['Average Duration (days)', dcma.get('average_duration', {}).get('mean', 0)])

        # Create DataFrame and write
        df_summary = pd.DataFrame(summary_data, columns=['Metric', 'Value'])
        df_summary.to_excel(writer, sheet_name='Summary', index=False)

    def _create_issues_sheet(self, writer):
        """Create issues detail sheet"""
        issues = self.analysis_results.get('issues', [])

        if not issues:
            df_issues = pd.DataFrame([['No issues identified']], columns=['Message'])
        else:
            issues_data = []
            for issue in issues:
                issues_data.append({
                    'Priority': issue['severity'].upper(),
                    'Category': issue['category'],
                    'Title': issue['title'],
                    'Description': issue['description'],
                    'Count': issue.get('count', 0),
                    'Recommendation': issue['recommendation']
                })
            df_issues = pd.DataFrame(issues_data)

        df_issues.to_excel(writer, sheet_name='Issues', index=False)

    def _create_activities_sheet(self, writer):
        """Create activities detail sheet"""
        activities = self.schedule_data.get('activities', [])

        if not activities:
            df_activities = pd.DataFrame([['No activities found']], columns=['Message'])
        else:
            # Select key columns for export
            df_all = pd.DataFrame(activities)

            # Select and order columns
            key_columns = ['Activity ID', 'Activity Name', 'Activity Status', 'Start', 'Finish',
                          'Total Float', 'At Completion Duration']

            # Add optional columns if they exist
            optional_columns = ['WBS Code', 'Primary Constraint', 'Activity Type',
                              'missing_logic', 'has_hard_constraint', 'is_long_duration']

            export_columns = []
            for col in key_columns:
                if col in df_all.columns:
                    export_columns.append(col)

            for col in optional_columns:
                if col in df_all.columns:
                    export_columns.append(col)

            df_activities = df_all[export_columns]

        df_activities.to_excel(writer, sheet_name='Activities', index=False)

    def _create_logic_sheet(self, writer):
        """Create logic relationships sheet"""
        activities = self.schedule_data.get('activities', [])
        logic_data = []

        for activity in activities:
            activity_id = activity.get('Activity ID', '')
            activity_name = activity.get('Activity Name', '')

            # Predecessors
            predecessors = activity.get('predecessor_list', [])
            for pred in predecessors:
                logic_data.append({
                    'Activity ID': activity_id,
                    'Activity Name': activity_name,
                    'Relationship': 'Predecessor',
                    'Related Activity': pred.get('activity', ''),
                    'Type': pred.get('type', 'FS'),
                    'Lag': pred.get('lag', 0)
                })

            # If no predecessors, add a row indicating that
            if not predecessors:
                logic_data.append({
                    'Activity ID': activity_id,
                    'Activity Name': activity_name,
                    'Relationship': 'Predecessor',
                    'Related Activity': 'NONE',
                    'Type': '',
                    'Lag': ''
                })

        if logic_data:
            df_logic = pd.DataFrame(logic_data)
        else:
            df_logic = pd.DataFrame([['No logic relationships found']], columns=['Message'])

        df_logic.to_excel(writer, sheet_name='Logic', index=False)

    def _create_metrics_sheet(self, writer):
        """Create detailed metrics breakdown sheet"""
        metrics_data = []

        dcma = self.analysis_results['dcma_metrics']

        # Negative Lags Detail
        metrics_data.append(['NEGATIVE LAGS', '', '', ''])
        neg_lags = dcma.get('negative_lags', {}).get('activities', [])
        if neg_lags:
            metrics_data.append(['Activity ID', 'Activity Name', 'Predecessor', 'Lag'])
            for nl in neg_lags:
                metrics_data.append([
                    nl.get('activity_id', ''),
                    nl.get('activity_name', ''),
                    nl.get('predecessor', ''),
                    nl.get('lag', 0)
                ])
        else:
            metrics_data.append(['No negative lags found', '', '', ''])
        metrics_data.append(['', '', '', ''])

        # Hard Constraints Detail
        metrics_data.append(['HARD CONSTRAINTS', '', '', ''])
        constraints = dcma.get('hard_constraints', {}).get('activities', [])
        if constraints:
            metrics_data.append(['Activity ID', 'Activity Name', 'Constraint Type', ''])
            for const in constraints:
                metrics_data.append([
                    const.get('activity_id', ''),
                    const.get('activity_name', ''),
                    const.get('constraint_type', ''),
                    ''
                ])
        else:
            metrics_data.append(['No hard constraints found', '', '', ''])
        metrics_data.append(['', '', '', ''])

        # Missing Logic Detail
        metrics_data.append(['MISSING LOGIC', '', '', ''])
        missing = dcma.get('missing_logic', {}).get('activities', [])
        if missing:
            metrics_data.append(['Activity ID', 'Activity Name', 'Missing Predecessor', 'Missing Successor'])
            for ml in missing:
                metrics_data.append([
                    ml.get('activity_id', ''),
                    ml.get('activity_name', ''),
                    'Yes' if ml.get('missing_predecessor', False) else 'No',
                    'Yes' if ml.get('missing_successor', False) else 'No'
                ])
        else:
            metrics_data.append(['No missing logic found', '', '', ''])

        df_metrics = pd.DataFrame(metrics_data)
        df_metrics.to_excel(writer, sheet_name='Metrics Detail', index=False, header=False)

    def _create_recommendations_sheet(self, writer):
        """Create recommendations sheet"""
        recommendations = self.analysis_results.get('recommendations', [])

        if not recommendations:
            df_recs = pd.DataFrame([['No recommendations at this time']], columns=['Message'])
        else:
            recs_data = []
            for rec in recommendations:
                recs_data.append({
                    'Priority': rec['priority'].upper(),
                    'Category': rec['category'],
                    'Title': rec['title'],
                    'Description': rec['description'],
                    'Recommendation': rec['recommendation'],
                    'Impact': rec['impact'],
                    'Effort': rec['effort']
                })
            df_recs = pd.DataFrame(recs_data)

        df_recs.to_excel(writer, sheet_name='Recommendations', index=False)
