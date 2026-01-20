"""
Data module - Loading and processing functions.
"""

from app.data.processors import (
    calculate_travel_times_df,
    extract_ape_image_b64,
    parse_ape_xml,
    process_population_data,
)

from .loaders import (
    get_coordinates,
    load_and_merge_data,
    load_geojson_data,
    load_static_data,
    read_xml_text_safe,
)

__all__ = [
    # Loaders
    "load_and_merge_data",
    "get_coordinates",
    "load_geojson_data",
    "load_static_data",
    "read_xml_text_safe",
    # Processors
    "process_population_data",
    "calculate_travel_times_df",
    "parse_ape_xml",
    "extract_ape_image_b64",
]
