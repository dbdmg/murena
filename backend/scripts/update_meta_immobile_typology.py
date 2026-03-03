import pandas as pd
import ast
from typing import Any, Dict, List, Optional
import sys
import os
import numpy as np

def update_meta_immobile_typology(file_path: str) -> None:
    """
    updates the 'tipologia_bene_immobile' for meta-immobili in a parquet file.
    
    the typology of a meta-immobile is determined by the typology that represents 
    the highest percentage of the total surface area of its associated properties.
    """
    if not os.path.exists(file_path):
        print(f"error: file not found at {file_path}")
        return

    print(f"reading parquet file: {file_path}")
    df = pd.read_parquet(file_path)

    # create a lookup dictionary for property data.
    # we drop duplicate ids to ensure the index is unique for to_dict('index').
    print("preparing property lookup table...")
    property_lookup: Dict[Any, Dict[str, Any]] = (
        df.drop_duplicates(subset=['id'])
        .set_index('id')[['tipologia_bene_immobile', 'superficie_di_riferimento_mq']]
        .to_dict('index')
    )

    def calculate_dominant_typology(row: pd.Series) -> str:
        """
        calculates the dominant typology based on associated ids and their surfaces.
        """
        if not row['meta_immobile']:
            return str(row['tipologia_bene_immobile'])

        raw_id_list = row['id_list']
        if pd.isna(raw_id_list) or not str(raw_id_list).strip():
            return str(row['tipologia_bene_immobile'])

        try:
            # handle various id_list formats
            if isinstance(raw_id_list, str):
                # clean potential string noise
                cleaned_id_list = raw_id_list.strip()
                if cleaned_id_list.startswith('[') and cleaned_id_list.endswith(']'):
                    associated_ids: List[Any] = ast.literal_eval(cleaned_id_list)
                else:
                    # check if comma separated
                    associated_ids = [s.strip() for s in cleaned_id_list.split(',') if s.strip()]
            elif isinstance(raw_id_list, (list, np.ndarray)):
                associated_ids = list(raw_id_list)
            else:
                return str(row['tipologia_bene_immobile'])
            
            if not isinstance(associated_ids, list):
                return str(row['tipologia_bene_immobile'])

            # aggregate surface area by typology
            typology_surfaces: Dict[str, float] = {}
            for child_id in associated_ids:
                # lookup with type normalization
                child_data = property_lookup.get(child_id)
                if not child_data:
                    # common case: int in list vs str in index or vice-versa
                    if isinstance(child_id, str) and child_id.isdigit():
                        child_data = property_lookup.get(int(child_id))
                    elif isinstance(child_id, (int, float)):
                        child_data = property_lookup.get(str(int(child_id)))

                if child_data:
                    typology = str(child_data['tipologia_bene_immobile'])
                    surface = child_data['superficie_di_riferimento_mq']
                    
                    try:
                        surface_val = float(surface) if pd.notna(surface) else 0.0
                    except (ValueError, TypeError):
                        surface_val = 0.0
                        
                    typology_surfaces[typology] = typology_surfaces.get(typology, 0.0) + surface_val

            if not typology_surfaces:
                return str(row['tipologia_bene_immobile'])

            # find the typology with the max total surface area
            dominant_typology = max(typology_surfaces, key=lambda k: typology_surfaces[k])
            return dominant_typology

        except (ValueError, SyntaxError, TypeError):
            return str(row['tipologia_bene_immobile'])

    print("calculating new typologies for meta-immobili...")
    # keep a copy of original values for logging
    original_values = df['tipologia_bene_immobile'].copy()
    
    # apply transformation
    df['tipologia_bene_immobile'] = df.apply(calculate_dominant_typology, axis=1)

    # identify modified rows
    # note: we compare as strings to avoid issues with potential None/NaN mismatch
    mask = df['tipologia_bene_immobile'].astype(str) != original_values.astype(str)
    modified_rows = df[mask].copy()
    
    if not modified_rows.empty:
        modified_rows['original_tipologia'] = original_values[mask]
        log_file = file_path.replace(".parquet", "_modifications.csv")
        
        # save only relevant columns for the log
        log_columns = ['id', 'original_tipologia', 'tipologia_bene_immobile']
        modified_rows[log_columns].to_csv(log_file, index=False)
        print(f"logged {len(modified_rows)} modified rows to: {log_file}")
    else:
        print("no rows were modified.")

    output_file = file_path.replace(".parquet", "_updated.parquet")
    print(f"saving updated data to: {output_file}")
    df.to_parquet(output_file, index=False)
    print("update completed successfully")

if __name__ == "__main__":
    target_file = "/Users/marcodeluca/Downloads/real-estate-ai/backend/data/FOLDER_META/immobili_with_meta_and_ape_full_cleaned.parquet"
    update_meta_immobile_typology(target_file)
