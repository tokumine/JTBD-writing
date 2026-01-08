"""Tests for data extraction and generation modules."""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.data.company_database import CompanyDatabase
from src.data.naics_mapper import NAICSMapper
from src.data.name_generator import NameGenerator
from src.data.onet_extractor import ONetExtractor
from src.prompts.schemas import Company, PersonName
from src.validation.onet_schema import ONetSchemaValidator, ValidationResult


@pytest.fixture
def temp_onet_db(temp_dir: Path) -> Path:
    """Create a minimal test O*NET database."""
    db_path = temp_dir / "test_onet.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create required tables
    cursor.execute("""
        CREATE TABLE task_statements (
            task_id TEXT PRIMARY KEY,
            onetsoc_code TEXT,
            task TEXT,
            task_type TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE occupation_data (
            onetsoc_code TEXT PRIMARY KEY,
            title TEXT,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE job_zones (
            onetsoc_code TEXT PRIMARY KEY,
            job_zone INTEGER
        )
    """)

    # Insert test data
    cursor.executemany(
        "INSERT INTO occupation_data VALUES (?, ?, ?)",
        [
            ("11-1011.00", "Chief Executives", "Top executives in organizations"),
            ("13-1111.00", "Management Analysts", "Conduct studies and propose solutions"),
        ],
    )

    cursor.executemany(
        "INSERT INTO job_zones VALUES (?, ?)",
        [
            ("11-1011.00", 5),
            ("13-1111.00", 4),
        ],
    )

    cursor.executemany(
        "INSERT INTO task_statements VALUES (?, ?, ?, ?)",
        [
            ("T1", "11-1011.00", "Write quarterly reports for stakeholders", "Core"),
            ("T2", "11-1011.00", "Draft correspondence for board members", "Core"),
            ("T3", "11-1011.00", "Manage company operations", "Core"),
            ("T4", "13-1111.00", "Document business processes", "Core"),
            ("T5", "13-1111.00", "Email clients about project updates", "Core"),
            ("T6", "13-1111.00", "Analyze data for insights", "Supplemental"),
        ],
    )

    conn.commit()
    conn.close()
    return db_path


