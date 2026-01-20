"""
Formatting utility functions for SQL queries and other data.

This module handles:
- SQL query formatting and cleaning
- Image MIME type guessing
"""

import sqlparse


def format_sql_query(sql_query):
    """
    Format SQL query by removing markdown code blocks and beautifying.

    Args:
        sql_query: Raw SQL query string (may contain markdown)

    Returns:
        str: Formatted SQL query
    """
    if "```sql" in sql_query:
        sql_query = sql_query.split("```sql")[1].split("```")[0]
    return sqlparse.format(sql_query.strip(), reindent=True, keyword_case="upper")
