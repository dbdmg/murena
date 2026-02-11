
# ============================================================================
# CONFIGURAZIONE USE CASES
# ============================================================================

USE_CASE_CONFIGS = {
    "studentato": {
        "superficie_range": (300, 800),
        "prezzo_mq_range": (1200, 2200),
        "piano_range": (0, 5),
        "locali_range": (10, 30),
        "poi_categories": ["università", "mensa", "biblioteca", "supermercato", "trasporti"],
        "poi_max_distance": 2000,
        "required_features": ["internet", "riscaldamento", "ascensore"],
        "preferred_typologies": ["Ufficio strutturato ed assimilabili", "Abitazione", "Struttura residenziale collettiva (es.: collegi e convitti, educandati, ricoveri, orfanotrofi, ospizi, conventi, seminari)"],
        "ape_classes": ["A", "B", "C"],
        "test_queries": [
            "Cerca un'abitazione tra i 2500 e i 3000 m2 da riconvertire in studentato. L'abitazione deve essere vicino alla linea della Metropolitana."
            "Cerca un edificio dismesso vicino a Palazzo Nuovo con superficie totale di 500 m² per farne uno studentato strutturato a micro alloggi di circa 40-60 m² ciascuno. Preferirei un edificio con classe energetica alta per ridurre i costi di gestione.",
            "Cerco immobile zona Crocetta, superficie 400-600 m², da convertire in studentato. Vicinanza Politecnico essenziale, accesso mezzi pubblici entro 300m. Budget contenuto, anche classe energetica C accettabile.",
            "Edificio abbandonato zona Centro, minimo 350 m², per studentato universitario. Deve avere almeno 8-10 locali per creare micro appartamenti. Presenza trasporti pubblici e supermercati nel raggio di 500m.",
            "Cerco stabile dismesso zona Aurora, superficie 450-700 m², per residenza studentesca. Priorità: vicinanza università (max 1.5km), buona connessione internet, possibilità installazione ascensore.",
            "Immobile inutilizzato zona San Salvario, circa 550 m², da riqualificare per alloggi studenti. Essenziale: piano terra o basso per accessibilità, vicinanza mense universitarie, classe energetica B o superiore."
        ]
    },
    "asilo_nido": {
        "superficie_range": (250, 500),
        "prezzo_mq_range": (1200, 2000),
        "piano_range": (0, 2),
        "locali_range": (8, 15),
        "poi_categories": ["parco", "ospedale", "farmacia", "supermercato", "trasporti"],
        "poi_max_distance": 500,
        "required_features": ["giardino", "accesso_disabili", "sicurezza"],
        "preferred_typologies": ["Abitazione", "Edificio scolastico (es.: scuola di ogni ordine e grado, università, scuola di formazione)", "Locale commerciale, negozio"],
        "ape_classes": ["A", "B"],
        "test_queries": [
            "Cerca un edificio abbandonato in zona residenziale, possibilmente con spazio esterno, da riconvertire in asilo nido per 30-40 bambini. Superficie indicativa 350 m². Vicinanza a parchi e servizi sanitari fondamentale. Classe energetica minima B per sostenibilità gestionale.",
            "Immobile dismesso zona Crocetta, 300-450 m², per asilo nido 0-3 anni. Indispensabile: giardino privato minimo 100 m², piano terra, vicinanza ospedale pediatrico entro 800m. Classe A preferibile.",
            "Cerco ex scuola o edificio pubblico zona Lingotto, superficie 280-400 m², da convertire in asilo nido. Requisiti: spazi esterni sicuri, accessibilità totale, parcheggio nelle vicinanze, farmacie entro 300m.",
            "Edificio abbandonato Centro storico, circa 320 m², per nido comunale. Essenziale: locali ampi e luminosi, possibilità adattamento normativa sicurezza bambini, parco pubblico raggiungibile a piedi.",
            "Stabile inutilizzato zona San Salvario, 350-480 m², per asilo nido aziendale. Priorità: ottima classe energetica (A), accesso disabili, vicinanza supermercati per logistica, trasporti pubblici."
        ]
    },
    "micronido": {
        "superficie_range": (120, 250),
        "prezzo_mq_range": (1300, 2100),
        "piano_range": (0, 1),
        "locali_range": (4, 8),
        "poi_categories": ["parco", "farmacia", "supermercato", "trasporti"],
        "poi_max_distance": 400,
        "required_features": ["giardino", "accesso_disabili"],
        "preferred_typologies": ["Abitazione", "Locale commerciale, negozio"],
        "ape_classes": ["A", "B", "C"],
        "test_queries": [
            "Cerca un immobile dismesso adatto per micronido (max 12 bambini) in zona residenziale tranquilla. Superficie circa 150-180 m², preferibilmente con piccolo giardino o terrazzo. Vicinanza a parchi verde e collegamenti mezzi pubblici importante.",
            "Piccolo edificio abbandonato zona Aurora, 130-200 m², per micronido familiare. Requisiti: piano terra, spazio esterno anche piccolo, zona tranquilla lontano da traffico. Budget limitato, classe C accettabile.",
            "Ex negozio o piccolo ufficio zona Crocetta, circa 160 m², da convertire in micronido. Necessario: accesso autonomo, possibilità ristrutturazione interna, vicinanza fermata bus, farmacia nel raggio 400m.",
            "Immobile dismesso Centro, 140-190 m², per micronido privato. Essenziale: locali tutti allo stesso piano, illuminazione naturale ottima, piccolo cortile o terrazzo per giochi all'aperto.",
            "Cerco appartamento o locale commerciale inutilizzato zona Lingotto, 170-220 m², per micronido aziendale. Priorità: accessibilità auto per genitori, parcheggio vicino, struttura già a norma o facilmente adattabile."
        ]
    },
    "centro_anziani": {
        "superficie_range": (300, 600),
        "prezzo_mq_range": (1000, 1800),
        "piano_range": (0, 2),
        "locali_range": (10, 20),
        "poi_categories": ["ospedale", "farmacia", "parco", "supermercato", "trasporti"],
        "poi_max_distance": 800,
        "required_features": ["ascensore", "accesso_disabili", "sicurezza"],
        "preferred_typologies": ["Abitazione", "Ufficio strutturato ed assimilabili"],
        "ape_classes": ["B", "C"],
        "test_queries": [
            "Cerca un edificio pubblico dismesso da riconvertire in centro diurno per anziani. Superficie minima 400 m² con possibilità di sale attività, ambulatorio e mensa. Essenziale presenza ascensore e accessibilità totale. Vicinanza presidi sanitari e farmacie entro 500m.",
            "Ex ambulatorio o ufficio pubblico zona Crocetta, 350-550 m², per centro diurno anziani. Requisiti critici: ascensore funzionante, accessibilità carrozzine, farmacia entro 300m, ospedale entro 1km.",
            "Immobile dismesso zona Lingotto, superficie 420-580 m², per centro servizi terza età. Necessario: ampi spazi comuni, cucina attrezzabile per mensa, bagni accessibili, parcheggio limitrofo.",
            "Cerco ex scuola o centro civico abbandonato zona San Salvario, minimo 450 m², per centro diurno. Priorità: piano unico o max 2 piani con ascensore, giardino o terrazzo, vicinanza parco pubblico.",
            "Edificio pubblico inutilizzato Centro storico, 380-500 m², da riqualificare per anziani. Essenziale: ottima accessibilità trasporti pubblici, servizi sanitari nel raggio 600m, classe energetica B minimo per comfort."
        ]
    },
    "centro_incontro": {
        "superficie_range": (200, 400),
        "prezzo_mq_range": (1100, 2000),
        "piano_range": (0, 3),
        "locali_range": (6, 12),
        "poi_categories": ["trasporti", "parcheggio", "supermercato"],
        "poi_max_distance": 1000,
        "required_features": ["accesso_disabili", "parcheggio"],
        "preferred_typologies": ["Abitazione", "Locale commerciale, negozio", "Palazzo storico, castello", "Ufficio strutturato ed assimilabili"],
        "ape_classes": ["B", "C", "D"],
        "test_queries": [
            "Cerca un edificio abbandonato da valorizzare come centro di aggregazione sociale e culturale. Superficie circa 250-300 m² con spazi flessibili per attività multiple. Buoni collegamenti trasporti pubblici e possibilità parcheggio nelle vicinanze. Preferibile zona centrale o semi-centrale.",
            "Ex circolo o biblioteca dismessa zona Aurora, 220-350 m², per centro culturale di quartiere. Requisiti: spazi modulabili, accesso disabili, fermata bus/tram entro 200m. Classe energetica non prioritaria.",
            "Immobile commerciale abbandonato zona Crocetta, 280-400 m², per centro incontro giovanile. Necessario: ampia sala principale, possibilità suddivisione spazi, parcheggio auto nelle vicinanze.",
            "Cerco ex cinema o teatro dismesso Centro storico, superficie 300-450 m², per spazio culturale polifunzionale. Priorità: visibilità e accessibilità ottima, collegamenti trasporti pubblici eccellenti.",
            "Edificio pubblico inutilizzato zona Lingotto, 260-380 m², per centro aggregazione sociale. Essenziale: spazi flessibili adattabili a eventi, attività ricreative, corsi. Parcheggio e supermercato entro 500m."
        ]
    }
}


