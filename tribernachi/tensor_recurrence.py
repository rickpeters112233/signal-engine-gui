"""
Tensor Recurrence Engine
Implements the two-channel tensor recurrence based on Axiom 12
"""

import numpy as np
from .constants import GAMMA, BETA, EPSILON, ZETA, RECURRENCE_HISTORY_DEPTH

class TensorRecurrence:
    """
    Two-channel tensor recurrence engine for predictive compression.

    Implements the recurrence equations from Axiom 12:
    a(n+1) = γa(n) + βb(n) - ε[a²+b²]a(n) + ζ[a²+b²]²a(n)
    b(n+1) = βa(n) + γb(n) - ε[a²+b²]b(n) + ζ[a²+b²]²b(n)
    """

    def __init__(self, gamma=GAMMA, beta=BETA, epsilon=EPSILON, zeta=ZETA):
        """
        Initialize the recurrence engine with coupling constants.

        Args:
            gamma: Radial growth coupling (default: φ ≈ 1.618)
            beta: Cross-channel coupling (default: 1.0)
            epsilon: Quadratic damping coefficient
            zeta: Cubic correction coefficient
        """
        self.gamma = gamma
        self.beta = beta
        self.epsilon = epsilon
        self.zeta = zeta

        # History buffers for a(n) and b(n)
        self.a_history = []
        self.b_history = []

    def tensorize(self, scalar_value):
        """
        Convert scalar value to tensor representation (a, b).

        Args:
            scalar_value: Scalar value to tensorize

        Returns:
            tuple: (a, b) tensor representation
        """
        # Simple tensorization: split into magnitude and phase
        # Using golden ratio decomposition
        magnitude = abs(scalar_value)
        sign = np.sign(scalar_value) if scalar_value != 0 else 1

        a = magnitude / (1 + self.gamma) * sign
        b = magnitude * self.gamma / (1 + self.gamma) * sign

        return (a, b)

    def detensorize(self, a, b):
        """
        Convert tensor representation (a, b) back to scalar.

        Args:
            a: First channel value
            b: Second channel value

        Returns:
            float: Reconstructed scalar value
        """
        # Inverse of tensorization
        # T(n) = √(a² + b²) preserving sign from dominant channel
        magnitude = np.sqrt(a**2 + b**2)
        sign = np.sign(a) if abs(a) >= abs(b) else np.sign(b)

        return magnitude * sign

    def predict_next(self, a_current, b_current):
        """
        Predict next state using recurrence equations.

        Args:
            a_current: Current value of channel a
            b_current: Current value of channel b

        Returns:
            tuple: (a_next, b_next) predicted values
        """
        # Calculate squared radius
        r_squared = a_current**2 + b_current**2

        # Apply recurrence equations (Axiom 12)
        a_next = (self.gamma * a_current +
                  self.beta * b_current -
                  self.epsilon * r_squared * a_current +
                  self.zeta * (r_squared**2) * a_current)

        b_next = (self.beta * a_current +
                  self.gamma * b_current -
                  self.epsilon * r_squared * b_current +
                  self.zeta * (r_squared**2) * b_current)

        return (a_next, b_next)

    def encode_sequence(self, scalar_sequence):
        """
        Encode a sequence of scalar values using predictive compression.

        Args:
            scalar_sequence: List or array of scalar values

        Returns:
            list: List of residuals (differences from predictions)
        """
        residuals = []
        self.a_history = []
        self.b_history = []

        for i, scalar in enumerate(scalar_sequence):
            a_actual, b_actual = self.tensorize(scalar)

            if i == 0:
                # First value: no prediction, store as-is
                residual_a = a_actual
                residual_b = b_actual
            else:
                # Predict based on previous state
                a_pred, b_pred = self.predict_next(
                    self.a_history[-1],
                    self.b_history[-1]
                )

                # Calculate residual
                residual_a = a_actual - a_pred
                residual_b = b_actual - b_pred

            # Store residual
            residuals.append((residual_a, residual_b))

            # Update history
            self.a_history.append(a_actual)
            self.b_history.append(b_actual)

            # Maintain history depth
            if len(self.a_history) > RECURRENCE_HISTORY_DEPTH:
                self.a_history.pop(0)
                self.b_history.pop(0)

        return residuals

    def decode_sequence(self, residuals):
        """
        Decode a sequence from residuals using inverse recurrence.

        Args:
            residuals: List of (residual_a, residual_b) tuples

        Returns:
            list: Reconstructed scalar sequence
        """
        scalars = []
        self.a_history = []
        self.b_history = []

        for i, (residual_a, residual_b) in enumerate(residuals):
            if i == 0:
                # First value: residual is the actual value
                a_actual = residual_a
                b_actual = residual_b
            else:
                # Predict and add residual
                a_pred, b_pred = self.predict_next(
                    self.a_history[-1],
                    self.b_history[-1]
                )

                a_actual = a_pred + residual_a
                b_actual = b_pred + residual_b

            # Reconstruct scalar
            scalar = self.detensorize(a_actual, b_actual)
            scalars.append(scalar)

            # Update history
            self.a_history.append(a_actual)
            self.b_history.append(b_actual)

            # Maintain history depth
            if len(self.a_history) > RECURRENCE_HISTORY_DEPTH:
                self.a_history.pop(0)
                self.b_history.pop(0)

        return scalars

    def validate_projection(self, a, b, expected_magnitude):
        """
        Validate tensor projection preservation (Axiom 11).

        Args:
            a: First channel value
            b: Second channel value
            expected_magnitude: Expected magnitude T(n)

        Returns:
            bool: True if projection is valid
        """
        actual_magnitude = np.sqrt(a**2 + b**2)
        error = abs(actual_magnitude - abs(expected_magnitude)) / (abs(expected_magnitude) + 1e-9)

        return error < 0.01  # 1% tolerance
