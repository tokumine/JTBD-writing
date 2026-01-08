"""Company database for grounding prompts in reality."""
import json
import random
from pathlib import Path

from src.prompts.schemas import Company


class CompanyDatabase:
    """Load and sample real companies for prompt grounding."""

    # Fallback companies when no external file is provided
    DEFAULT_COMPANIES: list[dict] = [
        # Tech Giants
        {"name": "Apple Inc.", "naics_code": "334111", "naics_sector": "31", "size": "enterprise", "employee_count": 164000, "industry_description": "Computer and Electronic Product Manufacturing", "hq_location": "Cupertino, CA", "is_public": True},
        {"name": "Microsoft Corporation", "naics_code": "511210", "naics_sector": "51", "size": "enterprise", "employee_count": 221000, "industry_description": "Software Publishers", "hq_location": "Redmond, WA", "is_public": True},
        {"name": "Google LLC", "naics_code": "519130", "naics_sector": "51", "size": "enterprise", "employee_count": 182000, "industry_description": "Internet Publishing and Broadcasting", "hq_location": "Mountain View, CA", "is_public": True},
        {"name": "Amazon.com Inc.", "naics_code": "454110", "naics_sector": "44", "size": "enterprise", "employee_count": 1500000, "industry_description": "Electronic Shopping and Mail-Order Houses", "hq_location": "Seattle, WA", "is_public": True},
        # Finance
        {"name": "JPMorgan Chase & Co.", "naics_code": "522110", "naics_sector": "52", "size": "enterprise", "employee_count": 293000, "industry_description": "Commercial Banking", "hq_location": "New York, NY", "is_public": True},
        {"name": "Goldman Sachs Group Inc.", "naics_code": "523110", "naics_sector": "52", "size": "large", "employee_count": 45000, "industry_description": "Investment Banking", "hq_location": "New York, NY", "is_public": True},
        # Healthcare
        {"name": "UnitedHealth Group", "naics_code": "524114", "naics_sector": "52", "size": "enterprise", "employee_count": 400000, "industry_description": "Health Insurance Carriers", "hq_location": "Minnetonka, MN", "is_public": True},
        {"name": "Mayo Clinic", "naics_code": "622110", "naics_sector": "62", "size": "large", "employee_count": 76000, "industry_description": "General Medical and Surgical Hospitals", "hq_location": "Rochester, MN", "is_public": False},
        # Manufacturing
        {"name": "General Motors Company", "naics_code": "336111", "naics_sector": "31", "size": "enterprise", "employee_count": 157000, "industry_description": "Automobile Manufacturing", "hq_location": "Detroit, MI", "is_public": True},
        {"name": "Boeing Company", "naics_code": "336411", "naics_sector": "31", "size": "enterprise", "employee_count": 142000, "industry_description": "Aircraft Manufacturing", "hq_location": "Arlington, VA", "is_public": True},
        # Retail
        {"name": "Walmart Inc.", "naics_code": "452311", "naics_sector": "44", "size": "enterprise", "employee_count": 2100000, "industry_description": "Warehouse Clubs and Supercenters", "hq_location": "Bentonville, AR", "is_public": True},
        {"name": "Target Corporation", "naics_code": "452210", "naics_sector": "44", "size": "enterprise", "employee_count": 440000, "industry_description": "Department Stores", "hq_location": "Minneapolis, MN", "is_public": True},
        # Professional Services
        {"name": "Deloitte LLP", "naics_code": "541211", "naics_sector": "54", "size": "enterprise", "employee_count": 415000, "industry_description": "Offices of Certified Public Accountants", "hq_location": "New York, NY", "is_public": False},
        {"name": "McKinsey & Company", "naics_code": "541611", "naics_sector": "54", "size": "large", "employee_count": 38000, "industry_description": "Management Consulting Services", "hq_location": "New York, NY", "is_public": False},
        # Education
        {"name": "Harvard University", "naics_code": "611310", "naics_sector": "61", "size": "large", "employee_count": 16000, "industry_description": "Colleges, Universities, and Professional Schools", "hq_location": "Cambridge, MA", "is_public": False},
        # Small/Medium businesses
        {"name": "TechStart Solutions", "naics_code": "541511", "naics_sector": "54", "size": "startup", "employee_count": 25, "industry_description": "Custom Computer Programming Services", "hq_location": "Austin, TX", "is_public": False},
        {"name": "Green Valley Farms", "naics_code": "111998", "naics_sector": "11", "size": "small", "employee_count": 50, "industry_description": "All Other Miscellaneous Crop Farming", "hq_location": "Fresno, CA", "is_public": False},
        {"name": "Metro Construction LLC", "naics_code": "236220", "naics_sector": "23", "size": "medium", "employee_count": 150, "industry_description": "Commercial and Institutional Building Construction", "hq_location": "Chicago, IL", "is_public": False},
        {"name": "Sunrise Senior Care", "naics_code": "623110", "naics_sector": "62", "size": "medium", "employee_count": 200, "industry_description": "Nursing Care Facilities", "hq_location": "Phoenix, AZ", "is_public": False},
        {"name": "Digital Marketing Pros", "naics_code": "541810", "naics_sector": "54", "size": "small", "employee_count": 35, "industry_description": "Advertising Agencies", "hq_location": "San Diego, CA", "is_public": False},
    ]

    def __init__(self, companies_file: Path | None = None):
        """Initialize with optional external companies file."""
        self._companies: list[dict] = self.DEFAULT_COMPANIES.copy()

        if companies_file and companies_file.exists():
            with open(companies_file) as f:
                external = json.load(f)
                if isinstance(external, list):
                    self._companies.extend(external)

        # Build indexes
        self._by_sector: dict[str, list[dict]] = {}
        self._by_size: dict[str, list[dict]] = {}

        for company in self._companies:
            sector = company.get("naics_sector", "54")
            if sector not in self._by_sector:
                self._by_sector[sector] = []
            self._by_sector[sector].append(company)

            size = company.get("size", "medium")
            if size not in self._by_size:
                self._by_size[size] = []
            self._by_size[size].append(company)

    def sample_company(
        self,
        seed: int,
        naics_sector: str | None = None,
        size: str | None = None,
    ) -> Company:
        """
        Sample a company with optional filters.

        Args:
            seed: Random seed for reproducibility
            naics_sector: Filter by NAICS sector
            size: Filter by company size

        Returns:
            Company object
        """
        rng = random.Random(seed)

        # Filter candidates
        candidates = self._companies

        if naics_sector and naics_sector in self._by_sector:
            candidates = self._by_sector[naics_sector]
        elif size and size in self._by_size:
            candidates = self._by_size[size]

        if not candidates:
            candidates = self._companies

        company_data = rng.choice(candidates)

        return Company(
            name=company_data["name"],
            naics_code=company_data.get("naics_code", "541511"),
            naics_sector=company_data.get("naics_sector", "54"),
            size=company_data.get("size", "medium"),
            employee_count=company_data.get("employee_count"),
            industry_description=company_data.get("industry_description", "Professional Services"),
            hq_location=company_data.get("hq_location"),
            is_public=company_data.get("is_public", False),
        )

    def get_companies_by_sector(self, naics_sector: str) -> list[Company]:
        """Get all companies in a sector."""
        return [
            Company(**c) for c in self._by_sector.get(naics_sector, [])
        ]

    def get_company_count(self) -> int:
        """Get total number of companies."""
        return len(self._companies)
