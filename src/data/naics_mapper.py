"""Map SOC codes to NAICS industries."""
import json
import random
from pathlib import Path


class NAICSMapper:
    """Map SOC codes to NAICS industries with complete fallback data."""

    # Complete SOC major group to NAICS sector mapping
    # Probabilities based on BLS Employment by Industry Matrix
    SOC_TO_NAICS_FALLBACK: dict[str, list[tuple[str, float]]] = {
        "11": [("54", 0.22), ("52", 0.15), ("62", 0.12), ("31", 0.10), ("44", 0.08), ("55", 0.08), ("23", 0.06), ("72", 0.05), ("92", 0.05), ("48", 0.04)],  # Management
        "13": [("54", 0.28), ("52", 0.22), ("55", 0.10), ("92", 0.08), ("62", 0.07), ("51", 0.06), ("31", 0.05), ("44", 0.04), ("61", 0.03)],  # Business/Financial
        "15": [("54", 0.32), ("51", 0.22), ("52", 0.10), ("31", 0.08), ("55", 0.06), ("92", 0.05), ("61", 0.04), ("62", 0.03), ("23", 0.03)],  # Computer/Math
        "17": [("54", 0.28), ("23", 0.18), ("31", 0.16), ("22", 0.08), ("92", 0.06), ("51", 0.05), ("48", 0.04), ("21", 0.04), ("55", 0.03)],  # Engineering
        "19": [("54", 0.25), ("61", 0.18), ("62", 0.15), ("92", 0.12), ("31", 0.08), ("51", 0.05), ("55", 0.04), ("21", 0.03), ("11", 0.03)],  # Life/Physical/Social Science
        "21": [("62", 0.32), ("92", 0.25), ("61", 0.12), ("81", 0.08), ("54", 0.06), ("52", 0.05), ("55", 0.03), ("71", 0.03)],  # Community/Social Service
        "23": [("61", 0.45), ("62", 0.15), ("92", 0.12), ("54", 0.08), ("81", 0.06), ("71", 0.04), ("55", 0.03)],  # Legal
        "25": [("61", 0.72), ("92", 0.08), ("62", 0.06), ("81", 0.04), ("71", 0.03), ("54", 0.02)],  # Education
        "27": [("51", 0.28), ("54", 0.18), ("71", 0.15), ("81", 0.10), ("61", 0.07), ("52", 0.05), ("44", 0.04), ("31", 0.03)],  # Arts/Design/Entertainment
        "29": [("62", 0.75), ("61", 0.08), ("92", 0.05), ("54", 0.03), ("55", 0.02)],  # Healthcare Practitioners
        "31": [("62", 0.55), ("72", 0.12), ("61", 0.10), ("81", 0.06), ("71", 0.05), ("44", 0.04)],  # Healthcare Support
        "33": [("92", 0.48), ("56", 0.15), ("61", 0.08), ("81", 0.06), ("48", 0.05), ("71", 0.04), ("52", 0.04)],  # Protective Service
        "35": [("72", 0.50), ("62", 0.12), ("61", 0.10), ("71", 0.08), ("44", 0.06), ("81", 0.04), ("92", 0.03)],  # Food Preparation
        "37": [("56", 0.25), ("81", 0.18), ("72", 0.12), ("62", 0.10), ("61", 0.08), ("92", 0.06), ("44", 0.05), ("53", 0.04)],  # Building/Grounds
        "39": [("81", 0.25), ("62", 0.20), ("72", 0.15), ("71", 0.12), ("61", 0.08), ("44", 0.06), ("52", 0.04)],  # Personal Care
        "41": [("44", 0.40), ("42", 0.18), ("52", 0.10), ("54", 0.08), ("31", 0.06), ("51", 0.04), ("72", 0.04)],  # Sales
        "43": [("62", 0.18), ("52", 0.15), ("54", 0.12), ("92", 0.10), ("56", 0.08), ("61", 0.06), ("44", 0.06), ("31", 0.05), ("51", 0.05)],  # Office/Admin
        "45": [("11", 0.60), ("21", 0.15), ("81", 0.08), ("92", 0.05), ("54", 0.04)],  # Farming/Fishing/Forestry
        "47": [("23", 0.55), ("56", 0.12), ("31", 0.08), ("22", 0.06), ("48", 0.05), ("81", 0.04)],  # Construction
        "49": [("44", 0.20), ("31", 0.18), ("48", 0.15), ("81", 0.12), ("23", 0.08), ("56", 0.06), ("42", 0.05)],  # Installation/Maintenance
        "51": [("31", 0.55), ("42", 0.12), ("44", 0.08), ("23", 0.06), ("22", 0.04), ("48", 0.04)],  # Production
        "53": [("48", 0.35), ("42", 0.18), ("44", 0.12), ("56", 0.08), ("31", 0.06), ("23", 0.05), ("81", 0.04)],  # Transportation
    }

    NAICS_SECTORS: dict[str, str] = {
        "11": "Agriculture, Forestry, Fishing and Hunting",
        "21": "Mining, Quarrying, and Oil and Gas Extraction",
        "22": "Utilities",
        "23": "Construction",
        "31": "Manufacturing",
        "42": "Wholesale Trade",
        "44": "Retail Trade",
        "48": "Transportation and Warehousing",
        "51": "Information",
        "52": "Finance and Insurance",
        "53": "Real Estate and Rental and Leasing",
        "54": "Professional, Scientific, and Technical Services",
        "55": "Management of Companies and Enterprises",
        "56": "Administrative and Support Services",
        "61": "Educational Services",
        "62": "Health Care and Social Assistance",
        "71": "Arts, Entertainment, and Recreation",
        "72": "Accommodation and Food Services",
        "81": "Other Services (except Public Administration)",
        "92": "Public Administration",
    }

    def __init__(self, crosswalk_path: Path | None = None):
        """Initialize with optional external crosswalk data."""
        self._external_crosswalk: dict | None = None
        if crosswalk_path and crosswalk_path.exists():
            with open(crosswalk_path) as f:
                self._external_crosswalk = json.load(f)

    def sample_industry(
        self,
        soc_code: str,
        seed: int,
        exclude: set[str] | None = None,
    ) -> tuple[str, str]:
        """
        Sample an industry for an occupation.

        Args:
            soc_code: Full O*NET SOC code (e.g., "11-1011.00")
            seed: Random seed for reproducibility
            exclude: NAICS sectors to exclude

        Returns:
            Tuple of (naics_sector, industry_name)
        """
        rng = random.Random(seed)
        soc_major = soc_code[:2]
        exclude = exclude or set()

        # Try external crosswalk first
        if self._external_crosswalk and soc_major in self._external_crosswalk:
            weights = self._external_crosswalk[soc_major]
        elif soc_major in self.SOC_TO_NAICS_FALLBACK:
            weights = self.SOC_TO_NAICS_FALLBACK[soc_major]
        else:
            # Ultimate fallback: uniform distribution
            all_sectors = list(self.NAICS_SECTORS.keys())
            sector = rng.choice([s for s in all_sectors if s not in exclude])
            return sector, self.NAICS_SECTORS[sector]

        # Filter and normalize weights
        filtered = [(s, w) for s, w in weights if s not in exclude]
        if not filtered:
            # All options excluded, use any available
            sector = rng.choice(list(self.NAICS_SECTORS.keys()))
            return sector, self.NAICS_SECTORS.get(sector, "Unknown")

        total = sum(w for _, w in filtered)
        normalized = [(s, w / total) for s, w in filtered]

        # Weighted random selection
        r = rng.random()
        cumulative = 0.0
        for sector, weight in normalized:
            cumulative += weight
            if r <= cumulative:
                return sector, self.NAICS_SECTORS.get(sector, "Unknown")

        # Fallback to last option
        sector = normalized[-1][0]
        return sector, self.NAICS_SECTORS.get(sector, "Unknown")

    def get_all_sectors(self) -> dict[str, str]:
        """Get all NAICS sectors."""
        return self.NAICS_SECTORS.copy()

    def get_sector_name(self, naics_code: str) -> str:
        """Get sector name for a NAICS code."""
        return self.NAICS_SECTORS.get(naics_code, "Unknown")
