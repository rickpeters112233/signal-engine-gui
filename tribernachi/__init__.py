"""
Tribernachi Package
Contains Tribernachi Geometric Compression (TGC) and T-Hex Versioning Code (TVC) modules
Based on Tribernachi Theory V4.02
"""

from .constants import (
    V_T,
    PHI,
    GAMMA,
    BETA,
    EPSILON,
    ZETA,
    T_HEX_ALPHABET,
    T_HEX_BASE,
    TVC_VERSION,
    QUANTIZATION_LEVELS,
    RECURRENCE_HISTORY_DEPTH
)

from .tensor_recurrence import TensorRecurrence

from .tvc_versioning import (
    int_to_base20,
    base20_to_int,
    generate_tvc,
    parse_tvc,
    generate_cache_key,
    parse_cache_key
)

from .tgc_encoder import TGCEncoder

__all__ = [
    # Constants
    'V_T',
    'PHI',
    'GAMMA',
    'BETA',
    'EPSILON',
    'ZETA',
    'T_HEX_ALPHABET',
    'T_HEX_BASE',
    'TVC_VERSION',
    'QUANTIZATION_LEVELS',
    'RECURRENCE_HISTORY_DEPTH',

    # Tensor Recurrence
    'TensorRecurrence',

    # TVC Versioning
    'int_to_base20',
    'base20_to_int',
    'generate_tvc',
    'parse_tvc',
    'generate_cache_key',
    'parse_cache_key',

    # TGC Encoder
    'TGCEncoder'
]
