from app.core.constants import update_runtime_metadata
from app.utils.logger import logger

class MetadataManager:
    """
    Manages runtime metadata updates.
    Metadata is centralized in memory (app.core.constants.DB_METADATA)
    instead of being written to JSON files.
    """
    
    def __init__(self, metadata_path: str = None, lite_metadata_path: str = None):
        # Percorsi mantenuti per compatibilità costruttore ma non più usati per scrittura
        pass

    def update_metadata(self, df):
        """Update in-memory metadata from the current DataFrame."""
        if df is None or df.empty:
            logger.warning("MetadataManager: DataFrame is empty or null; skipping update.")
            return

        try:
            logger.info("Updating in-memory metadata...")
            update_runtime_metadata(df)
            logger.info("In-memory metadata updated successfully.")
        except Exception as e:
            logger.error(f"Error updating metadata: {e}")
