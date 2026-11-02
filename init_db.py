#!/usr/bin/env python
"""
Initialize database and create tables
"""
from app.database import get_engine
from app.models import Base

if __name__ == "__main__":
    engine = get_engine()
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized successfully")
