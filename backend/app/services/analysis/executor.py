"""
executor.py
===========
Module for running live analysis with LLM agents.

Main functions:
- execute_sql_query(): SQL query execution with DuckDB
"""

import os
import logging

import duckdb
import pandas as pd
import pyarrow.parquet as pq
import sqlglot
from sqlglot import exp
from sqlglot.tokens import TokenType

from app.data.loaders import COMPATIBILITY_ALIASES
from app.utils.helpers import haversine_km

logger = logging.getLogger(__name__)


def _parquet_view_select(dataset_path: str) -> str:
    """Build a DuckDB SELECT that keeps Italian columns and adds English aliases."""
    cols = set(pq.read_schema(dataset_path).names)
    alias_exprs = []
    for source, targets in COMPATIBILITY_ALIASES.items():
        if source not in cols:
            continue
        for target in targets:
            if target not in cols:
                alias_exprs.append(f'"{source}" AS "{target}"')

    safe_path = dataset_path.replace("\\", "/")
    if alias_exprs:
        return (
            f"SELECT *, {', '.join(alias_exprs)} "
            f"FROM read_parquet('{safe_path}')"
        )
    return f"SELECT * FROM read_parquet('{safe_path}')"


_READ_ONLY_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Subquery)
_FORBIDDEN_NODES = tuple(
    node
    for node in (
        getattr(exp, name, None)
        for name in (
            "Insert", "Update", "Delete", "Drop", "Create", "Alter", "Command",
            "Merge", "Copy", "Attach", "Detach", "Pragma", "Set", "Use",
            "Transaction", "Commit", "Rollback", "Install", "Load",
        )
    )
    if isinstance(node, type)
)


def validate_select_sql(sql_query: str) -> str | None:
    """Return an error message unless ``sql_query`` is exactly one read-only query.

    Uses sqlglot (DuckDB dialect): semicolons inside string literals are fine,
    but any additional statement (``SELECT 1; DROP ...``) is rejected, as is
    any statement that is not a SELECT / WITH ... SELECT / set operation.
    """
    if not isinstance(sql_query, str) or not sql_query.strip():
        return "SQL Validation Error: empty query"
    try:
        statements = [s for s in sqlglot.parse(sql_query, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as e:
        # Let DuckDB report genuine syntax errors, but only if the query is a
        # single statement: refuse any ';' token outside literals.
        try:
            tokens = sqlglot.tokenize(sql_query, read="duckdb")
        except Exception:
            return f"SQL Validation Error: unparseable query ({e})"
        semis = [i for i, t in enumerate(tokens) if t.token_type == TokenType.SEMICOLON]
        if any(i != len(tokens) - 1 for i in semis):
            return "SQL Validation Error: multiple statements are not allowed"
        first = tokens[0].token_type if tokens else None
        if first not in (TokenType.SELECT, TokenType.WITH, TokenType.L_PAREN):
            return "SQL Validation Error: only SELECT queries are allowed"
        return None

    if len(statements) != 1:
        return "SQL Validation Error: exactly one SELECT statement is required"
    stmt = statements[0]
    if not isinstance(stmt, _READ_ONLY_ROOTS):
        return f"SQL Validation Error: only SELECT queries are allowed (got {type(stmt).__name__})"
    if _FORBIDDEN_NODES and any(True for _ in stmt.find_all(*_FORBIDDEN_NODES)):
        return "SQL Validation Error: data-modifying or command statements are not allowed"
    return None


def _lock_down(con, allowed_paths=None) -> None:
    """Disable DuckDB file-system / network access for the user query.

    The parquet views read the file lazily at query time, so the dataset file is
    whitelisted through ``allowed_paths`` (DuckDB >= 1.3) *before* external
    access is disabled. Registered pandas DataFrames are unaffected.
    """
    try:
        if allowed_paths:
            quoted = ", ".join("'" + p.replace("'", "''") + "'" for p in allowed_paths)
            con.execute(f"SET allowed_paths = [{quoted}]")
        con.execute("SET enable_external_access = false")
    except Exception as e:  # pragma: no cover - depends on DuckDB version
        logger.warning(f"Could not restrict DuckDB external access: {e}")


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
    validation_error = validate_select_sql(sql_query)
    if validation_error:
        logger.warning(f"{validation_error}\nQuery: {sql_query}")
        return pd.DataFrame(), validation_error

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
                    abs_dataset_path = os.path.abspath(dataset_path).replace("\\", "/")
                    # Create view for base data with English compatibility aliases.
                    con.execute(
                        f"CREATE VIEW base_properties AS {_parquet_view_select(abs_dataset_path)}"
                    )

                    con.execute("CREATE VIEW PROPERTIES AS SELECT * FROM base_properties")
                    con.execute("CREATE VIEW ESTATES AS SELECT * FROM base_properties")
                    con.execute("CREATE VIEW IMMOBILI AS SELECT * FROM base_properties")
                    _lock_down(con, allowed_paths=[abs_dataset_path])

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
            _lock_down(con)

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
