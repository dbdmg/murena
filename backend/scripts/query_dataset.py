
import sys
import os
import pandas as pd
import json
from pathlib import Path

# Aggiungi la root del progetto al sys.path per importare i moduli interni
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.services.analysis.executor import execute_sql_query
from app.core.config import settings
from app.data.loaders import load_and_merge_data

# Query SQL da testare (modifica questa stringa per cambiare test)
DEFAULT_SQL_QUERY = """
SELECT
  *
FROM IMMOBILI
WHERE
  superficie_di_riferimento_mq BETWEEN 2500 AND 3000
  AND tipologia_bene_immobile = 'Abitazione'
ORDER BY
  id ASC
"""

def main():
    # Usa la variabile hardcoded se non viene passata una query da riga di comando
    sql_query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SQL_QUERY
    # Risolvi il path del dataset in modo assoluto per evitare problemi di CWD
    dataset_path = settings.DATASET_FULL
    if not os.path.isabs(dataset_path):
        dataset_path = str(backend_root / dataset_path)
    
    print(f"Esecuzione query: {sql_query}")
    print(f"Dataset (Path): {dataset_path}")
    
    # Carichiamo i dati come fallback se il caricamento nativo di DuckDB dovesse fallire
    # o se il file non viene trovato direttamente dall'executor
    print("Caricamento dati...")
    df_base = load_and_merge_data(dataset_path)
    
    if df_base is None or df_base.empty:
        print("Errore: Impossibile caricare il dataset.")
        return

    df_result, error = execute_sql_query(
        sql_query=sql_query,
        pd_data=df_base, 
        dataset_path=dataset_path
    )
    
    if error:
        print(f"Errore: {error}")
    else:
        print(f"Risultati trovati (count): {len(df_result)}")

if __name__ == "__main__":
    main()
