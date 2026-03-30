import pandas as pd
import numpy as np
from typing import List, Union, Any

def calculate_continuous_score(
    series: pd.Series, 
    target: Union[float, int], 
    operator: str = ">=", 
    exclusive: bool = False
) -> pd.Series:
    """
    Calculates a score between 0 and 100 for continuous variables using 50/100 logic.
    
    Rules for '>=' (Minimum required):
    - Value = Target: 50 points
    - Value = 2 * Target: 100 points
    - Value < Target: 0 points (if exclusive or op == '>')
    
    Rules for '<=' (Maximum required):
    - Value = Target: 50 points
    - Value = Target / 2: 100 points
    - Value > Target: 0 points (if exclusive or op == '<')
    
    Args:
        series: Pandas series of numerical values.
        target: Reference value searched by the user.
        operator: Comparison operator (>=, >, <=, <).
        exclusive: If True, the limit is categorical (under/over threshold = 0).
        
    Returns:
        pd.Series: Calculated scores limited to [0, 100].
    """
    if target is None:
        return pd.Series(0.0, index=series.index)
    
    # Ensure values are numerical
    vals = pd.to_numeric(series, errors="coerce").fillna(0)
    T = float(target)
    
    op = str(operator).upper()
    
    if op in [">=", ">"]:
        if T > 0:
            # Formula: (value / T * 50) -> at T gives 50, at 2T gives 100
            score = (vals / T * 50).clip(0, 100)
            
            # Exclusivity / operator rigor handling
            if op == ">" or exclusive:
                score = score.mask(vals <= T, 0.0)
            else: # >=
                score = score.mask(vals < T, 0.0)
        else:
            # If target is 0, any value >= 0 is a perfect match (100)
            score = pd.Series(100.0, index=series.index)
            if op == ">":
                score = score.mask(vals <= 0, 0.0)
            
    elif op in ["<=", "<"]:
        if T > 0:
            # Formula: 150 - (value / T * 100) -> at T gives 50, at T/2 gives 100
            score = (150 - (vals / T * 100)).clip(0, 100)
            
            # Exclusivity handling
            if op == "<" or exclusive:
                score = score.mask(vals >= T, 0.0)
            else: # <=
                score = score.mask(vals > T, 0.0)
        else:
            # If target is 0, only values <= 0 (so 0) are valid
            score = (vals <= 0).astype(float) * 100.0
    else:
        # Fallback for equality if not handled otherwise
        score = (vals == T).astype(float) * 100.0
        
    return score.round(1)

def calculate_discrete_score(
    series: pd.Series, 
    preferred_values: List[Any]
) -> pd.Series:
    """
    Calculates a score between 0 and 100 for discrete variables (categorical/ordinal).
    
    Rules:
    - Single choice: Perfect match = 100 points, otherwise 0.
    - Multiple choices (ordered):
        - First choice (Best): 100 points
        - Last choice (Minimum acceptable): 50 points
        - Intermediate: linear scale between 100 and 50.
        
    Args:
        series: Pandas series of values (strings, typologies, energy classes).
        preferred_values: List of accepted values, ordered by decreasing preference.
        
    Returns:
        pd.Series: Calculated scores.
    """
    if not preferred_values:
        return pd.Series(0.0, index=series.index)
    
    # Input cleaning
    vals_clean = series.astype(str).str.lower().str.strip()
    target_list = [str(v).lower().strip().strip("'\"") for v in preferred_values]
    
    n_target = len(target_list)
    mapping = {}
    
    if n_target == 1:
        # Single choice = Perfect match 100
        mapping[target_list[0]] = 100.0
    else:
        for idx, t in enumerate(target_list):
            # Formula: First choice (idx=0) = 100, Last (idx=n-1) = 50
            score = round(100.0 - (idx / (n_target - 1) * 50.0), 1)
            mapping[t] = score
            
    def get_score(v):
        v_str = str(v).lower().strip()
        # Case 1: Exact match in dictionary
        if v_str in mapping:
            return mapping[v_str]
        
        # Case 2: Partial match (if value in DB contains or is contained in one of the targets)
        for t, s in mapping.items():
            if t in v_str or v_str in t:
                return s
        return 0.0

    return vals_clean.apply(get_score)
