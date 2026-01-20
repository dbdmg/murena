"""
LLM integration module - prepared for LangChain migration.
Currently uses Gemini API directly, will be refactored to use LangChain.
"""

# from .client import gemini_response
# from .prompts import (
#     generate_prompt_location,
#     generate_prompt_sql,
#     generate_prompt_sql_retry,
#     generate_evaluation_prompt,
#     generate_use_case_from_query,
# )

__all__ = [
    "gemini_response",
    "generate_prompt_location",
    "generate_prompt_sql",
    "generate_prompt_sql_retry",
    "generate_evaluation_prompt",
    "generate_use_case_from_query",
]
