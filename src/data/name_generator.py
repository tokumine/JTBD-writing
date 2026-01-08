"""Generate demographically diverse names."""
import json
import random
from pathlib import Path

from src.prompts.schemas import PersonName


class NameGenerator:
    """Generate demographically diverse person names."""

    # Fallback name pools when no external file is provided
    DEFAULT_FIRST_NAMES: dict[str, dict[str, list[str]]] = {
        "white": {
            "male": ["James", "Michael", "Robert", "David", "John", "William", "Richard", "Thomas", "Christopher", "Daniel"],
            "female": ["Jennifer", "Sarah", "Jessica", "Ashley", "Amanda", "Emily", "Megan", "Nicole", "Stephanie", "Lauren"],
        },
        "hispanic": {
            "male": ["Carlos", "Miguel", "Jose", "Luis", "Juan", "Antonio", "Francisco", "Diego", "Alejandro", "Rafael"],
            "female": ["Maria", "Sofia", "Isabella", "Gabriela", "Carmen", "Ana", "Rosa", "Elena", "Valentina", "Lucia"],
        },
        "black": {
            "male": ["Marcus", "Darnell", "Terrence", "Andre", "DeShawn", "Malik", "Jamal", "Tyrone", "Xavier", "Brandon"],
            "female": ["Tamika", "Keisha", "Aaliyah", "Destiny", "Imani", "Jasmine", "Brianna", "Shaniqua", "Ebony", "Latoya"],
        },
        "asian": {
            "male": ["Wei", "Jin", "Hiroshi", "Kenji", "Min-jun", "Raj", "Vikram", "Arjun", "Nguyen", "Tran"],
            "female": ["Mei", "Yuki", "Sakura", "Priya", "Ananya", "Lin", "Xia", "Hana", "Mai", "Soo-yeon"],
        },
    }

    DEFAULT_LAST_NAMES: dict[str, list[str]] = {
        "white": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Anderson", "Taylor"],
        "hispanic": ["Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres"],
        "black": ["Jackson", "Washington", "Jefferson", "Robinson", "Harris", "Lewis", "Walker", "Green", "Carter", "Mitchell"],
        "asian": ["Chen", "Wang", "Kim", "Nguyen", "Patel", "Singh", "Li", "Lee", "Park", "Tanaka"],
    }

    GENERATIONAL_NAMES: dict[str, dict[str, list[str]]] = {
        "boomer": {
            "male": ["Robert", "William", "Richard", "Donald", "Gary", "Ronald", "Kenneth", "Steven", "Larry", "Dennis"],
            "female": ["Linda", "Barbara", "Patricia", "Susan", "Carol", "Nancy", "Deborah", "Sandra", "Karen", "Donna"],
        },
        "gen_x": {
            "male": ["Michael", "Christopher", "Jason", "David", "James", "Matthew", "Brian", "Jeffrey", "Eric", "Kevin"],
            "female": ["Jennifer", "Lisa", "Michelle", "Amy", "Angela", "Melissa", "Kimberly", "Stephanie", "Nicole", "Heather"],
        },
        "millennial": {
            "male": ["Joshua", "Matthew", "Andrew", "Daniel", "Christopher", "Michael", "Ryan", "Tyler", "Brandon", "Justin"],
            "female": ["Ashley", "Emily", "Jessica", "Samantha", "Sarah", "Taylor", "Brittany", "Hannah", "Amanda", "Megan"],
        },
        "gen_z": {
            "male": ["Liam", "Noah", "Oliver", "Elijah", "Lucas", "Mason", "Ethan", "Aiden", "Logan", "Jackson"],
            "female": ["Emma", "Olivia", "Ava", "Isabella", "Sophia", "Mia", "Charlotte", "Amelia", "Harper", "Evelyn"],
        },
    }

    def __init__(self, names_file: Path | None = None):
        """Initialize with optional external names file."""
        self._first_names = self.DEFAULT_FIRST_NAMES
        self._last_names = self.DEFAULT_LAST_NAMES
        self._generational_names = self.GENERATIONAL_NAMES

        if names_file and names_file.exists():
            with open(names_file) as f:
                data = json.load(f)
                if "first_names" in data:
                    self._first_names = data["first_names"]
                if "last_names" in data:
                    self._last_names = data["last_names"]
                if "generational_names" in data:
                    self._generational_names = data["generational_names"]

    def generate_name(
        self,
        seed: int,
        demographic: str | None = None,
        gender: str | None = None,
        age_group: str | None = None,
    ) -> PersonName:
        """
        Generate a realistic person name.

        Args:
            seed: Random seed for reproducibility
            demographic: Demographic category (white, hispanic, black, asian)
            gender: Gender (male, female)
            age_group: Generation (gen_z, millennial, gen_x, boomer)

        Returns:
            PersonName with full name and variants
        """
        rng = random.Random(seed)

        # Select demographic if not specified
        if demographic is None:
            demographic = rng.choice(list(self._first_names.keys()))

        # Select gender if not specified
        if gender is None:
            gender = rng.choice(["male", "female"])

        # Get first name pool
        if age_group and age_group in self._generational_names:
            first_pool = self._generational_names[age_group].get(gender, [])
            if first_pool:
                first_name = rng.choice(first_pool)
            else:
                first_name = rng.choice(
                    self._first_names.get(demographic, {}).get(gender, ["Alex"])
                )
        else:
            demo_names = self._first_names.get(demographic, {})
            first_pool = demo_names.get(gender, ["Alex"])
            first_name = rng.choice(first_pool)

        # Get last name
        last_pool = self._last_names.get(demographic, ["Smith"])
        last_name = rng.choice(last_pool)

        # Generate full name and variants
        full_name = f"{first_name} {last_name}"

        # Generate email
        email_formats = [
            f"{first_name.lower()}.{last_name.lower()}@company.com",
            f"{first_name[0].lower()}{last_name.lower()}@company.com",
            f"{first_name.lower()}{last_name[0].lower()}@company.com",
        ]
        email = rng.choice(email_formats)

        # Generate formality variants
        honorific = "Mr." if gender == "male" else "Ms."
        formality_variants = {
            "formal": f"{honorific} {last_name}",
            "casual": first_name,
            "full": full_name,
            "email_only": email.split("@")[0],
        }

        return PersonName(
            first=first_name,
            last=last_name,
            full=full_name,
            email=email,
            demographic=demographic,
            gender=gender,
            formality_variants=formality_variants,
        )

    def generate_batch(
        self,
        count: int,
        seed: int,
        ensure_diversity: bool = True,
    ) -> list[PersonName]:
        """
        Generate a batch of diverse names.

        Args:
            count: Number of names to generate
            seed: Base random seed
            ensure_diversity: If True, ensure demographic diversity

        Returns:
            List of PersonName objects
        """
        names = []
        demographics = list(self._first_names.keys())
        genders = ["male", "female"]
        age_groups = list(self._generational_names.keys())

        for i in range(count):
            if ensure_diversity:
                # Cycle through demographics and genders
                demographic = demographics[i % len(demographics)]
                gender = genders[i % len(genders)]
                age_group = age_groups[i % len(age_groups)]
            else:
                demographic = None
                gender = None
                age_group = None

            name = self.generate_name(
                seed=seed + i,
                demographic=demographic,
                gender=gender,
                age_group=age_group,
            )
            names.append(name)

        return names
