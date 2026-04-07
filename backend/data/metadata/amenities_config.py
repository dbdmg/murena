# Configuration for POI categories and amenities
CATEGORIES = [
    'commercial',
    'education',
    'mobility',
    'healthcare',
    'sport',
    'green'
]

# Mapping of OSM tags to categories and amenities
# (category, [(tag_key, tag_value), ...])
CATEGORY_AMENITIES = {
    'commercial': [
        ('shop', '*'),
        ('amenity', 'marketplace'),
        ('amenity', 'restaurant'),
        ('amenity', 'cafe'),
        ('amenity', 'bar'),
        ('amenity', 'fast_food'),
        ('amenity', 'pub'),
        ('amenity', 'bank'),
        ('amenity', 'atm'),
        ('amenity', 'post_office')
    ],
    'education': [
        ('amenity', 'school'),
        ('amenity', 'kindergarten'),
        ('amenity', 'university'),
        ('amenity', 'college'),
        ('amenity', 'music_school'),
        ('amenity', 'driving_school'),
        ('amenity', 'library'),
        ('amenity', 'archive'),
        ('tourism', 'museum'),
        ('amenity', 'community_centre')
    ],
    'mobility': [
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
        ('amenity', 'bicycle_rental')
    ],
    'healthcare': [
        ('healthcare', '*'),
        ('amenity', 'hospital'),
        ('amenity', 'pharmacy'),
        ('amenity', 'dentist'),
        ('amenity', 'doctors'),
        ('amenity', 'clinic'),
        ('amenity', 'veterinary'),
        ('amenity', 'optician'),
        ('emergency', 'defibrillator')
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
        ('leisure', 'climbing_wall')
    ],
    'green': [
        ('leisure', 'park'),
        ('leisure', 'garden'),
        ('landuse', 'grass'),
        ('landuse', 'forest'),
        ('natural', 'wood'),
        ('natural', 'meadow'),
        ('natural', 'scrub'),
        ('landuse', 'allotments'),
        ('leisure', 'playground'),
        ('leisure', 'recreation_ground'),
        ('leisure', 'nature_reserve')
    ]
}
