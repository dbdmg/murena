"""
executor.py
===========
Modulo per l'esecuzione dell'analisi live con LLM.

Funzioni principali:
- execute_sql_query(): Esecuzione query SQL con DuckDB
"""

import os
import traceback
from typing import Any, Dict

import duckdb
import pandas as pd

from app.core.config import settings

APE_DETAILED_DATA_PATH = settings.APE_DETAILED_DATA_PATH

# Switch to GraphOrchestratorAgent
from app.services.llm.agents.graph_agent import GraphOrchestratorAgent
from app.utils.helpers import haversine_km


def execute_sql_query(sql_query, pd_data, dataset_path=None):
    """
    Esegue una query SQL su un DataFrame Pandas usando DuckDB.

    Args:
        sql_query (str): La query SQL da eseguire
        pd_data (pd.DataFrame): Il DataFrame su cui eseguire la query
        dataset_path (str, optional): Path al file parquet per caricamento nativo

    Returns:
        tuple: (pd.DataFrame, str|None) Risultato della query e eventuale messaggio di errore
    """
    try:
        with duckdb.connect(database=":memory:") as con:
            con.create_function("haversine_km", haversine_km, return_type="FLOAT")

            # DuckDB Native Loading Optimization
            if dataset_path and dataset_path.endswith(".parquet") and os.path.exists(dataset_path):
                try:
                    # Create view for base data
                    con.execute(f"CREATE VIEW base_immobili AS SELECT * FROM '{dataset_path}'")

                    # Check for APE data and join if available
                    if os.path.exists(APE_DETAILED_DATA_PATH) and APE_DETAILED_DATA_PATH.endswith(
                        ".parquet"
                    ):
                        con.execute(
                            f"CREATE VIEW ape_data AS SELECT * FROM '{APE_DETAILED_DATA_PATH}'"
                        )

                        # Check if 'id' column exists in ape_data
                        ape_cols = [c[0] for c in con.execute("DESCRIBE ape_data").fetchall()]

                        if "id" in ape_cols:
                            # Construct join query to replicate load_and_merge_data logic
                            # We cast ID to VARCHAR to ensure matching works
                            join_query = """
                            CREATE VIEW IMMOBILI AS 
                            SELECT b.*, 
                                   COALESCE(a.ape_score, 0) as ape_score,
                                   COALESCE(a.ape_total_points, 0) as ape_total_points,
                                   COALESCE(a.ape_class_score, 0) as ape_class_score,
                                   COALESCE(a.ape_system_score, 0) as ape_system_score,
                                   COALESCE(a.ape_envelope_score, 0) as ape_envelope_score,
                                   COALESCE(a.ape_renewables_score, 0) as ape_renewables_score
                            FROM base_immobili b
                            LEFT JOIN ape_data a ON CAST(b.id AS VARCHAR) = CAST(a.id AS VARCHAR)
                            """
                            con.execute(join_query)
                        else:
                            # If no ID in APE data, just alias base table (skip join)
                            # This matches the behavior of pandas load_and_merge_data which skips merge if 'id' missing
                            con.execute("CREATE VIEW IMMOBILI AS SELECT * FROM base_immobili")
                    else:
                        # If no APE data, just alias base table
                        con.execute("CREATE VIEW IMMOBILI AS SELECT * FROM base_immobili")

                    return con.execute(sql_query).fetchdf(), None
                except Exception as e:
                    print(f"DuckDB Native Loading failed, falling back to Pandas: {e}")
                    # Fallback to pandas registration below

            con.register("IMMOBILI", pd_data)
            return con.execute(sql_query).fetchdf(), None
    except Exception as e:
        print(f"Errore nell'esecuzione della query SQL: {e}\nQuery: {sql_query}")
        return pd.DataFrame(), str(e)
