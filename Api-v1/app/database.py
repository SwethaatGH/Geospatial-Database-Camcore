from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import settings

# Create engines for both regions
engine_brazil = create_async_engine(settings.DATABASE_URL, echo=True, pool_size=100, max_overflow=50)
engine_indonesia = create_async_engine(settings.DATABASE_URL_INDONESIA, echo=True, pool_size=100, max_overflow=50)

# Create sessionmakers for both regions
AsyncSessionLocal_Brazil = sessionmaker(engine_brazil, class_=AsyncSession, expire_on_commit=False)
AsyncSessionLocal_Indonesia = sessionmaker(engine_indonesia, class_=AsyncSession, expire_on_commit=False)

# Store engines in a dict for easy access
_engines = {
    "brazil": engine_brazil,
    "indonesia": engine_indonesia
}

_session_makers = {
    "brazil": AsyncSessionLocal_Brazil,
    "indonesia": AsyncSessionLocal_Indonesia
}

# Dependency to get the database session for a specific region
async def get_db(region: str = "brazil"):
    session_maker = _session_makers.get(region, AsyncSessionLocal_Brazil)
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()  # Ensure session is properly closed

# Helper function to get session maker by region
def get_session_maker(region: str):
    return _session_makers.get(region, AsyncSessionLocal_Brazil)
