#!/usr/bin/env python
"""
Script per aggiornare gli score APE nel dataset immobili.

Questo script:
1. Carica il dataset APE con gli score già calcolati (scala 1-5)
2. Carica il dataset immobili
3. Per ogni immobile, cerca i file APE corrispondenti
4. Aggrega gli score (MODA per classe energetica, MEDIA per punti radar)
5. Aggiorna il dataset immobili con i nuovi score

Aggregazione Multi-APE:
- Classe Energetica Globale: MODA (valore più frequente)
- Punteggio Radar Globale: MEDIA aritmetica dei punti grezzi (scala 6-20)
- I singoli score radar sono la MEDIA dei rispettivi punteggi

Usage:
    python update_immobili_ape_scores.py                    # Aggiorna il dataset
    python update_immobili_ape_scores.py --dry-run          # Mostra cosa farebbe senza salvare
    python update_immobili_ape_scores.py --output PATH      # Salva in un file diverso
"""

import sys
import argparse
from pathlib import Path
from collections import Counter
from typing import Optional, Tuple, List, Dict

# Add backend to path
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd
import numpy as np

# Default paths
DEFAULT_APE_PATH = BACKEND_DIR / "data" / "FOLDER_META" / "ape_detailed_data.parquet"
DEFAULT_IMMOBILI_PATH = (
    BACKEND_DIR / "data" / "FOLDER_META" / "immobili_with_meta_and_ape_full_cleaned.parquet"
)


def normalize_filename(filename: str) -> str:
    """Normalizza il nome file APE per il matching."""
    if not filename:
        return ""
    # Rimuovi estensione se presente
    name = str(filename).strip()
    if name.lower().endswith(".xml"):
        name = name[:-4]
    return name.lower()


