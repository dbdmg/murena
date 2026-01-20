"""
Constants that are specific to the backend API.
These constants are imported from the original app/config.py but only relevant 
for backend operations (not used in frontend).
"""

# ==============================================================================
# APE (Energy Performance Certificate) MAPPINGS
# ==============================================================================

# Mapping for envelope quality codes
MAPPING_QUALITA_INVOLUCRO = {"0": "Sorridente", "1": "Basita/o", "2": "Triste"}

# Mapping for 'tipoImpianto' codes
MAPPING_IMPIANTI = {
    "0": "Caldaia standard",
    "1": "Caldaia a condensazione",
    "2": "Stufa o caminetto",
    "3": "Riscaldamento elettrico",
    **{str(i): "Pompa di calore" for i in range(4, 16)},  # 4-15 are all heat pumps
    "16": "Impianto solare termico",
    "17": "Impianto fotovoltaico",
    "18": "Cogeneratore",
    "19": "Teleriscaldamento",
    "32": "Scalda-acqua a gas",
    "33": "Scalda-acqua a gas",
    "34": "Scalda-acqua a pompa di calore",
    "35": "Scalda-acqua a pompa di calore",
    "36": "Boiler elettrico",
}

# Energy vector XPaths for main energy source calculation
VETTORI_XPATHS = {
    "Energia elettrica da rete": "//ape:prestazioneImpianti/ape:energiaElettricaRete/ape:consumoAnnuo",
    "Gas naturale": "//ape:prestazioneImpianti/ape:gasNaturale/ape:consumoAnnuo",
    "GPL": "//ape:prestazioneImpianti/ape:gpl/ape:consumoAnnuo",
    "Carbone": "//ape:prestazioneImpianti/ape:carbone/ape:consumoAnnuo",
    "Gasolio": "//ape:prestazioneImpianti/ape:gasolio/ape:consumoAnnuo",
    "Olio combustibile": "//ape:prestazioneImpianti/ape:olioCombustibile/ape:consumoAnnuo",
    "Biomasse solide": "//ape:prestazioneImpianti/ape:biomasseSolide/ape:consumoAnnuo",
    "Biomasse liquide": "//ape:prestazioneImpianti/ape:biomasseLiquide/ape:consumoAnnuo",
    "Biomasse gassose": "//ape:prestazioneImpianti/ape:biomasseGassose/ape:consumoAnnuo",
    "Solare fotovoltaico": "//ape:prestazioneImpianti/ape:solareFotovoltaico/ape:consumoAnnuo",
    "Solare termico": "//ape:prestazioneImpianti/ape:solareTermico/ape:consumoAnnuo",
    "Eolico": "//ape:prestazioneImpianti/ape:eolico/ape:consumoAnnuo",
    "Teleriscaldamento": "//ape:prestazioneImpianti/ape:teleriscaldamento/ape:consumoAnnuo",
    "Teleraffrescamento": "//ape:prestazioneImpianti/ape:teleraffrescamento/ape:consumoAnnuo",
}

# PCI (Lower Heating Value) for energy vectors
VETTORI_PCI = {
    "Gas naturale": 9.94,
    "GPL": 12.778,
    "Carbone": 7.917,
    "Gasolio": 11.87,
    "Olio combustibile": 11.75,
    "Biomasse solide": 4.67,
    "Biomasse liquide": 7.5,
    "Biomasse gassose": 6.4,
}

# Metro line colors (for Roma metro data)
METRO_LINE_COLORS = {
    "A": "#FF6B35",
    "B": "#4ECDC4",
    "B1": "#45B7D1",
    "C": "#96CEB4",
    "DEFAULT": "#gray",
}

# Tile layers configuration (for frontend reference, will be moved to frontend later)
TILE_LAYERS = {
    "default": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Tiles © Esri",
    },
    "dark": {
        "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "attribution": "© OpenStreetMap contributors © CARTO",
    },
    "satellite": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Tiles © Esri",
    },
}

# Icon URLs (for frontend reference, will be moved to frontend later)
DEFAULT_BUILDING_ICON_URL = (
    "https://img.icons8.com/?size=100&id=3ZCXMixo1GDb&format=png&color=000000"
)
EVALUATED_BUILDING_ICON_URL = (
    "https://img.icons8.com/?size=100&id=PbzMHs1A73Dy&format=png&color=000000"
)
SELECTED_BUILDING_ICON_URL = (
    "https://img.icons8.com/?size=100&id=h1ACssMxjHCf&format=png&color=000000"
)
LOCATION_ICON_URL = "https://img.icons8.com/?size=100&id=Cl0BYMUbkFMN&format=png&color=000000"
META_BUILDING_ICON_URL = "https://img.icons8.com/?size=100&id=KxXZNaqhRRv8&format=png&color=00C853"
META_SELECTED_BUILDING_ICON_URL = (
    "https://img.icons8.com/?size=100&id=h1ACssMxjHCf&format=png&color=00C853"
)
