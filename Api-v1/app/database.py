from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import settings
from functools import partial

# Create engines for each region
engines = {
    region: create_async_engine(db_url, echo=True, pool_size=100, max_overflow=50)
    for region, db_url in settings.DATABASES.items()
}

# Create sessionmakers for each region
session_makers = {
    region: sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    for region, engine in engines.items()
}

# Dependency to get the database session for a specific region
async def get_db(region: str = "brazil"):
    """Get database session for the specified region."""
    if region not in session_makers:
        raise ValueError(f"Unknown region: {region}. Available regions: {list(session_makers.keys())}")
    
    SessionLocal = session_makers[region]
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()  # Ensure session is properly closed

def get_db_for_region(region: str):
    """Factory function to create a get_db dependency for a specific region."""
    return partial(get_db, region=region)
