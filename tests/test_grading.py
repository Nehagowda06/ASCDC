"""Unit tests for grading system algorithm."""

import pytest
from grader.grader import ASCDCGrader
from core.evaluation_metrics import evaluate_step_metrics


class TestASCDCGrader:
    """Test trajectory grading system."""

    def setup_method(self):
        """Setup grader."""
        self.grader = ASCDCGrader()

    def test_empty_trajectory_returns_zero(self):
        """Empty trajectory should score 0.0."""
        trajectory = []
        score = self.grader.grade(trajectory)
        assert score == 0.0

    def test_score_in_valid_range(self):
        """Score should be in [0, 1] range."""
        trajectory = [
            {
                "observation": {"system_pressure": 1.0, "instability_score": 0.5},
                "action": {"type": "scale", "target": "A"},
                "next_observation": {"system_pressure": 0.8, "instability_score": 0.4},
                "info": {"latency": 1.5, "stability": 0.7},
            },
            {
                "observation": {"system_pressure": 0.8, "instability_score": 0.4},
                "action": {"type": "noop", "target": None},
                "next_observation": {"system_pressure": 0.7, "instability_score": 0.3},
                "info": {"latency": 1.4, "stability": 0.8},
            },
        ]
        score = self.grader.grade(trajectory)
        assert 0.0 <= score <= 1.0

    def test_collapse_penalty_applied(self):
        """Collapsed system (pressure > 5.0) should get 0.2x penalty."""
        trajectory = [
            {
                "observation": {"system_pressure": 1.0, "instability_score": 0.5},
                "action": {"type": "noop", "target": None},
                "next_observation": {"system_pressure": 6.0, "instability_score": 2.0},
                "info": {
                    "latency": 1.5,
                    "stability": 0.7,
                    "failure_flags": {"collapsed": True},
                },
            },
        ]
        score = self.grader.grade(trajectory)
        # Score should be significantly reduced
        assert score < 0.3

    def test_good_trajectory_scores_high(self):
        """Good trajectory (stable, timely actions) should score high."""
        trajectory = [
            {
                "observation": {"system_pressure": 0.5, "instability_score": 0.1},
                "action": {"type": "scale", "target": "A"},
                "next_observation": {"system_pressure": 0.4, "instability_score": 0.05},
                "info": {
                    "latency": 1.2,
                    "stability": 0.8,
                    "necessity": True,
                    "timing_window": True,
                },
            },
            {
                "observation": {"system_pressure": 0.4, "instability_score": 0.05},
                "action": {"type": "noop", "target": None},
                "next_observation": {"system_pressure": 0.3, "instability_score": 0.02},
                "info": {
                    "latency": 1.1,
                    "stability": 0.9,
                    "necessity": False,
                },
            },
        ]
        score = self.grader.grade(trajectory)
        assert score > 0.5

    def test_poor_trajectory_scores_low(self):
        """Poor trajectory (high pressure, unnecessary actions) should score low."""
        trajectory = [
            {
                "observation": {"system_pressure": 2.0, "instability_score": 1.0},
                "action": {"type": "noop", "target": None},
                "next_observation": {"system_pressure": 2.5, "instability_score": 1.5},
                "info": {
                    "latency": 3.0,
                    "stability": 0.3,
                    "necessity": True,
                },
            },
            {
                "observation": {"system_pressure": 2.5, "instability_score": 1.5},
                "action": {"type": "scale", "target": "A"},
                "next_observation": {"system_pressure": 2.4, "instability_score": 1.4},
                "info": {
                    "latency": 3.2,
                    "stability": 0.2,
                    "necessity": False,
                },
            },
        ]
        score = self.grader.grade(trajectory)
        assert score < 0.4

    def test_stability_score_component(self):
        """Stability score should reflect latency and pressure."""
        trajectory = [
            {
                "observation": {"system_pressure": 0.5, "instability_score": 0.1},
                "action": {"type": "noop", "target": None},
                "next_observation": {"system_pressure": 0.5, "instability_score": 0.1},
                "info": {"latency": 1.2, "stability": 0.8},
            },
        ]
        score = self.grader.grade(trajectory)
        # Low latency and pressure should contribute to high score
        assert score > 0.5

    def test_timing_score_component(self):
        """Timing score should reward timely actions and penalize missed interventions."""
        # Good timing: action taken when necessary
        good_trajectory = [
            {
                "observation": {"system_pressure": 1.5, "instability_score": 0.5},
                "action": {"type": "scale", "target": "A"},
                "next_observation": {"system_pressure": 1.3, "instability_score": 0.4},
                "info": {
                    "latency": 1.5,
                    "stability": 0.7,
                    "necessity": True,
                    "timing_window": True,
                },
            },
        ]
        good_score = self.grader.grade(good_trajectory)
        
        # Bad timing: action taken when not necessary
        bad_trajectory = [
            {
                "observation": {"system_pressure": 0.3, "instability_score": 0.05},
                "action": {"type": "scale", "target": "A"},
                "next_observation": {"system_pressure": 0.3, "instability_score": 0.05},
                "info": {
                    "latency": 1.2,
                    "stability": 0.9,
                    "necessity": False,
                    "timing_window": False,
                },
            },
        ]
        bad_score = self.grader.grade(bad_trajectory)
        
        assert good_score > bad_score

    def test_smoothness_score_component(self):
        """Smoothness score should penalize oscillation."""
        # Oscillating trajectory
        oscillating = [
            {
                "observation": {"system_pressure": 1.0, "instability_score": 0.5},
                "action": {"type": "scale", "target": "A"},
                "next_observation": {"system_pressure": 0.8, "instability_score": 0.4},
                "info": {"latency": 1.5, "stability": 0.7, "pressure_delta": -0.2},
            },
            {
                "observation": {"system_pressure": 0.8, "instability_score": 0.4},
                "action": {"type": "throttle", "target": "B"},
                "next_observation": {"system_pressure": 1.0, "instability_score": 0.5},
                "info": {"latency": 1.6, "stability": 0.6, "pressure_delta": 0.2},
            },
        ]
        oscillating_score = self.grader.grade(oscillating)
        
        # Smooth trajectory
        smooth = [
            {
                "observation": {"system_pressure": 1.0, "instability_score": 0.5},
                "action": {"type": "scale", "target": "A"},
                "next_observation": {"system_pressure": 0.8, "instability_score": 0.4},
                "info": {"latency": 1.5, "stability": 0.7, "pressure_delta": -0.2},
            },
            {
                "observation": {"system_pressure": 0.8, "instability_score": 0.4},
                "action": {"type": "noop", "target": None},
                "next_observation": {"system_pressure": 0.7, "instability_score": 0.3},
                "info": {"latency": 1.4, "stability": 0.8, "pressure_delta": -0.1},
            },
        ]
        smooth_score = self.grader.grade(smooth)
        
        assert smooth_score > oscillating_score
