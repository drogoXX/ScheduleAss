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
        """Add DCMA 14-Point compliance checklist"""
        self.document.add_heading('DCMA 14-Point Compliance', level=1)

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
