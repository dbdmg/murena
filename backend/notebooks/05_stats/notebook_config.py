# Configurazione percorsi per il notebook analisi_poi_studentati_torino

# Percorso al file dei POI
POIS_PATH = '../01_pois/pois_by_category.json'

def get_config(use_case):
    config = {
        'studentati': {
            'data_path': 'studentati.csv',
            'output_path': 'analisi_poi_studentati_torino.csv'
        },
        'ospizi': {
            'data_path': 'ospizi.csv',
            'output_path': 'analisi_poi_ospizi_torino.csv'
        }
    }
    return config[use_case]