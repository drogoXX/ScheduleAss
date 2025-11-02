"""
Recommendations Engine
Generates prioritized, actionable recommendations based on schedule analysis
"""

from typing import Dict, List


class RecommendationsEngine:
    """Generates intelligent recommendations for schedule improvement"""

    def __init__(self, dcma_metrics: Dict, performance_metrics: Dict, issues: List[Dict]):
        """
        Initialize recommendations engine

        Args:
            dcma_metrics: DCMA analysis metrics
            performance_metrics: Performance metrics (CPLI, BEI, health score)
            issues: List of identified issues
        """
        self.dcma_metrics = dcma_metrics
        self.performance_metrics = performance_metrics
        self.issues = issues
        self.recommendations = []

    def generate_recommendations(self) -> List[Dict]:
        """Generate all recommendations"""
        # Generate recommendations from issues
        for issue in self.issues:
            self.recommendations.append({
                'priority': issue['severity'],
                'category': issue['category'],
                'title': issue['title'],
                'description': issue['description'],
                'recommendation': issue['recommendation'],
                'impact': self._assess_impact(issue),
                'effort': self._assess_effort(issue),
                'affected_count': issue.get('count', 0)
            })

        # Generate recommendations from performance metrics
        self._add_cpli_recommendations()
        self._add_bei_recommendations()
        self._add_health_score_recommendations()

        # Sort by priority
        priority_order = {'high': 1, 'medium': 2, 'low': 3}
        self.recommendations.sort(key=lambda x: priority_order.get(x['priority'], 4))

        return self.recommendations

    def _assess_impact(self, issue: Dict) -> str:
        """Assess the impact of an issue"""
        severity = issue.get('severity', 'low')
        count = issue.get('count', 0)

        if severity == 'high':
            return 'High - Significantly affects schedule reliability'
        elif severity == 'medium':
            if count > 20:
                return 'Medium-High - Multiple occurrences may impact schedule'
            return 'Medium - May affect schedule predictability'
        else:
            return 'Low - Minor impact on schedule quality'

    def _assess_effort(self, issue: Dict) -> str:
        """Assess the effort required to fix an issue"""
        count = issue.get('count', 0)

        if count > 50:
            return 'High - Requires significant schedule rework'
        elif count > 20:
            return 'Medium - Requires moderate schedule updates'
        elif count > 5:
            return 'Low-Medium - Requires some schedule adjustments'
        else:
            return 'Low - Can be fixed quickly'

    def _add_cpli_recommendations(self):
        """Add recommendations based on CPLI"""
        cpli_data = self.performance_metrics.get('cpli', {})
        cpli_value = cpli_data.get('value', 0)

        if cpli_value == 0:
            return

        if cpli_value < 0.90:
            self.recommendations.append({
                'priority': 'high',
                'category': 'Schedule Performance',
                'title': f'Critical Path Length Index Below Target: {cpli_value:.3f}',
                'description': f'CPLI of {cpli_value:.3f} is below the target of 0.95, indicating insufficient schedule margin.',
                'recommendation': 'Add schedule float by: 1) Reviewing and optimizing critical path activities, 2) Identifying opportunities to run activities in parallel, 3) Re-sequencing work to reduce path length.',
                'impact': 'High - Schedule is at risk of delays with minimal buffer',
                'effort': 'Medium-High - Requires logic optimization',
                'affected_count': 0
            })
        elif cpli_value < 0.95:
            self.recommendations.append({
                'priority': 'medium',
                'category': 'Schedule Performance',
                'title': f'Critical Path Length Index Near Target: {cpli_value:.3f}',
                'description': f'CPLI of {cpli_value:.3f} is close to but below the target of 0.95.',
                'recommendation': 'Consider adding modest schedule margin to improve resilience against delays.',
                'impact': 'Medium - Limited schedule flexibility',
                'effort': 'Low-Medium - Minor adjustments needed',
                'affected_count': 0
            })

    def _add_bei_recommendations(self):
        """Add recommendations based on BEI"""
        bei_data = self.performance_metrics.get('bei', {})
        bei_value = bei_data.get('value', 0)
        status = bei_data.get('status', 'unknown')

        if status == 'unknown' or bei_value == 0:
            return

        if bei_value < 0.90:
            self.recommendations.append({
                'priority': 'high',
                'category': 'Schedule Execution',
                'title': f'Baseline Execution Index Below Target: {bei_value:.3f}',
                'description': f'BEI of {bei_value:.3f} indicates schedule is behind planned progress.',
                'recommendation': 'Immediate action required: 1) Identify root causes of delays, 2) Develop recovery plan, 3) Re-baseline if necessary, 4) Increase monitoring frequency.',
                'impact': 'High - Project is falling behind schedule',
                'effort': 'High - Requires recovery planning',
                'affected_count': bei_data.get('planned', 0) - bei_data.get('completed', 0)
            })
        elif bei_value < 0.95:
            self.recommendations.append({
                'priority': 'medium',
                'category': 'Schedule Execution',
                'title': f'Baseline Execution Index Below Target: {bei_value:.3f}',
                'description': f'BEI of {bei_value:.3f} indicates minor schedule slippage.',
                'recommendation': 'Monitor closely and implement corrective actions to prevent further delays.',
                'impact': 'Medium - Schedule is slightly behind',
                'effort': 'Medium - Requires corrective action',
                'affected_count': bei_data.get('planned', 0) - bei_data.get('completed', 0)
            })

    def _add_health_score_recommendations(self):
        """Add recommendations based on overall health score"""
        health_data = self.performance_metrics.get('health_score', {})
        score = health_data.get('score', 0)
        rating = health_data.get('rating', 'Unknown')

        if score < 60:
            self.recommendations.append({
                'priority': 'high',
                'category': 'Overall Schedule Quality',
                'title': f'Schedule Health Score Critical: {score:.1f}/100',
                'description': f'Overall schedule health is rated as "{rating}" with a score of {score:.1f}/100.',
                'recommendation': 'Comprehensive schedule review and remediation required. Prioritize fixing high-severity issues first: negative lags, missing logic, and hard constraints.',
                'impact': 'High - Schedule quality is inadequate for reliable project management',
                'effort': 'High - Requires significant rework',
                'affected_count': 0
            })
        elif score < 75:
            self.recommendations.append({
                'priority': 'medium',
                'category': 'Overall Schedule Quality',
                'title': f'Schedule Health Score Needs Improvement: {score:.1f}/100',
                'description': f'Overall schedule health is rated as "{rating}" with a score of {score:.1f}/100.',
                'recommendation': 'Address medium and high priority issues to improve schedule quality. Focus on logic completeness and constraint management.',
                'impact': 'Medium - Schedule quality limits predictability',
                'effort': 'Medium - Requires focused improvements',
                'affected_count': 0
            })

    def get_summary(self) -> Dict:
        """Get summary of recommendations"""
        high_priority = [r for r in self.recommendations if r['priority'] == 'high']
        medium_priority = [r for r in self.recommendations if r['priority'] == 'medium']
        low_priority = [r for r in self.recommendations if r['priority'] == 'low']

        return {
            'total_recommendations': len(self.recommendations),
            'high_priority_count': len(high_priority),
            'medium_priority_count': len(medium_priority),
            'low_priority_count': len(low_priority),
            'top_3_recommendations': self.recommendations[:3] if len(self.recommendations) >= 3 else self.recommendations
        }
