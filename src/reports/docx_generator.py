"""
DOCX Executive Summary Report Generator
Generates professional Word documents with schedule analysis
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime
from typing import Dict, List
import io


class DOCXGenerator:
    """Generates executive summary reports in DOCX format"""

    def __init__(self, project_name: str, schedule_data: Dict, analysis_results: Dict):
        """
        Initialize DOCX generator

        Args:
            project_name: Name of the project
            schedule_data: Parsed schedule data
            analysis_results: Complete analysis results including metrics and recommendations
        """
        self.project_name = project_name
        self.schedule_data = schedule_data
        self.analysis_results = analysis_results
        self.document = Document()

    def generate(self) -> bytes:
        """Generate the DOCX report and return as bytes"""
        # Set up document properties
        self._setup_document()

        # Add content sections
        self._add_cover_page()
        self._add_executive_summary()
        self._add_dcma_compliance()
        self._add_missing_logic_breakdown()
        self._add_key_metrics()
        self._add_wbs_analysis()
        self._add_issues_summary()
        self._add_recommendations()
        self._add_appendix()

        # Save to bytes
        file_stream = io.BytesIO()
        self.document.save(file_stream)
        file_stream.seek(0)
        return file_stream.getvalue()

    def _setup_document(self):
        """Set up document styles and properties"""
        # Set document title
        self.document.core_properties.title = f"Schedule Quality Analysis - {self.project_name}"
        self.document.core_properties.author = "Schedule Quality Analyzer"
        self.document.core_properties.created = datetime.now()

    def _add_cover_page(self):
        """Add cover page"""
        # Title
        title = self.document.add_heading('Schedule Quality Analysis Report', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Project name
        project = self.document.add_heading(self.project_name, level=1)
        project.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Date
        date_para = self.document.add_paragraph()
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_run = date_para.add_run(f"\nAnalysis Date: {datetime.now().strftime('%B %d, %Y')}")
        date_run.font.size = Pt(14)

        # Health score
        health_score = self.analysis_results['performance_metrics']['health_score']
        score_para = self.document.add_paragraph()
        score_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        score_run = score_para.add_run(f"\n\nSchedule Health Score: {health_score['score']:.1f}/100")
        score_run.font.size = Pt(18)
        score_run.font.bold = True

        rating_run = score_para.add_run(f"\nRating: {health_score['rating']}")
        rating_run.font.size = Pt(16)
        self._set_color_by_rating(rating_run, health_score['rating'])

        # Page break
        self.document.add_page_break()

    def _add_executive_summary(self):
        """Add executive summary section"""
        self.document.add_heading('Executive Summary', level=1)

        # Overall assessment
        health_score = self.analysis_results['performance_metrics']['health_score']
        stats = self.analysis_results['performance_metrics']['statistics']

        summary_text = f"""
This report presents a comprehensive analysis of the {self.project_name} schedule based on industry-standard \
DCMA 14-Point Assessment and GAO Schedule Assessment Guide best practices.

