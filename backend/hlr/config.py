"""
backend/hlr/config.py
Configuration parameters for Half-Life Regression.
Pure Python, standard library only.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class HLRConfig:
    """Configuration for HLR prediction, bounding, and review policies.
    
    ASSUMPTION: Default bounding values reflect Settles & Meeder (2016) spacing
    dynamics where minimum review horizon is 15 minutes (15/1440 days) and
    maximum half-life is capped at 270 days (~9 months).
    """
    h_min_days: float = 15.0 / 1440.0
    h_max_days: float = 270.0
    p_min: float = 0.0001
    p_max: float = 0.9999
    review_threshold: float = 0.70
    default_model: str = "hlr_v0_fixed"
