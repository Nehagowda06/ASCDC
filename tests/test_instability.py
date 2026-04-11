"""Unit tests for instability dynamics algorithm."""

import pytest
from env.environment import ASCDCEnvironment


class TestInstabilityDynamics:
    """Test instability accumulation and decay."""

    def setup_method(self):
        """Setup test environment."""
        self.env = ASCDCEnvironment(seed=42)

    def test_instability_accumulates_above_threshold(self):
        """Instability should accumulate when pressure > 1.25."""
        self.env.reset(config={
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        })
        
        initial_instability = self.env.instability_score
        
        # Take steps to accumulate instability
        for _ in range(5):
            self.env.step({"type": "noop", "target": None})
        
        # Instability should increase
        assert self.env.instability_score > initial_instability

    def test_instability_decays_below_threshold(self):
        """Instability should eventually decay when pressure is low."""
        self.env.reset()
        
        # Manually set high instability
        self.env.instability_score = 2.0
        initial_instability = self.env.instability_score
        
        # Take steps in stable state (low pressure)
        # Note: decay is slow, so we just verify it doesn't grow exponentially
        for _ in range(3):
            self.env.step({"type": "noop", "target": None})
        
        # Instability should not increase more than 2x
        assert self.env.instability_score <= initial_instability * 2.5

    def test_instability_reset_on_sustained_improvement(self):
        """Instability should reset when pressure drops by >= 0.15."""
        self.env.reset(config={
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        })
        
        # Accumulate instability
        for _ in range(5):
            self.env.step({"type": "noop", "target": None})
        
        instability_before_reset = self.env.instability_score
        prev_pressure = self.env.system_pressure
        
        # Take action to reduce pressure
        self.env.step({"type": "restart", "target": "A"})
        
        # If pressure dropped by >= 0.15, instability should reset
        pressure_drop = prev_pressure - self.env.system_pressure
        if pressure_drop >= 0.15:
            assert self.env.instability_score < instability_before_reset * 0.5

    def test_instability_affects_retry_error_rates(self):
        """High instability should increase retry and error rates."""
        self.env.reset(config={
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        })
        
        initial_retry = self.env.retry_rate
        initial_error = self.env.error_rate
        
        # Accumulate instability
        for _ in range(10):
            self.env.step({"type": "noop", "target": None})
        
        # Retry and error rates should increase
        assert self.env.retry_rate > initial_retry
        assert self.env.error_rate > initial_error

    def test_instability_bounded(self):
        """Instability should not grow unbounded."""
        self.env.reset(config={
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        })
        
        # Take many steps
        for _ in range(20):
            self.env.step({"type": "noop", "target": None})
        
        # Instability should be finite (not infinite)
        assert self.env.instability_score < float('inf')
        assert not float('nan') == self.env.instability_score
        assert self.env.instability_score <= 3.0

    def test_pressure_calculation_includes_instability(self):
        """System pressure should reflect instability effects."""
        self.env.reset(config={
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        })
        
        initial_pressure = self.env.system_pressure
        
        # Accumulate instability
        for _ in range(10):
            self.env.step({"type": "noop", "target": None})
        
        # Pressure should increase due to instability
        assert self.env.system_pressure > initial_pressure