The schedule contains {stats['total_activities']} activities with an overall health score of \
{health_score['score']:.1f}/100, rated as "{health_score['rating']}".
        """

        self.document.add_paragraph(summary_text.strip())

        # Key findings
        self.document.add_heading('Key Findings', level=2)

        issues = self.analysis_results.get('issues', [])
        high_priority_issues = [i for i in issues if i['severity'] == 'high']

        if high_priority_issues:
            self.document.add_paragraph('High Priority Issues:', style='List Bullet')
            for issue in high_priority_issues[:5]:
                self.document.add_paragraph(f"{issue['title']}", style='List Bullet 2')
        else:
            self.document.add_paragraph('No high-priority issues identified.', style='List Bullet')

        # Add spacing
        self.document.add_paragraph()

    def _add_dcma_compliance(self):
        """Add DCMA 14-Point compliance checklist with all categories"""
        self.document.add_heading('DCMA 14-Point Compliance Assessment', level=1)

        # Get DCMA 14-point summary
        dcma_14 = self.analysis_results.get('dcma_14_point', {})

        if not dcma_14:
            # Fallback to old format if dcma_14_point not available
            self._add_dcma_compliance_legacy()
            return

        # Overall Score
        overall_para = self.document.add_paragraph()
        overall_para.add_run(f"Overall Score: {dcma_14.get('overall_score_text', 'N/A')}").bold = True
        overall_para.add_run(f"\n{dcma_14.get('overall_pass_count', 0)} PASS  |  ")
        overall_para.add_run(f"{dcma_14.get('overall_fail_count', 0)} FAIL  |  ")
        overall_para.add_run(f"{dcma_14.get('overall_na_count', 0)} N/A  |  ")
        overall_para.add_run(f"{dcma_14.get('overall_manual_count', 0)} MANUAL")

        self.document.add_paragraph()

        # Iterate through categories
        categories = dcma_14.get('categories', {})

        for cat_name, cat_data in categories.items():
            # Category header
            self.document.add_heading(f"Category {cat_data['number']}: {cat_name}", level=2)

            # Calculate category pass/fail
            cat_metrics = cat_data['metrics']
            cat_pass = sum(1 for m in cat_metrics if m['status'] == 'pass')
            cat_fail = sum(1 for m in cat_metrics if m['status'] == 'fail')
            cat_total = len([m for m in cat_metrics if m['status'] not in ['n/a', 'manual', 'unknown']])

            if cat_total > 0:
                cat_score_text = f"[{cat_pass}/{cat_total}]"
            else:
                cat_score_text = "[N/A]"

            # Add category score
            cat_para = self.document.add_paragraph()
            cat_para.add_run(f"Category Score: {cat_score_text}").italic = True
            self.document.add_paragraph()

            # Create table for metrics
            table = self.document.add_table(rows=1, cols=4)
            table.style = 'Light Grid Accent 1'

            # Header row
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = '#'
            hdr_cells[1].text = 'Metric'
            hdr_cells[2].text = 'Status'
            hdr_cells[3].text = 'Result'

            # Add metrics for this category
            for metric in cat_metrics:
                row_cells = table.add_row().cells
                row_cells[0].text = str(metric['number'])
                row_cells[1].text = metric['name']

                # Status with symbols
                status = metric['status'].upper()
                if status == 'PASS':
                    row_cells[2].text = '✓ PASS'
                elif status == 'FAIL':
                    row_cells[2].text = '✗ FAIL'
                elif status == 'N/A':
                    row_cells[2].text = '○ N/A'
                elif status == 'MANUAL':
                    row_cells[2].text = '◐ MANUAL'
                else:
                    row_cells[2].text = '? UNKNOWN'

                row_cells[3].text = metric['description']

            self.document.add_paragraph()

            # Add recommendations for failed metrics
            failed_metrics = [m for m in cat_metrics if m['status'] == 'fail' and m.get('recommendation')]
            if failed_metrics:
                self.document.add_heading('Recommendations:', level=3)
                for metric in failed_metrics:
                    rec_para = self.document.add_paragraph(style='List Bullet')
                    rec_para.add_run(f"{metric['name']}: ").bold = True
                    rec_para.add_run(metric['recommendation'])

            self.document.add_paragraph()

        # Add legend
        self.document.add_heading('Status Legend', level=2)
        legend_para = self.document.add_paragraph()
        legend_para.add_run('✓ PASS').bold = True
        legend_para.add_run(' - Meets DCMA standard\n')
        legend_para.add_run('✗ FAIL').bold = True
        legend_para.add_run(' - Does not meet DCMA standard (action required)\n')
        legend_para.add_run('○ N/A').bold = True
        legend_para.add_run(' - Not applicable or data not available\n')
        legend_para.add_run('◐ MANUAL').bold = True
        legend_para.add_run(' - Manual verification required')

        self.document.add_paragraph()

    def _add_dcma_compliance_legacy(self):
        """Legacy DCMA compliance section (fallback)"""
        dcma_metrics = self.analysis_results['dcma_metrics']

        # Create checklist table
        table = self.document.add_table(rows=1, cols=3)
        table.style = 'Light Grid Accent 1'

        # Header row
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Metric'
        hdr_cells[1].text = 'Status'
        hdr_cells[2].text = 'Result'

        # Add metrics
        checklist = [
            ('Negative Lags', dcma_metrics.get('negative_lags', {}).get('status', 'unknown'),
             f"{dcma_metrics.get('negative_lags', {}).get('count', 0)} found (Target: 0)"),
            ('Positive Lags', dcma_metrics.get('positive_lags', {}).get('status', 'unknown'),
             f"{dcma_metrics.get('positive_lags', {}).get('percentage', 0):.1f}% (Target: ≤5%)"),
            ('Hard Constraints', dcma_metrics.get('hard_constraints', {}).get('status', 'unknown'),
             f"{dcma_metrics.get('hard_constraints', {}).get('percentage', 0):.1f}% (Target: ≤10%)"),
            ('Missing Logic', dcma_metrics.get('missing_logic', {}).get('status', 'unknown'),
             f"{dcma_metrics.get('missing_logic', {}).get('count', 0)} activities (Target: 0)"),
        ]

        for metric_name, status, result in checklist:
            row_cells = table.add_row().cells
            row_cells[0].text = metric_name
            row_cells[1].text = status.upper()
            row_cells[2].text = result

        self.document.add_paragraph()

    def _add_missing_logic_breakdown(self):
        """Add detailed missing logic breakdown section"""
        self.document.add_heading('Logic Completeness Analysis', level=1)

        dcma_metrics = self.analysis_results.get('dcma_metrics', {})
        missing_logic_info = dcma_metrics.get('missing_logic', {})

        # Check if there's any missing logic
        total_missing = missing_logic_info.get('count', 0)

        if total_missing == 0:
            self.document.add_paragraph('✓ All activities have complete logic relationships (predecessors and successors).')
            self.document.add_paragraph()
            return

        # Add overview paragraph
        overview = self.document.add_paragraph()
        overview.add_run(f'Found {total_missing} activities with missing logic relationships. ').bold = True
        overview.add_run('Activities without proper predecessors or successors indicate incomplete schedule logic and can affect critical path calculations.')

        self.document.add_paragraph()

        # Create breakdown table
        self.document.add_heading('Missing Logic Breakdown', level=2)

        table = self.document.add_table(rows=1, cols=3)
        table.style = 'Light Grid Accent 1'

        # Header row
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Category'
        hdr_cells[1].text = 'Count'
        hdr_cells[2].text = 'Description'

        # Total
        row_cells = table.add_row().cells
        row_cells[0].text = 'Total Missing Logic'
        row_cells[1].text = str(total_missing)
        row_cells[2].text = 'Unique activities with missing predecessor and/or successor'

        # Missing predecessor only
        pred_only = missing_logic_info.get('missing_predecessor_only_count', 0)
        row_cells = table.add_row().cells
        row_cells[0].text = '  ├─ Missing Predecessor Only'
        row_cells[1].text = str(pred_only)
        row_cells[2].text = 'Activities that need predecessors added'

        # Missing successor only
        succ_only = missing_logic_info.get('missing_successor_only_count', 0)
        row_cells = table.add_row().cells
        row_cells[0].text = '  ├─ Missing Successor Only'
        row_cells[1].text = str(succ_only)
        row_cells[2].text = 'Activities that need successors added'

        # Missing both
        both_count = missing_logic_info.get('missing_both_count', 0)
        row_cells = table.add_row().cells
        row_cells[0].text = '  └─ Missing Both'
        row_cells[1].text = str(both_count)
        row_cells[2].text = 'Activities that need both predecessors and successors'

        self.document.add_paragraph()

        # DCMA validation section
        self.document.add_heading('DCMA Validation', level=2)

        dcma_pred = dcma_metrics.get('dcma_missing_predecessors', {}).get('count', 0)
        dcma_succ = dcma_metrics.get('dcma_missing_successors', {}).get('count', 0)

        validation_para = self.document.add_paragraph()
        validation_para.add_run('DCMA Missing Predecessors: ').bold = True
        validation_para.add_run(f'{dcma_pred} activities ')
        validation_para.add_run(f'(includes {pred_only} pred-only + {both_count} both)\n')

        validation_para.add_run('DCMA Missing Successors: ').bold = True
        validation_para.add_run(f'{dcma_succ} activities ')
        validation_para.add_run(f'(includes {succ_only} succ-only + {both_count} both)\n\n')

        validation_para.add_run('Note: ').bold = True
        validation_para.add_run('Activities missing both predecessors and successors are counted in each DCMA category. ')
        validation_para.add_run(f'Breakdown validation: {pred_only} + {succ_only} + {both_count} = {total_missing} total.')

        self.document.add_paragraph()

        # Add recommendation if there are issues
        if total_missing > 0:
            self.document.add_heading('Recommendation', level=2)
            rec_para = self.document.add_paragraph()
            rec_para.add_run('⚠ Action Required: ').bold = True
            rec_para.add_run('Add logical relationships to all activities. Every activity (except start/finish milestones) should have both predecessors and successors to ensure proper schedule logic and accurate critical path calculations.')

        self.document.add_paragraph()

    def _add_key_metrics(self):
        """Add key performance metrics"""
        self.document.add_heading('Key Performance Metrics', level=1)

        perf_metrics = self.analysis_results['performance_metrics']

        # CPLI
        cpli = perf_metrics.get('cpli', {})
        self.document.add_heading('Critical Path Length Index (CPLI)', level=2)
        self.document.add_paragraph(
            f"Value: {cpli.get('value', 0):.3f} (Target: ≥0.95)\n"
            f"Status: {cpli.get('status', 'unknown').upper()}\n"
            f"{cpli.get('description', '')}"
        )

        # BEI
        bei = perf_metrics.get('bei', {})
        self.document.add_heading('Baseline Execution Index (BEI)', level=2)
        self.document.add_paragraph(
            f"Value: {bei.get('value', 0):.3f} (Target: ≥0.95)\n"
            f"Status: {bei.get('status', 'unknown').upper()}\n"
            f"Completed: {bei.get('completed', 0)} / Planned: {bei.get('planned', 0)}"
        )

        self.document.add_paragraph()

    def _add_wbs_analysis(self):
        """Add WBS (Work Breakdown Structure) analysis"""
        # Check if WBS analysis is available
        wbs_analysis = self.analysis_results['dcma_metrics'].get('wbs_analysis', {})

        if not wbs_analysis.get('available'):
            # Skip this section if WBS data is not available
            return

        self.document.add_heading('WBS Analysis', level=1)

        # Overview
        self.document.add_paragraph(
            f"Total Activities: {wbs_analysis.get('total_activities', 0)}\n"
            f"Activities with WBS Codes: {wbs_analysis.get('activities_with_wbs', 0)}\n"
            f"Average WBS Depth: {wbs_analysis.get('avg_depth', 0):.1f}\n"
            f"Maximum WBS Depth: {wbs_analysis.get('max_depth', 0)}"
        )

        self.document.add_paragraph()

        # WBS Level 1 (Phases) Analysis
        level1 = wbs_analysis.get('level_1_phases', {})
        if level1:
            self.document.add_heading('WBS Level 1 - Phases', level=2)

            # Create table
            table = self.document.add_table(rows=1, cols=7)
            table.style = 'Light Grid Accent 1'

            # Header
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'Phase'
            hdr_cells[1].text = 'Activities'
            hdr_cells[2].text = 'Avg Float'
            hdr_cells[3].text = 'Critical'
            hdr_cells[4].text = 'Negative'
            hdr_cells[5].text = 'Health Score'
            hdr_cells[6].text = 'Rating'

            # Add phase data
            for wbs_code, stats in sorted(level1.items()):
                row_cells = table.add_row().cells
                health_score = stats.get('health_score', {})

                row_cells[0].text = f"Phase {wbs_code}"
                row_cells[1].text = str(stats.get('activity_count', 0))
                row_cells[2].text = f"{stats.get('avg_float', 0):.1f}"
                row_cells[3].text = str(stats.get('critical_count', 0))
                row_cells[4].text = str(stats.get('negative_float_count', 0))
                row_cells[5].text = f"{health_score.get('score', 0):.0f}/100"
                row_cells[6].text = health_score.get('rating', 'Unknown')

            self.document.add_paragraph()

        # WBS Level 2 (Areas) Analysis
        level2 = wbs_analysis.get('level_2_areas', {})
        if level2:
            self.document.add_heading('WBS Level 2 - Areas', level=2)

            # Create table
            table = self.document.add_table(rows=1, cols=7)
            table.style = 'Light Grid Accent 1'

            # Header
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'Area'
            hdr_cells[1].text = 'Activities'
            hdr_cells[2].text = 'Avg Float'
            hdr_cells[3].text = 'Critical'
            hdr_cells[4].text = '% Critical'
            hdr_cells[5].text = 'Health Score'
            hdr_cells[6].text = 'Rating'

            # Add area data (sorted by health score to show problem areas first)
            areas_with_scores = []
            for wbs_code, stats in level2.items():
                health_score = stats.get('health_score', {})
                areas_with_scores.append((wbs_code, stats, health_score.get('score', 0)))

            areas_with_scores.sort(key=lambda x: x[2])  # Sort by health score ascending

            for wbs_code, stats, _ in areas_with_scores:
                row_cells = table.add_row().cells
                health_score = stats.get('health_score', {})

                activity_count = stats.get('activity_count', 0)
                critical_count = stats.get('critical_count', 0)
                pct_critical = (critical_count / activity_count * 100) if activity_count > 0 else 0

                row_cells[0].text = f"Area {wbs_code}"
                row_cells[1].text = str(activity_count)
                row_cells[2].text = f"{stats.get('avg_float', 0):.1f}"
                row_cells[3].text = str(critical_count)
                row_cells[4].text = f"{pct_critical:.0f}%"
                row_cells[5].text = f"{health_score.get('score', 0):.0f}/100"
                row_cells[6].text = health_score.get('rating', 'Unknown')

            self.document.add_paragraph()

        # WBS Health Score Legend
        self.document.add_heading('Health Score Interpretation', level=2)
        self.document.add_paragraph(
            "Health scores are calculated based on:\n"
            "• Critical Path % (40 points): Lower is better\n"
            "• Average Float (30 points): Higher is better\n"
            "• Negative Float % (20 points): Lower is better\n"
            "• Activity Distribution (10 points): Balanced is better\n\n"
            "Rating Scale:\n"
            "• Excellent (80-100): Well-balanced, low risk\n"
            "• Good (65-79): Acceptable performance\n"
            "• Fair (50-64): Some concerns\n"
            "• Poor (35-49): Significant issues\n"
            "• Critical (0-34): Immediate attention required"
        )

        self.document.add_paragraph()

    def _add_issues_summary(self):
        """Add issues summary table"""
        self.document.add_heading('Issues Summary', level=1)

        issues = self.analysis_results.get('issues', [])

        if not issues:
            self.document.add_paragraph('No issues identified.')
            return

        # Create table
        table = self.document.add_table(rows=1, cols=4)
        table.style = 'Light Grid Accent 1'

        # Header
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Priority'
        hdr_cells[1].text = 'Category'
        hdr_cells[2].text = 'Issue'
        hdr_cells[3].text = 'Count'

        # Add issues
        for issue in issues:
            row_cells = table.add_row().cells
            row_cells[0].text = issue['severity'].upper()
            row_cells[1].text = issue['category']
            row_cells[2].text = issue['title']
            row_cells[3].text = str(issue.get('count', 0))

        self.document.add_paragraph()

    def _add_recommendations(self):
        """Add recommendations section"""
        self.document.add_heading('Recommendations', level=1)

        recommendations = self.analysis_results.get('recommendations', [])

        if not recommendations:
            self.document.add_paragraph('No recommendations at this time.')
            return

        # Group by priority
        high = [r for r in recommendations if r['priority'] == 'high']
        medium = [r for r in recommendations if r['priority'] == 'medium']
        low = [r for r in recommendations if r['priority'] == 'low']

        # High priority
        if high:
            self.document.add_heading('High Priority', level=2)
            for i, rec in enumerate(high, 1):
                self.document.add_heading(f"{i}. {rec['title']}", level=3)
                self.document.add_paragraph(f"Description: {rec['description']}")
                self.document.add_paragraph(f"Recommendation: {rec['recommendation']}")
                self.document.add_paragraph(f"Impact: {rec['impact']}")
                self.document.add_paragraph(f"Effort: {rec['effort']}")
                self.document.add_paragraph()

        # Medium priority
        if medium:
            self.document.add_heading('Medium Priority', level=2)
            for i, rec in enumerate(medium, 1):
                self.document.add_heading(f"{i}. {rec['title']}", level=3)
                self.document.add_paragraph(f"Recommendation: {rec['recommendation']}")
                self.document.add_paragraph()

    def _add_appendix(self):
        """Add appendix with methodology"""
        self.document.add_page_break()
        self.document.add_heading('Appendix: Methodology', level=1)

        methodology_text = """