class TestONetSchemaValidator:
    """Tests for O*NET schema validation."""

    @pytest.mark.asyncio
    async def test_valid_schema(self, temp_onet_db: Path) -> None:
        """Test validation of valid database."""
        validator = ONetSchemaValidator()
        result = await validator.validate(temp_onet_db)

        assert result.is_valid
        assert len(result.errors) == 0
        assert "task_statements" in result.table_info

    @pytest.mark.asyncio
    async def test_missing_database(self) -> None:
        """Test validation of missing database."""
        validator = ONetSchemaValidator()
        result = await validator.validate(Path("/nonexistent/path.db"))

        assert not result.is_valid
        assert any("not found" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_get_table_stats(self, temp_onet_db: Path) -> None:
        """Test getting table statistics."""
        validator = ONetSchemaValidator()
        stats = await validator.get_table_stats(temp_onet_db)

        assert stats["task_statements"] == 6
        assert stats["occupation_data"] == 2
        assert stats["job_zones"] == 2


class TestONetExtractor:
    """Tests for O*NET task extraction."""

    @pytest.mark.asyncio
    async def test_extract_writing_tasks(self, temp_onet_db: Path) -> None:
        """Test extracting writing-relevant tasks."""
        extractor = ONetExtractor(temp_onet_db)
        tasks = await extractor.extract_writing_tasks(min_relevance=0.5)

        # Should find tasks with writing keywords
        assert len(tasks) >= 3  # Write, Draft, Document, Email
        task_texts = [t.task for t in tasks]
        assert any("write" in t.lower() for t in task_texts)
        assert any("draft" in t.lower() for t in task_texts)

    @pytest.mark.asyncio
    async def test_filter_by_job_zone(self, temp_onet_db: Path) -> None:
        """Test filtering by job zone."""
        extractor = ONetExtractor(temp_onet_db)

        # Only job zone 5 (CEOs)
        tasks = await extractor.extract_writing_tasks(
            min_relevance=0.5,
            job_zones=[5],
        )

        for task in tasks:
            assert task.job_zone == 5

    @pytest.mark.asyncio
    async def test_filter_by_soc_code(self, temp_onet_db: Path) -> None:
        """Test filtering by SOC major code."""
        extractor = ONetExtractor(temp_onet_db)

        # Only management (11-*)
        tasks = await extractor.extract_writing_tasks(
            min_relevance=0.5,
            soc_codes=["11"],
        )

        for task in tasks:
            assert task.soc_major_group == "11"

    @pytest.mark.asyncio
    async def test_limit_results(self, temp_onet_db: Path) -> None:
        """Test limiting number of results."""
        extractor = ONetExtractor(temp_onet_db)
        tasks = await extractor.extract_writing_tasks(
            min_relevance=0.0,  # Low threshold to get more results
            limit=2,
        )

        assert len(tasks) <= 2

    @pytest.mark.asyncio
    async def test_category_inference(self, temp_onet_db: Path) -> None:
        """Test category inference for tasks."""
        extractor = ONetExtractor(temp_onet_db)
        tasks = await extractor.extract_writing_tasks(min_relevance=0.5)

        # Find the email task
        email_task = next((t for t in tasks if "email" in t.task.lower()), None)
        if email_task:
            assert email_task.inferred_channel == "email"

    @pytest.mark.asyncio
    async def test_occupation_count(self, temp_onet_db: Path) -> None:
        """Test getting occupation count."""
        extractor = ONetExtractor(temp_onet_db)
        count = await extractor.get_occupation_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_task_count(self, temp_onet_db: Path) -> None:
        """Test getting task count."""
        extractor = ONetExtractor(temp_onet_db)
        count = await extractor.get_task_count()
        assert count == 6


class TestNAICSMapper:
    """Tests for NAICS industry mapping."""

    def test_sample_industry(self) -> None:
        """Test sampling an industry for an occupation."""
        mapper = NAICSMapper()
        sector, name = mapper.sample_industry("11-1011.00", seed=42)

        assert sector in mapper.NAICS_SECTORS
        assert len(name) > 0

    def test_reproducibility(self) -> None:
        """Test that same seed produces same result."""
        mapper = NAICSMapper()

        result1 = mapper.sample_industry("11-1011.00", seed=42)
        result2 = mapper.sample_industry("11-1011.00", seed=42)

        assert result1 == result2

    def test_different_seeds(self) -> None:
        """Test that different seeds can produce different results."""
        mapper = NAICSMapper()

        results = set()
        for seed in range(100):
            sector, _ = mapper.sample_industry("11-1011.00", seed=seed)
            results.add(sector)

        # Should see some variety with different seeds
        assert len(results) > 1

    def test_exclude_sectors(self) -> None:
        """Test excluding specific sectors."""
        mapper = NAICSMapper()

        exclude = {"54", "52", "62"}  # Exclude most common for management
        sector, _ = mapper.sample_industry("11-1011.00", seed=42, exclude=exclude)

        assert sector not in exclude

    def test_all_soc_majors_covered(self) -> None:
        """Test all SOC major groups have mappings."""
        mapper = NAICSMapper()

        for soc_major in ["11", "13", "15", "17", "19", "21", "23", "25",
                          "27", "29", "31", "33", "35", "37", "39", "41",
                          "43", "45", "47", "49", "51", "53"]:
            sector, name = mapper.sample_industry(f"{soc_major}-1111.00", seed=42)
            assert sector in mapper.NAICS_SECTORS

    def test_get_all_sectors(self) -> None:
        """Test getting all NAICS sectors."""
        mapper = NAICSMapper()
        sectors = mapper.get_all_sectors()

        assert len(sectors) == 20
        assert "54" in sectors
        assert sectors["54"] == "Professional, Scientific, and Technical Services"


class TestNameGenerator:
    """Tests for name generation."""

    def test_generate_name(self) -> None:
        """Test generating a single name."""
        generator = NameGenerator()
        name = generator.generate_name(seed=42)

        assert isinstance(name, PersonName)
        assert len(name.first) > 0
        assert len(name.last) > 0
        assert name.full == f"{name.first} {name.last}"

    def test_reproducibility(self) -> None:
        """Test that same seed produces same name."""
        generator = NameGenerator()

        name1 = generator.generate_name(seed=42)
        name2 = generator.generate_name(seed=42)

        assert name1.full == name2.full

    def test_demographic_constraint(self) -> None:
        """Test generating name with demographic constraint."""
        generator = NameGenerator()
        name = generator.generate_name(seed=42, demographic="asian")

        assert name.demographic == "asian"

    def test_gender_constraint(self) -> None:
        """Test generating name with gender constraint."""
        generator = NameGenerator()
        name = generator.generate_name(seed=42, gender="female")

        assert name.gender == "female"

    def test_age_group_constraint(self) -> None:
        """Test generating name with age group constraint."""
        generator = NameGenerator()
        name = generator.generate_name(seed=42, age_group="gen_z")

        # Name should be from gen_z pool
        assert name.first in generator.GENERATIONAL_NAMES["gen_z"]["male"] + \
               generator.GENERATIONAL_NAMES["gen_z"]["female"]

    def test_email_generation(self) -> None:
        """Test email is generated."""
        generator = NameGenerator()
        name = generator.generate_name(seed=42)

        assert name.email is not None
        assert "@" in name.email
        assert name.first.lower() in name.email or name.last.lower() in name.email

    def test_formality_variants(self) -> None:
        """Test formality variants are generated."""
        generator = NameGenerator()
        name = generator.generate_name(seed=42)

        assert "formal" in name.formality_variants
        assert "casual" in name.formality_variants
        assert name.formality_variants["casual"] == name.first

    def test_generate_batch(self) -> None:
        """Test generating batch of names."""
        generator = NameGenerator()
        names = generator.generate_batch(count=10, seed=42)

        assert len(names) == 10
        assert all(isinstance(n, PersonName) for n in names)

    def test_batch_diversity(self) -> None:
        """Test batch generation ensures diversity."""
        generator = NameGenerator()
        names = generator.generate_batch(count=8, seed=42, ensure_diversity=True)

        demographics = set(n.demographic for n in names)
        genders = set(n.gender for n in names)

        # With 8 names and diversity, should see multiple demographics and genders
        assert len(demographics) > 1
        assert len(genders) == 2


class TestCompanyDatabase:
    """Tests for company database."""

    def test_sample_company(self) -> None:
        """Test sampling a company."""
        db = CompanyDatabase()
        company = db.sample_company(seed=42)

        assert isinstance(company, Company)
        assert len(company.name) > 0
        assert company.naics_sector in NAICSMapper.NAICS_SECTORS

    def test_reproducibility(self) -> None:
        """Test that same seed produces same company."""
        db = CompanyDatabase()

        company1 = db.sample_company(seed=42)
        company2 = db.sample_company(seed=42)

        assert company1.name == company2.name

    def test_filter_by_sector(self) -> None:
        """Test filtering by NAICS sector."""
        db = CompanyDatabase()
        company = db.sample_company(seed=42, naics_sector="52")

        # Should get a finance company
        assert company.naics_sector == "52"

    def test_filter_by_size(self) -> None:
        """Test filtering by company size."""
        db = CompanyDatabase()
        company = db.sample_company(seed=42, size="startup")

        assert company.size == "startup"

    def test_default_companies_exist(self) -> None:
        """Test default companies are loaded."""
        db = CompanyDatabase()
        count = db.get_company_count()

        assert count >= 20  # At least the default companies

    def test_companies_have_required_fields(self) -> None:
        """Test all companies have required fields."""
        db = CompanyDatabase()

        for _ in range(10):
            company = db.sample_company(seed=_)
            assert company.name
            assert company.naics_code
            assert company.naics_sector
            assert company.size in ["startup", "small", "medium", "large", "enterprise"]
            assert company.industry_description
