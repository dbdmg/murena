from app.core.constants import update_runtime_metadata
from app.utils.logger import logger

class MetadataManager:
    """
    Gestisce l'aggiornamento dei metadati a runtime. 
    Ora centralizzato in memoria (app.core.constants.DB_METADATA) 
    invece di utilizzare file JSON.
    """
    
    def __init__(self, metadata_path: str = None, lite_metadata_path: str = None):
        # Percorsi mantenuti per compatibilità costruttore ma non più usati per scrittura
        pass

    def update_metadata(self, df):
        """Aggiorna i metadati in memoria basandosi sul dataframe attuale."""
        if df is None or df.empty:
            logger.warning("MetadataManager: DataFrame vuoto o nullo, salto aggiornamento.")
            return

        try:
            logger.info("Aggiornamento dinamico dei metadati in memoria...")
            update_runtime_metadata(df)
            logger.info("Metadati in memoria aggiornati con successo.")
        except Exception as e:
            logger.error(f"Errore durante l'aggiornamento dei metadati: {e}")