This analysis is based on the following industry-standard frameworks:

1. DCMA 14-Point Schedule Assessment
   - Defense Contract Management Agency best practices for schedule quality
   - Focuses on logic integrity, schedule realism, and execution readiness

2. GAO Schedule Assessment Guide
   - Government Accountability Office guidelines for schedule management
   - Emphasizes comprehensive planning and reliable progress measurement

Key Metrics Definitions:

- CPLI (Critical Path Length Index): Measures schedule compression risk
  Formula: (Critical Path + Total Float) / Critical Path
  Target: ≥ 0.95

- BEI (Baseline Execution Index): Measures schedule adherence
  Formula: Completed Tasks / Planned Tasks
  Target: ≥ 0.95

- Health Score: Composite metric (0-100) based on DCMA compliance
  90-100: Excellent
  75-89: Good
  60-74: Fair
  40-59: Poor
  0-39: Critical
        """

        self.document.add_paragraph(methodology_text.strip())

    def _set_color_by_rating(self, run, rating: str):
        """Set text color based on rating"""
        color_map = {
            'Excellent': RGBColor(0, 128, 0),    # Green
            'Good': RGBColor(0, 0, 255),          # Blue
            'Fair': RGBColor(255, 165, 0),        # Orange
            'Poor': RGBColor(255, 140, 0),        # Dark Orange
            'Critical': RGBColor(255, 0, 0)       # Red
        }
        run.font.color.rgb = color_map.get(rating, RGBColor(0, 0, 0))
