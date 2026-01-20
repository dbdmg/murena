"""
Utility helper functions for text processing, distance calculations, and graph creation.

This module handles:
- String slugification for file/folder names
- Haversine distance calculation
- Metro network graph creation
- Coordinate extraction from LLM responses
"""

import os
import re

import networkx as nx
import numpy as np
import pandas as pd
import unidecode

# Import get_coordinates inside functions to avoid circular import


def slugify(text):
    """
    Crea una stringa sicura per i nomi di file/cartelle da un testo.

    Args:
        text: Input text to slugify

    Returns:
        str: Safe string for filenames
    """
    text = unidecode.unidecode(text).lower()
    return re.sub(r"[\W_]+", "_", text).strip("_")


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two points on Earth using Haversine formula.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        float: Distance in kilometers
    """
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(
        np.radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
    )
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


def extract_geo_coordinates(response):
    """
    Extract geographic coordinates from LLM response.

    Args:
        response: LLM response string with location names separated by semicolons

    Returns:
        list: List of [name, lat, lon] for each location, or "NESSUN LUOGO"
    """
    from app.data.loaders import (
        get_coordinates,
    )  # Local import to avoid circular dependency

    locations = response.split(";")
    coordinates = []
    for loc in locations:
        loc = loc.strip()
        if "NESSUN LUOGO" not in loc.upper() and loc:
            lat, lon = get_coordinates(loc)
            if lat and lon:
                coordinates.append([loc, lat, lon])
    return coordinates if coordinates else "NESSUN LUOGO"


def create_graph_metro(folder_linee="data/FOLDER_STATIC_ROME/Linee"):
    """
    Create NetworkX graph from metro line CSV files.

    Args:
        folder_linee: Folder containing metro line CSV files

    Returns:
        nx.Graph: Metro network graph with stations as nodes
    """
    G = nx.Graph()

    if not os.path.exists(folder_linee):
        print(f"La cartella '{folder_linee}' non esiste.")
        return G

    for file in os.listdir(folder_linee):
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(folder_linee, file))
            for i, row in df.iterrows():
                if G.has_node(row["Nome"]):
                    if row["Linea"] not in G.nodes[row["Nome"]]["Linea"]:
                        G.nodes[row["Nome"]]["Linea"] += f", {row['Linea']}"
                else:
                    G.add_node(row["Nome"], **row.to_dict())
                if i > 0:
                    G.add_edge(df.iloc[i - 1]["Nome"], row["Nome"])
    return G