def extract_ape_files_list(val) -> List[str]:
    """Estrai lista di file APE da vari formati (stringa, tupla, lista)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    
    if isinstance(val, (list, tuple)):
        return [str(f).strip() for f in val if f and str(f).strip()]
    
    if isinstance(val, str):
        # Potrebbe essere una stringa rappresentante una tupla/lista
        val = val.strip()
        if val.startswith("(") and val.endswith(")"):
            # Parse tuple string: "('file1.xml', 'file2.xml')"
            val = val[1:-1]
        if val.startswith("[") and val.endswith("]"):
            val = val[1:-1]
        
        # Split by comma
        parts = [p.strip().strip("'\"") for p in val.split(",")]
        return [p for p in parts if p]
    
    return []


def aggregate_ape_scores(
    ape_records: List[Dict],
) -> Tuple[Optional[str], Dict[str, float]]:
    """
    Aggrega gli score di più APE per lo stesso immobile.
    
    Args:
        ape_records: Lista di dizionari con i dati APE
        
    Returns:
        Tuple: (classe_energetica_globale, dict_scores)
        - classe_energetica_globale: MODA delle classi energetiche
        - dict_scores: dizionario con le MEDIE degli score radar
    """
    if not ape_records:
        return None, {}
    
    # Raccogli le classi energetiche
    classi = [r.get("classe") for r in ape_records if r.get("classe")]
    
    # Calcola MODA per classe energetica
    classe_globale = None
    if classi:
        counter = Counter(classi)
        # In caso di pareggio, prendi la classe migliore (ordine: A4>A3>A2>A1>B>C>D>E>F>G)
        classe_order = ["A4", "A3", "A2", "A1", "A", "B", "C", "D", "E", "F", "G"]
        most_common = counter.most_common()
        if most_common:
            max_count = most_common[0][1]
            tied_classes = [c for c, count in most_common if count == max_count]
            # Ordina per qualità e prendi la migliore
            for c in classe_order:
                if c in tied_classes:
                    classe_globale = c
                    break
            if classe_globale is None:
                classe_globale = tied_classes[0]
    
    # Calcola MEDIA per gli score radar
    scores_keys = [
        ("ape_class_score", "ape_score_classe"),
        ("ape_system_score", "ape_score_impianto"),
        ("ape_envelope_score", "ape_score_involucro"),
        ("ape_renewables_score", "ape_score_rinnovabili"),
        ("ape_total_points", "ape_score_total"),
    ]
    
    aggregated_scores = {}
    for src_key, dest_key in scores_keys:
        values = [r.get(src_key) for r in ape_records if r.get(src_key) is not None]
        if values:
            # Converti in float e calcola media
            numeric_values = [float(v) for v in values if not pd.isna(v)]
            if numeric_values:
                aggregated_scores[dest_key] = np.mean(numeric_values)
    
    return classe_globale, aggregated_scores


def update_immobili_scores(
    ape_path: Optional[Path] = None,
    immobili_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, int, int]:
    """
    Aggiorna gli score APE nel dataset immobili.
    
    Args:
        ape_path: Path al dataset APE dettagliato
        immobili_path: Path al dataset immobili
        output_path: Path per l'output (default: sovrascrive immobili_path)
        dry_run: Se True, mostra cosa farebbe senza salvare
        
    Returns:
        Tuple: (totale_immobili, immobili_con_ape, immobili_aggiornati)
    """
    ape_path = ape_path or DEFAULT_APE_PATH
    immobili_path = immobili_path or DEFAULT_IMMOBILI_PATH
    output_path = output_path or immobili_path
    
    print(f"Caricamento dataset APE da {ape_path}...")
    df_ape = pd.read_parquet(ape_path)
    print(f"  Caricati {len(df_ape)} record APE")
    
    # Crea dizionario APE indicizzato per nome file normalizzato
    ape_by_file = {}
    for _, row in df_ape.iterrows():
        filename = normalize_filename(row.get("file", ""))
        if filename:
            ape_by_file[filename] = row.to_dict()
    print(f"  Indicizzati {len(ape_by_file)} file APE unici")
    
    print(f"\nCaricamento dataset immobili da {immobili_path}...")
    df_imm = pd.read_parquet(immobili_path)
    print(f"  Caricati {len(df_imm)} immobili")
    
    # Colonne per i file APE - prova varie possibilità
    ape_list_cols = [
        "list_file_ape_validated_norm",
        "list_file_ape_validated", 
        "list_file_ape_filtered",
        "lista_file_ape",
    ]
    
    ape_list_col = None
    for col in ape_list_cols:
        if col in df_imm.columns:
            ape_list_col = col
            break
    
    if not ape_list_col:
        print("ERRORE: Nessuna colonna con lista file APE trovata!")
        return 0, 0, 0
    
    print(f"  Usando colonna: {ape_list_col}")
    
    # Inizializza colonne score se non esistono
    score_cols = [
        "ape_score_classe",
        "ape_score_impianto", 
        "ape_score_involucro",
        "ape_score_rinnovabili",
        "ape_score_total",
    ]
    
    for col in score_cols:
        if col not in df_imm.columns:
            df_imm[col] = np.nan
    
    # Contatori
    total = len(df_imm)
    with_ape = 0
    updated = 0
    multi_ape_count = 0
    
    print("\nAggiornamento score immobili...")
    
    for idx, row in df_imm.iterrows():
        # Estrai lista file APE
        ape_files = extract_ape_files_list(row.get(ape_list_col))
        
        if not ape_files:
            continue
        
        with_ape += 1
        
        if len(ape_files) > 1:
            multi_ape_count += 1
        
        # Trova i record APE corrispondenti
        matched_apes = []
        for fname in ape_files:
            normalized = normalize_filename(fname)
            if normalized in ape_by_file:
                matched_apes.append(ape_by_file[normalized])
            # Prova anche senza estensione
            elif normalized.replace(".xml", "") in ape_by_file:
                matched_apes.append(ape_by_file[normalized.replace(".xml", "")])
        
        if not matched_apes:
            continue
        
        # Aggrega gli score
        classe_globale, scores = aggregate_ape_scores(matched_apes)
        
        if scores:
            updated += 1
            
            # Aggiorna i valori
            if classe_globale:
                df_imm.at[idx, "classe_energetica_ape"] = classe_globale
            
            for col, val in scores.items():
                df_imm.at[idx, col] = val
    
    print(f"\n📊 Statistiche:")
    print(f"  Totale immobili: {total}")
    print(f"  Immobili con APE: {with_ape}")
    print(f"  Immobili con multi-APE: {multi_ape_count}")
    print(f"  Immobili aggiornati: {updated}")
    
    # Mostra distribuuzione score
    valid_scores = df_imm[df_imm["ape_score_total"].notna()]["ape_score_total"]
    if len(valid_scores) > 0:
        print(f"\n📈 Distribuzione score totale:")
        print(f"  Min: {valid_scores.min():.1f}")
        print(f"  Max: {valid_scores.max():.1f}")
        print(f"  Media: {valid_scores.mean():.1f}")
        print(f"  Mediana: {valid_scores.median():.1f}")
    
    if dry_run:
        print("\n⚠️  DRY RUN: Nessun file salvato")
    else:
        print(f"\n💾 Salvataggio in {output_path}...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            df_imm.to_parquet(output_path, index=False, engine="pyarrow")
        except Exception as e:
            print(f"Warning: pyarrow fallito ({e}), provo engine default...")
            df_imm.to_parquet(output_path, index=False)
        print(f"✅ Salvati {len(df_imm)} record")
    
    return total, with_ape, updated


def main():
    parser = argparse.ArgumentParser(
        description="Aggiorna gli score APE nel dataset immobili"
    )
    parser.add_argument(
        "--ape-file",
        type=Path,
        default=DEFAULT_APE_PATH,
        help=f"Path al dataset APE (default: {DEFAULT_APE_PATH})",
    )
    parser.add_argument(
        "--immobili-file",
        type=Path,
        default=DEFAULT_IMMOBILI_PATH,
        help=f"Path al dataset immobili (default: {DEFAULT_IMMOBILI_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path output (default: sovrascrive il file immobili)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra cosa farebbe senza salvare",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Aggiornamento Score APE nel Dataset Immobili")
    print("=" * 60)
    print(f"\nLogica di aggregazione Multi-APE:")
    print(f"  • Classe Energetica: MODA (valore più frequente)")
    print(f"  • Score Radar: MEDIA aritmetica (scala 1-5 per categoria)")
    print(f"  • Totale Punti: MEDIA aritmetica (scala 6-20)")
    print()
    
    update_immobili_scores(
        ape_path=args.ape_file,
        immobili_path=args.immobili_file,
        output_path=args.output,
        dry_run=args.dry_run,
    )
    
    print("\nDone!")


if __name__ == "__main__":
    main()
