import sys
import os
import pandas as pd
from pathlib import Path
import argparse
from tabulate import tabulate

# Aggiungi la root del progetto al sys.path per importare i moduli interni
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.services.analysis.executor import execute_sql_query
from app.core.config import settings
from app.data.loaders import load_and_merge_data

def run_query(query: str, limit: int = 15, output: str = None):
    """
    Esegue una query SQL sul dataset degli immobili e stampa i risultati.
    """
    # Risolvi il path del dataset in modo assoluto
    dataset_path = settings.DATASET_FULL
    if not os.path.isabs(dataset_path):
        dataset_path = str(backend_root / dataset_path)
    
    print(f"--- SQL Query Tool ---")
    print(f"Dataset path: {dataset_path}")
    print(f"Esecuzione query: {query}\n")
    
    # Caricamento dati (necessario per DuckDB registration se il caricamento nativo fallisce)
    # load_and_merge_data gestisce già il merge con i dati APE
    df_base = load_and_merge_data(dataset_path)
    
    if df_base is None or df_base.empty:
        print("Errore: Impossibile caricare il dataset.")
        return

    # Esecuzione query tramite l'executor ufficiale del progetto
    df_result, error = execute_sql_query(
        sql_query=query,
        pd_data=df_base, 
        dataset_path=dataset_path
    )
    
    if error:
        print(f"ERRORE SQL: {error}")
        return

    total_results = len(df_result)
    print(f"\n>>> NUMERO DI RIGHE TROVATE: {total_results}")
    
    if total_results == 0:
        print("Nessun risultato trovato per i criteri specificati.")

def main():
    query = """
    SELECT
        *
    FROM
        IMMOBILI
    WHERE
        tipologia_bene_immobile IN (
            'Struttura residenziale collettiva (es.: collegi e convitti, educandati, ricoveri, orfanotrofi, ospizi, conventi, seminari)',
            'Fabbricato per attività produttiva (industriale, artigianale o agricola)'
        )
        AND superficie_di_riferimento_mq >= 3000
        AND HAVERSINE_KM(latitudine, longitudine, 45.0688106, 7.6953675) <= 3.0
        AND mobilita >= 75
        AND classe_energetica_ape IN ('A1', 'A2', 'A4', 'B', 'C', 'D')
    ORDER BY
        HAVERSINE_KM(latitudine, longitudine, 45.0688106, 7.6953675) ASC;
    """
    run_query(query, limit=25)

if __name__ == "__main__":
    main()
