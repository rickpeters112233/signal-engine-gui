"""
Tribernachi Constants
Mathematical constants used throughout the Tribernachi encoding system
Based on Tribernachi Theory V4.02
"""

import numpy as np

# Geometric Fidelity (Axiom 0) - The fundamental constant
V_T = 0.117851130197758

# Golden Ratio (φ) - Used for radial growth coupling
PHI = 1.618033988749895

# Radial growth coupling coefficient
GAMMA = PHI

# Cross-channel coupling coefficient
BETA = 1.0

# Quadratic damping coefficient (derived from V_T)
EPSILON = V_T * 0.5

# Cubic correction coefficient (derived from V_T)
ZETA = V_T * 0.1

# Expected compression ratio (2-3x over GZIP)
EXPECTED_COMPRESSION_RATIO = 2.5

# T-Hex alphabet for base-20 encoding (20 characters)
T_HEX_ALPHABET = "0123456789ABCDEFGHIJ"

# Base for T-Hex encoding
T_HEX_BASE = 20

# TVC (T-Hex Versioning Code) constants
TVC_VERSION = "4.02"

# TGC (Tribernachi Geometric Compression) quantization parameters
QUANTIZATION_LEVELS = 256
QUANTIZATION_SCALING_FACTOR = V_T

# Recurrence history depth required for accurate decoding
RECURRENCE_HISTORY_DEPTH = 3

# Convergence criteria (Axiom 36)
CONVERGENCE_STEPS = 7
CONVERGENCE_TOLERANCE = 1e-6

# Error detection threshold
ERROR_DETECTION_THRESHOLD = 0.001
