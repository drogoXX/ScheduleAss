"""
Test script to verify missing logic breakdown calculations
"""
import pandas as pd
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer

def test_missing_logic_breakdown():
    """Test that missing logic breakdown is calculated correctly"""

    # Create test data with different missing logic scenarios
    test_data = {
        'Activity ID': ['A001', 'A002', 'A003', 'A004', 'A005'],
        'Activity Name': [
            'Activity with Missing Pred Only',
            'Activity with Missing Succ Only',
            'Activity with Missing Both',
            'Activity with Complete Logic',
            'Another with Missing Both'
        ],
        'Predecessors': ['', 'A001', '', 'A002', ''],
        'Successors': ['A002', '', '', 'A005', ''],
        'Activity Status': ['Not Started'] * 5,
        'Start': pd.to_datetime(['2024-01-01'] * 5),
        'Finish': pd.to_datetime(['2024-01-10'] * 5),
        'At Completion Duration': [10] * 5,
    }

    df = pd.DataFrame(test_data)

    # Initialize parser and manually set up predecessor/successor lists
    df['predecessor_list'] = [
        [],  # A001: no predecessor
        [{'activity_id': 'A001', 'type': 'FS', 'lag': 0}],  # A002: has predecessor
        [],  # A003: no predecessor
        [{'activity_id': 'A002', 'type': 'FS', 'lag': 0}],  # A004: has predecessor
        []   # A005: no predecessor
    ]

    df['successor_list'] = [
        [{'activity_id': 'A002', 'type': 'FS', 'lag': 0}],  # A001: has successor
        [],  # A002: no successor
        [],  # A003: no successor
        [{'activity_id': 'A005', 'type': 'FS', 'lag': 0}],  # A004: has successor
        []   # A005: no successor
    ]

    # Calculate missing logic flags
    df['missing_predecessor'] = df['predecessor_list'].apply(lambda x: len(x) == 0)
    df['missing_successor'] = df['successor_list'].apply(lambda x: len(x) == 0)
    df['missing_logic'] = df['missing_predecessor'] | df['missing_successor']

    print("\n=== Test Data ===")
    print(df[['Activity ID', 'Activity Name', 'missing_predecessor', 'missing_successor', 'missing_logic']])

    # Analyze with DCMAAnalyzer
    analyzer = DCMAAnalyzer(df, project_name="Test Project")
    analyzer._analyze_missing_logic()
    analyzer._analyze_missing_predecessors()
    analyzer._analyze_missing_successors()

    # Get results
    missing_logic_metrics = analyzer.metrics['missing_logic']
    dcma_pred_metrics = analyzer.metrics['dcma_missing_predecessors']
    dcma_succ_metrics = analyzer.metrics['dcma_missing_successors']

    print("\n=== Missing Logic Breakdown ===")
    print(f"Total Missing Logic: {missing_logic_metrics['count']}")
    print(f"  - Missing Predecessor Only: {missing_logic_metrics['missing_predecessor_only_count']}")
    print(f"  - Missing Successor Only: {missing_logic_metrics['missing_successor_only_count']}")
    print(f"  - Missing Both: {missing_logic_metrics['missing_both_count']}")
    print(f"\nDCMA Missing Predecessors: {dcma_pred_metrics['count']}")
    print(f"DCMA Missing Successors: {dcma_succ_metrics['count']}")

    # Expected values:
    # A001: missing pred only -> 1
    # A002: missing succ only -> 1
    # A003: missing both -> 1
    # A005: missing both -> 1
    # Total unique: 4
    # Missing pred only: 1 (A001)
    # Missing succ only: 1 (A002)
    # Missing both: 2 (A003, A005)
    # DCMA Missing Pred: 3 (A001, A003, A005)
    # DCMA Missing Succ: 3 (A002, A003, A005)

    expected_total = 4
    expected_pred_only = 1
    expected_succ_only = 1
    expected_both = 2
    expected_dcma_pred = 3
    expected_dcma_succ = 3

    print("\n=== Validation ===")
    assert missing_logic_metrics['count'] == expected_total, \
        f"Total should be {expected_total}, got {missing_logic_metrics['count']}"
    print(f"✓ Total Missing Logic: {expected_total}")

    assert missing_logic_metrics['missing_predecessor_only_count'] == expected_pred_only, \
        f"Missing Pred Only should be {expected_pred_only}, got {missing_logic_metrics['missing_predecessor_only_count']}"
    print(f"✓ Missing Predecessor Only: {expected_pred_only}")

    assert missing_logic_metrics['missing_successor_only_count'] == expected_succ_only, \
        f"Missing Succ Only should be {expected_succ_only}, got {missing_logic_metrics['missing_successor_only_count']}"
    print(f"✓ Missing Successor Only: {expected_succ_only}")

    assert missing_logic_metrics['missing_both_count'] == expected_both, \
        f"Missing Both should be {expected_both}, got {missing_logic_metrics['missing_both_count']}"
    print(f"✓ Missing Both: {expected_both}")

    assert dcma_pred_metrics['count'] == expected_dcma_pred, \
        f"DCMA Missing Pred should be {expected_dcma_pred}, got {dcma_pred_metrics['count']}"
    print(f"✓ DCMA Missing Predecessors: {expected_dcma_pred}")

    assert dcma_succ_metrics['count'] == expected_dcma_succ, \
        f"DCMA Missing Succ should be {expected_dcma_succ}, got {dcma_succ_metrics['count']}"
    print(f"✓ DCMA Missing Successors: {expected_dcma_succ}")

    # Verify the relationship: pred_only + succ_only + both = total
    calculated_total = (missing_logic_metrics['missing_predecessor_only_count'] +
                       missing_logic_metrics['missing_successor_only_count'] +
                       missing_logic_metrics['missing_both_count'])
    assert calculated_total == missing_logic_metrics['count'], \
        f"Breakdown doesn't add up: {calculated_total} != {missing_logic_metrics['count']}"
    print(f"✓ Breakdown adds up correctly: {expected_pred_only} + {expected_succ_only} + {expected_both} = {expected_total}")

    # Verify DCMA counts
    calculated_dcma_pred = (missing_logic_metrics['missing_predecessor_only_count'] +
                           missing_logic_metrics['missing_both_count'])
    assert calculated_dcma_pred == dcma_pred_metrics['count'], \
        f"DCMA Pred calculation wrong: {calculated_dcma_pred} != {dcma_pred_metrics['count']}"
    print(f"✓ DCMA Predecessors = Pred Only + Both: {expected_pred_only} + {expected_both} = {expected_dcma_pred}")

    calculated_dcma_succ = (missing_logic_metrics['missing_successor_only_count'] +
                           missing_logic_metrics['missing_both_count'])
    assert calculated_dcma_succ == dcma_succ_metrics['count'], \
        f"DCMA Succ calculation wrong: {calculated_dcma_succ} != {dcma_succ_metrics['count']}"
    print(f"✓ DCMA Successors = Succ Only + Both: {expected_succ_only} + {expected_both} = {expected_dcma_succ}")

    print("\n✅ All tests passed! Missing logic breakdown is calculated correctly.")


if __name__ == "__main__":
    test_missing_logic_breakdown()
