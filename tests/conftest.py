"""Pytest configuration and fixtures."""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set test environment variables."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key-12345")
    monkeypatch.setenv("EVAL_LOG_LEVEL", "DEBUG")


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_onet_task_data() -> dict:
    """Sample O*NET task data for testing."""
    return {
        "task_id": "T1234",
        "onetsoc_code": "11-1011.00",
        "task": "Write quarterly reports for stakeholders",
        "task_type": "Core",
        "occupation_title": "Chief Executives",
        "occupation_description": "Top executives in organizations",
        "job_zone": 5,
        "soc_major_group": "11",
        "writing_relevance_score": 0.95,
        "inferred_category": "reports",
        "inferred_channel": "report",
    }


@pytest.fixture
def sample_persona_data() -> dict:
    """Sample persona data for testing."""
    return {
        "id": "persona_001",
        "job_title": "Senior Marketing Manager",
        "experience_level": "senior",
        "age_group": "millennial",
        "communication_style": "professional",
        "industry_background": "Technology",
        "education_level": "MBA",
        "years_experience": 12,
    }


@pytest.fixture
def sample_company_data() -> dict:
    """Sample company data for testing."""
    return {
        "name": "Acme Corporation",
        "naics_code": "541511",
        "naics_sector": "54",
        "size": "large",
        "employee_count": 5000,
        "industry_description": "Computer Systems Design Services",
        "hq_location": "San Francisco, CA",
        "is_public": True,
    }


@pytest.fixture
def sample_person_name_data() -> dict:
    """Sample person name data for testing."""
    return {
        "first": "Sarah",
        "last": "Chen",
        "full": "Sarah Chen",
        "email": "sarah.chen@acme.com",
        "demographic": "asian",
        "gender": "female",
        "formality_variants": {
            "formal": "Ms. Chen",
            "casual": "Sarah",
            "full": "Sarah T. Chen",
        },
    }
