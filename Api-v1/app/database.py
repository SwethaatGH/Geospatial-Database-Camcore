from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import settings

# Create an asynchronous engine
engine = create_async_engine(settings.DATABASE_URL, echo=True, pool_size = 100, max_overflow = 100)

# Create a sessionmaker for AsyncSession
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Dependency to get the database session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()  # Ensure session is properly closed
