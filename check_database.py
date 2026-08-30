from sqlalchemy import inspect
from app.database import engine

inspector = inspect(engine)

print("Database connection: OK")
print("Tables:")
for table in inspector.get_table_names():
    print(f" - {table}")
