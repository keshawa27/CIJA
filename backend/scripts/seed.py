"""Fill the database with SYNTHETIC demo data. Nobody in it is real.

    python -m scripts.seed           # seed an empty database
    python -m scripts.seed --reset   # wipe everything, re-run migrations, seed again

Seeded with a fixed random seed, so every run produces the same demo.
"""

import argparse
import os
import random
from datetime import timedelta

from alembic.config import Config
from faker import Faker
from sqlalchemy import delete, func, select, text

from alembic import command
from app.db import SessionLocal, engine
from app.journey import STAGES
from app.models import Notification, Task, User, now
from app.schemas import IntakeIn
from app.security import hash_password
from app.services import complete_task, skip_task, submit_intake

PASSWORD = os.environ.get("SEED_PASSWORD", "demo-password-123")
STAFF = [
    ("admin@example.com", "Avery Admin", "admin"),
    ("lead@example.com", "Taylor Lead", "team_lead"),
    ("manager@example.com", "Morgan Manager", "manager"),
    ("casey@example.com", "Casey Worker", "caseworker"),
    ("jordan@example.com", "Jordan Worker", "caseworker"),
    ("riley@example.com", "Riley Worker", "caseworker"),
]
NEEDS = ["digital_safety", "housing", "financial", "legal", "counselling", "other"]
INTAKES = 60


def reset() -> None:
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config("alembic.ini"), "head")


def synthetic_intake(fake: Faker, n: int) -> IntakeIn:
    method = random.choices(["email", "phone", "none"], [6, 3, 1])[0]
    return IntakeIn(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=80),
        email=f"client{n:03}@example.com",
        phone=f"04{random.randint(0, 99):02} {random.randint(0, 999):03} {random.randint(0, 999):03}",
        safe_contact_method=method,
        safe_to_leave_message=random.random() < 0.5,
        needs=random.sample(NEEDS, random.randint(1, 3)),
        immediate_safety_concern=random.random() < 0.12,
        housing_unstable=random.random() < 0.25,
        has_dependants=random.random() < 0.35,
        urgency_self_rating=random.randint(1, 5),
        free_text="Synthetic record generated for demonstration.",
        consent=True,
    )


def seed() -> None:
    fake = Faker("en_AU")
    Faker.seed(42)
    random.seed(42)

    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            raise SystemExit("Database already has data. Use --reset to wipe and reseed.")

        password_hash = hash_password(PASSWORD)
        db.add_all(User(email=e, name=n, role=r, password_hash=password_hash) for e, n, r in STAFF)
        db.commit()
        lead = db.scalar(select(User).where(User.role == "team_lead"))

        for n in range(INTAKES):
            intake = submit_intake(db, synthetic_intake(fake, n))
            days_ago = random.randint(0, 30)
            intake.submitted_at -= timedelta(days=days_ago, hours=random.randint(0, 8))

            # walk the case part of the way through the journey
            target = random.choices(STAGES[1:], [8, 8, 10, 10, 8, 16 if days_ago >= 2 else 0])[0]
            worker = db.get(User, intake.assigned_to)
            while intake.stage != target:
                for task in db.scalars(select(Task).where(Task.intake_id == intake.id, Task.status == "open")):
                    if random.random() < 0.03:
                        skip_task(db, task, lead, "Synthetic: client declined this step")
                    else:
                        complete_task(db, task, worker)

            if intake.stage == "closed":
                intake.closed_at = intake.submitted_at + timedelta(days=random.uniform(1, days_ago))
            elif random.random() < 0.2:  # some open cases have gone quiet
                for task in db.scalars(select(Task).where(Task.intake_id == intake.id, Task.status == "open")):
                    task.due_at = now() - timedelta(days=random.randint(1, 4))
            db.commit()

        # Don't flood the mail catcher with a backlog of emails nobody asked for.
        db.execute(delete(Notification).where(Notification.channel == "email", Notification.status == "pending"))
        db.commit()

        print(f"Seeded {len(STAFF)} staff and {INTAKES} synthetic intakes.")
        print(f"Log in with any of these (password: {PASSWORD}):")
        for email, _, role in STAFF:
            print(f"  {role:<11} {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="wipe the database first")
    if parser.parse_args().reset:
        reset()
    seed()
