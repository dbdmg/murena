"""
Energy Score Calculator

Calculates energy efficiency scores based on APE data using percentile-based normalization.

Process:
1. Calculate kWh/m²/year for each APE certificate
2. Group by usage type (destinazione_uso_cod)
3. Build Gaussian distribution per group
4. Calculate percentiles → normalized score (0-100)

Lower kWh/m²/year = better efficiency = higher score
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Energy cost coefficients (€/unit) from COSTI_ENERGETICI
ENERGY_COSTS = {
    "energia_elettrica": 0.25,  # €/kWh
    "gas_naturale": 0.87,  # €/Smc
    "gpl": 1.63,  # €/L
    "gasolio": 1.70,  # €/L
    "teleriscaldamento": 0.09,  # €/kWh
    "solare_eolico": 0.00,  # €/kWh (free)
    "default": 0.25,  # Default to electricity rate
}

# Usage type labels
USAGE_TYPE_LABELS = {
    0: "Residenziale",
    1: "Uffici/Commerciale",
}

# Default electricity cost for kWh-based calculations
DEFAULT_KWH_COST = 0.25  # €/kWh


class EnergyScoreCalculator:
    """
    Calculates energy efficiency scores using percentile-based normalization.
    """

    def __init__(self, ape_data_path: Optional[Path] = None):
        """
        Initialize the calculator with APE data.

        Args:
            ape_data_path: Path to the APE parquet file. If None, uses default.
        """
        self.ape_data_path = (
            ape_data_path
            or Path(__file__).parent.parent.parent
            / "data"
            / "FOLDER_META"
            / "ape_detailed_data.parquet"
        )
        self._distributions: Dict[float, Dict[str, float]] = {}
        self._global_distribution: Dict[str, float] = {}
        self._scores_df: Optional[pd.DataFrame] = None
        self._loaded = False

    def load_and_compute(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Load APE data and compute all scores.

        Args:
            df: Optional DataFrame to use. If None, loads from self.ape_data_path.

        Returns:
            DataFrame with computed scores.
        """
        if self._loaded and self._scores_df is not None and df is None:
            return self._scores_df

        if df is None:
            logger.info(f"Loading APE data from {self.ape_data_path}")
            try:
                if not self.ape_data_path.exists():
                    logger.error(f"APE data file not found at {self.ape_data_path}")
                    self._scores_df = pd.DataFrame()
                    self._loaded = True
                    return self._scores_df
                df = pd.read_parquet(self.ape_data_path)
            except Exception as e:
                logger.error(f"Failed to load APE data: {e}")
                self._scores_df = pd.DataFrame()
                self._loaded = True
                return self._scores_df
        else:
            df = df.copy()

        try:
            # Calculate kWh per square meter
            if "consumo_kwh_tot" in df.columns and "superficie" in df.columns:
                df["kwh_per_sqm"] = pd.to_numeric(df["consumo_kwh_tot"], errors='coerce') / pd.to_numeric(df["superficie"], errors='coerce')
            else:
                logger.warning("APE data missing required columns")
                return df

            # Remove invalid values for distribution building
            valid_df = df[
                df["kwh_per_sqm"].notna()
                & (df["kwh_per_sqm"] > 0)
                & (df["kwh_per_sqm"] < 1000)
            ].copy()

            # Build distributions per usage type
            self._distributions = {}
            if "destinazione_uso_cod" in valid_df.columns:
                for usage_type in valid_df["destinazione_uso_cod"].dropna().unique():
                    subset = valid_df[valid_df["destinazione_uso_cod"] == usage_type]["kwh_per_sqm"]
                    if len(subset) >= 10:
                        self._distributions[usage_type] = {
                            "mean": subset.mean(),
                            "std": subset.std(),
                            "count": len(subset),
                        }

            # Global distribution as fallback
            all_values = valid_df["kwh_per_sqm"].dropna()
            self._global_distribution = {
                "mean": all_values.mean(),
                "std": all_values.std(),
                "count": len(all_values),
            }

            # Calculate scores for all rows
            df["energy_score"] = df.apply(self._compute_score_for_row, axis=1)

            # Calculate estimated annual cost (€/year)
            df["estimated_cost_year"] = pd.to_numeric(df["consumo_kwh_tot"], errors='coerce') * DEFAULT_KWH_COST

            # Calculate cost per sqm (€/m²/year)
            df["cost_per_sqm_year"] = df["kwh_per_sqm"] * DEFAULT_KWH_COST

            if df is None: # Only cache if we loaded from file
                self._scores_df = df
                self._loaded = True

            return df

        except Exception as e:
            logger.error(f"Failed to compute APE scores: {e}")
            return df

    def _compute_score_for_row(self, row: pd.Series) -> int:
        """Compute score for a single row."""
        kwh_per_sqm = row.get("kwh_per_sqm")
        usage_type = row.get("destinazione_uso_cod")

        if pd.isna(kwh_per_sqm) or kwh_per_sqm <= 0:
            return 0

        return self.get_score(kwh_per_sqm, usage_type)

    def get_score(self, kwh_per_sqm: float, usage_type: Optional[float] = None) -> int:
        """
        Get energy efficiency score for a building.

        Args:
            kwh_per_sqm: Energy consumption in kWh/m²/year
            usage_type: Building usage type code (0=residential, 1=commercial)

        Returns:
            Score from 0-100 (higher = more efficient)
        """
        # Select the right distribution
        if usage_type is not None and usage_type in self._distributions:
            dist = self._distributions[usage_type]
        else:
            dist = self._global_distribution

        if not dist or dist["std"] == 0:
            return 50  # Fallback to median

        # Calculate z-score
        z_score = (kwh_per_sqm - dist["mean"]) / dist["std"]

        # Convert to percentile (inverted: lower consumption = higher score)
        # norm.cdf gives probability that value is <= z
        # We want lower consumption to have higher score
        percentile = 1 - stats.norm.cdf(z_score)

        # Convert to 0-100 and clamp
        score = int(percentile * 100)
        return max(0, min(100, score))

    def get_score_details(
        self, kwh_per_sqm: float, superficie: float, usage_type: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get detailed energy cost analysis for a building.

        Args:
            kwh_per_sqm: Energy consumption in kWh/m²/year
            superficie: Surface area in m²
            usage_type: Building usage type code

        Returns:
            Dictionary with detailed analysis
        """
        score = self.get_score(kwh_per_sqm, usage_type)

        # Calculate costs
        total_kwh = kwh_per_sqm * superficie
        annual_cost = total_kwh * DEFAULT_KWH_COST

        # Get comparison stats
        if usage_type is not None and usage_type in self._distributions:
            dist = self._distributions[usage_type]
            usage_label = USAGE_TYPE_LABELS.get(
                int(usage_type), f"Tipo {int(usage_type)}"
            )
        else:
            dist = self._global_distribution
            usage_label = "Media generale"

        return {
            "ape_score": score,
            "kwh_per_sqm": round(kwh_per_sqm, 1),
            "consumo_kwh_anno": round(total_kwh, 0),
            "costo_annuo_euro": round(annual_cost, 2),
            "costo_per_mq_anno": round(kwh_per_sqm * DEFAULT_KWH_COST, 2),
            "confronto": {
                "tipo_uso": usage_label,
                "media_kwh_mq": round(dist["mean"], 1) if dist else None,
                "differenza_percentuale": (
                    round(((kwh_per_sqm - dist["mean"]) / dist["mean"]) * 100, 1)
                    if dist and dist["mean"] > 0
                    else None
                ),
            },
        }

    def get_score_for_ape(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Get energy score details for a specific APE file.

        Args:
            filename: APE filename

        Returns:
            Score details or None if not found
        """
        if self._scores_df is None:
            self.load_and_compute()

        if self._scores_df is None:
            return None

        row = self._scores_df[self._scores_df["file"] == filename]
        if row.empty:
            return None

        row = row.iloc[0]

        kwh_per_sqm = row.get("kwh_per_sqm")
        superficie = row.get("superficie")
        usage_type = row.get("destinazione_uso_cod")

        if pd.isna(kwh_per_sqm) or pd.isna(superficie):
            return None

        details = self.get_score_details(kwh_per_sqm, superficie, usage_type)

        # Add class comparison
        classe = row.get("classe")
        if classe:
            details["classe_energetica"] = classe

        return details

    def save_scores(self, output_path: Optional[Path] = None) -> Path:
        """
        Save computed scores to a new parquet file.

        Args:
            output_path: Output path. If None, saves alongside original file.

        Returns:
            Path to saved file
        """
        if self._scores_df is None:
            self.load_and_compute()

        if output_path is None:
            output_path = self.ape_data_path.parent / "ape_with_scores.parquet"

        self._scores_df.to_parquet(output_path, index=False)
        logger.info(f"Saved scores to {output_path}")

        return output_path


# Singleton instance
_calculator: Optional[EnergyScoreCalculator] = None


def get_energy_calculator() -> EnergyScoreCalculator:
    """Get or create the energy score calculator singleton."""
    global _calculator
    if _calculator is None:
        _calculator = EnergyScoreCalculator()
        _calculator.load_and_compute()
    return _calculator


def calculate_energy_score(
    kwh_per_sqm: float, usage_type: Optional[float] = None
) -> int:
    """
    Convenience function to get energy score.

    Args:
        kwh_per_sqm: Energy consumption in kWh/m²/year
        usage_type: Building usage type code

    Returns:
        Score from 0-100
    """
    return get_energy_calculator().get_score(kwh_per_sqm, usage_type)


def get_ape_score_details(filename: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get APE score details.

    Args:
        filename: APE filename

    Returns:
        Score details or None
    """
    return get_energy_calculator().get_score_for_ape(filename)
