"""
Configurazione centralizzata delle categorie di amenity per l'analisi urbana.
"""

# Categorie POI standard (con accenti)
CATEGORIES = ['sanità', 'mobilità', 'verde', 'sport', 'commerciale', 'educazione']

# Tutte le categorie sono già con l'accento, non serve più una mappatura
# Manteniamo questa lista per compatibilità con il codice esistente
PROMPT_CATEGORIES = CATEGORIES

CATEGORY_AMENITIES = {
    'sanità': [
        ('healthcare', '*'),
        ('amenity', 'pharmacy'),
        ('amenity', 'dentist'),
        ('amenity', 'veterinary'),
        ('amenity', 'optician'),
        ('shop', 'medical_supply'),
        ('emergency', 'defibrillator'),
        ('amenity', 'hospital'),
        ('amenity', 'clinic'),
        ('amenity', 'doctors')
    ],
    'mobilità': [
        ('railway', 'station'),
        ('railway', 'subway_entrance'),
        ('railway', 'tram_stop'),
        ('highway', 'bus_stop'),
        ('amenity', 'charging_station'),
        ('amenity', 'car_sharing'),
        ('amenity', 'taxi'),
        ('amenity', 'parking'),
        ('amenity', 'car_rental'),
        ('amenity', 'bicycle_parking'),
        ('amenity', 'bicycle_rental'),
        ('highway', 'primary'),
        ('highway', 'secondary')
    ],
    'verde': [
        ('leisure', 'park'),
        ('leisure', 'garden'),
        ('landuse', 'grass'),
        ('natural', 'wood'),
        ('landuse', 'forest'),
        ('natural', 'meadow'),
        ('natural', 'scrub'),
        ('landuse', 'allotments'),
        ('leisure', 'playground'),
        ('leisure', 'recreation_ground'),
        ('leisure', 'nature_reserve'),
        ('natural', 'lake'),
        ('natural', 'reservoir'),
        ('natural', 'park')
    ],
    'sport': [
        ('leisure', 'fitness_centre'),
        ('leisure', 'sports_centre'),
        ('leisure', 'stadium'),
        ('leisure', 'swimming_pool'),
        ('leisure', 'water_park'),
        ('leisure', 'pitch'),
        ('leisure', 'tennis_court'),
        ('leisure', 'golf_course'),
        ('leisure', 'ice_rink'),
        ('leisure', 'bowling_alley'),
        ('leisure', 'climbing_wall'),
        ('amenity', 'gym')
    ],
    'commerciale': [
        ('shop', '*')
    ],
    'educazione': [
        ('amenity', 'school'),
        ('amenity', 'kindergarten'),
        ('amenity', 'university'),
        ('amenity', 'college'),
        ('amenity', 'music_school'),
        ('amenity', 'driving_school'),
        ('amenity', 'research_institute'),
        ('amenity', 'vocational_school'),
        ('amenity', 'library'),
        ('amenity', 'archive'),
        ('tourism', 'museum'),
        ('amenity', 'community_centre')
    ]
}