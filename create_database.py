from app.database import Base, engine
from app.models import Issue  # noqa: F401

print("Creating BugFlow database...")
Base.metadata.create_all(bind=engine)
print("Database created successfully.")
print("Database file: bugflow.db")
print("Table created: issues")
