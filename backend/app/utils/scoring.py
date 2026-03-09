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
    Calcola un punteggio tra 0 e 100 per variabili continue secondo la logica 50/100.
    
    Regole per '>=' (Minimo richiesto):
    - Valore = Target: 50 punti
    - Valore = 2 * Target: 100 punti
    - Valore < Target: 0 punti (se exclusive o op == '>')
    
    Regole per '<=' (Massimo richiesto):
    - Valore = Target: 50 punti
    - Valore = Target / 2: 100 punti
    - Valore > Target: 0 punti (se exclusive o op == '<')
    
    Args:
        series: Serie pandas di valori numerici.
        target: Valore di riferimento cercato dall'utente.
        operator: Operatore di confronto (>=, >, <=, <).
        exclusive: Se True, il limite è categorico (sotto/sopra soglia = 0).
        
    Returns:
        pd.Series: Punteggi calcolati e limitati a [0, 100].
    """
    if target is None:
        return pd.Series(0.0, index=series.index)
    
    # Assicuriamoci che i valori siano numerici
    vals = pd.to_numeric(series, errors="coerce").fillna(0)
    T = float(target)
    
    op = str(operator).upper()
    
    if op in [">=", ">"]:
        if T > 0:
            # Formula: (valore / T * 50) -> a T dà 50, a 2T dà 100
            score = (vals / T * 50).clip(0, 100)
            
            # Gestione esclusività/rigore operatore
            if op == ">" or exclusive:
                score = score.mask(vals <= T, 0.0)
            else: # >=
                score = score.mask(vals < T, 0.0)
        else:
            # Se il target è 0, ogni valore >= 0 è un match perfetto (100)
            score = pd.Series(100.0, index=series.index)
            if op == ">":
                score = score.mask(vals <= 0, 0.0)
            
    elif op in ["<=", "<"]:
        if T > 0:
            # Formula: 150 - (valore / T * 100) -> a T dà 50, a T/2 dà 100
            score = (150 - (vals / T * 100)).clip(0, 100)
            
            # Gestione esclusività
            if op == "<" or exclusive:
                score = score.mask(vals >= T, 0.0)
            else: # <=
                score = score.mask(vals > T, 0.0)
        else:
            # Se il target è 0, solo valori <= 0 (quindi 0) sono validi
            score = (vals <= 0).astype(float) * 100.0
    else:
        # Fallback per uguaglianza se non gestito diversamente
        score = (vals == T).astype(float) * 100.0
        
    return score.round(1)

def calculate_discrete_score(
    series: pd.Series, 
    preferred_values: List[Any]
) -> pd.Series:
    """
    Calcola un punteggio tra 0 e 100 per variabili discrete (categoriche/ordinali).
    
    Regole:
    - Scelta singola: Match perfetto = 100 punti, altrimenti 0.
    - Scelte multiple (ordinate):
        - Prima scelta (Best): 100 punti
        - Ultima scelta (Minimo accettabile): 50 punti
        - Intermedie: scalo lineare tra 100 e 50.
        
    Args:
        series: Serie pandas di valori (stringhe, tipologie, classi energetiche).
        preferred_values: Lista di valori accettati, ordinati per preferenza decrescente.
        
    Returns:
        pd.Series: Punteggi calcolati.
    """
    if not preferred_values:
        return pd.Series(0.0, index=series.index)
        
    # Pulizia input
    vals_clean = series.astype(str).str.lower().str.strip()
    target_list = [str(v).lower().strip().strip("'\"") for v in preferred_values]
    
    n_target = len(target_list)
    mapping = {}
    
    if n_target == 1:
        # Scelta singola = Match perfetto 100
        mapping[target_list[0]] = 100.0
    else:
        for idx, t in enumerate(target_list):
            # Formula: Prima scelta (idx=0) = 100, Ultima (idx=n-1) = 50
            score = round(100.0 - (idx / (n_target - 1) * 50.0), 1)
            mapping[t] = score
            
    def get_score(v):
        v_str = str(v).lower().strip()
        # Case 1: Match esatto nel dizionario
        if v_str in mapping:
            return mapping[v_str]
        
        # Case 2: Match parziale (se il valore nel DB contiene o è contenuto in uno dei target)
        for t, s in mapping.items():
            if t in v_str or v_str in t:
                return s
        return 0.0

    return vals_clean.apply(get_score)