POI_TEMPLATES = {
    "università": [
        {"name": "Politecnico di Torino", "lat": 45.0628, "lon": 7.6621},
        {"name": "Università di Torino", "lat": 45.0703, "lon": 7.6869},
        {"name": "Campus Luigi Einaudi", "lat": 45.0736, "lon": 7.6603},
    ],
    "ospedale": [
        {"name": "Ospedale Molinette", "lat": 45.0344, "lon": 7.6635},
        {"name": "Ospedale San Giovanni Bosco", "lat": 45.0833, "lon": 7.7058},
    ],
    "parco": [
        {"name": "Parco del Valentino", "lat": 45.0547, "lon": 7.6861},
        {"name": "Parco della Pellerina", "lat": 45.0886, "lon": 7.6364},
    ],
    "mensa": [
        {"name": "Mensa Universitaria", "lat": 45.0705, "lon": 7.6870},
        {"name": "Mensa Politecnico", "lat": 45.0630, "lon": 7.6625},
    ],
    "biblioteca": [
        {"name": "Biblioteca Nazionale", "lat": 45.0706, "lon": 7.6919},
    ],
    "farmacia": [
        {"name": "Farmacia Comunale 1", "lat": 45.0650, "lon": 7.6700},
    ],
    "supermercato": [
        {"name": "Carrefour", "lat": 45.0656, "lon": 7.6789},
        {"name": "Esselunga", "lat": 45.0756, "lon": 7.6689},
    ],
    "trasporti": [
        {"name": "Stazione Porta Nuova", "lat": 45.0614, "lon": 7.6781},
        {"name": "Stazione Porta Susa", "lat": 45.0706, "lon": 7.6661},
    ],
    "parcheggio": [
        {"name": "Parcheggio Valentino", "lat": 45.0560, "lon": 7.6850},
    ],
}


TIPOLOGIE = ["ufficio", "residenziale", "commerciale", "scolastico", "culturale", "sanitario"]


ZONE_TORINO = [
    {"name": "Centro", "lat_center": 45.0703, "lon_center": 7.6869},
    {"name": "Crocetta", "lat_center": 45.0547, "lon_center": 7.6861},
    {"name": "San Salvario", "lat_center": 45.0519, "lon_center": 7.6747},
    {"name": "Lingotto", "lat_center": 45.0297, "lon_center": 7.6650},
    {"name": "Aurora", "lat_center": 45.0833, "lon_center": 7.6922},
]


# Agenti disponibili per ablation
AVAILABLE_AGENTS = [
    "location_agent",
    "typology_agent",
    "poi_agent",
    "ape_agent",
    "normative_agent",
    "ranking_agent",
    "sql_agent",
    "evaluation_agent"
]
