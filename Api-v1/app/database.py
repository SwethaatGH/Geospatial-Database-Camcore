from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from .config import settings
from functools import partial

# Create engines for each region with optimized settings
engines = {
    region: create_async_engine(
        db_url,
        echo=False,  # Set to True for debugging
        pool_size=100,
        max_overflow=50,
        pool_pre_ping=True,  # Verify connections before using
    )
    for region, db_url in settings.DATABASES.items()
}

# Create sessionmakers for each region
session_makers = {
    region: sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    for region, engine in engines.items()
}

# Dependency to get the database session for a specific region
async def get_db(region: str = "brazil"):
    """Get database session for the specified region with parallel execution enabled."""
    if region not in session_makers:
        raise ValueError(f"Unknown region: {region}. Available regions: {list(session_makers.keys())}")
    
    SessionLocal = session_makers[region]
    async with SessionLocal() as session:
        try:
            # Enable parallel execution for this session
            await session.execute(text("SET max_parallel_workers_per_gather = 4"))
            await session.execute(text("SET parallel_tuple_cost = 0.01"))
            yield session
        finally:
            await session.close()  # Ensure session is properly closed

def get_db_for_region(region: str):
    """Factory function to create a get_db dependency for a specific region."""
    return partial(get_db, region=region)
