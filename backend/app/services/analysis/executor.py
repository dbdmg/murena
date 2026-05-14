"""
executor.py
===========
Module for running live analysis with LLM agents.

Main functions:
- execute_sql_query(): SQL query execution with DuckDB
"""

import os
import traceback
import logging
from typing import Any, Dict

import duckdb
import pandas as pd

from app.core.config import settings


# Switch to GraphOrchestratorAgent
from app.services.llm.agents.graph_agent import GraphOrchestratorAgent
from app.utils.helpers import haversine_km

logger = logging.getLogger(__name__)


def execute_sql_query(sql_query, pd_data, dataset_path=None):
    """
    Executes a SQL query on a Pandas DataFrame using DuckDB.

    Args:
        sql_query (str): The SQL query to execute
        pd_data (pd.DataFrame): The DataFrame to query
        dataset_path (str, optional): Path to the parquet file for native loading

    Returns:
        tuple: (pd.DataFrame, str|None) Query result and optional error message
    """
    try:
        with duckdb.connect(database=":memory:") as con:
            con.create_function("haversine_km", haversine_km, return_type="FLOAT")

            # DuckDB Native Loading Optimization
            if (
                dataset_path
                and dataset_path.endswith(".parquet")
                and os.path.exists(dataset_path)
            ):
                try:
                    # Create view for base data
                    con.execute(
                        f"CREATE VIEW base_properties AS SELECT * FROM '{dataset_path}'"
                    )

                    con.execute("CREATE VIEW PROPERTIES AS SELECT * FROM base_properties")
                    con.execute("CREATE VIEW ESTATES AS SELECT * FROM base_properties")

                    # Pre-check SQL syntax with EXPLAIN
                    sql_query = sql_query.strip().rstrip(';')
                    try:
                        con.execute(f"EXPLAIN {sql_query}")
                    except Exception as syntax_error:
                        return pd.DataFrame(), f"SQL Syntax Error: {str(syntax_error)}"

                    return con.execute(sql_query).fetchdf(), None
                except Exception as e:
                    print(f"DuckDB Native Loading failed, falling back to Pandas: {e}")
                    # Fallback to pandas registration below

            # Check if we have valid data to register
            if pd_data is None or pd_data.empty:
                error_msg = "No valid dataset provided for SQL execution"
                return pd.DataFrame(), error_msg

            con.register("PROPERTIES", pd_data)
            con.register("ESTATES", pd_data)
            
            # Pre-check SQL syntax with EXPLAIN
            sql_query = sql_query.strip().rstrip(';')
            try:
                con.execute(f"EXPLAIN {sql_query}")
            except Exception as syntax_error:
                return pd.DataFrame(), f"SQL Syntax Error: {str(syntax_error)}"

            return con.execute(sql_query).fetchdf(), None
    except Exception as e:
        logger.error(f"Error executing SQL query: {e}\nQuery: {sql_query}")
        return pd.DataFrame(), str(e)
