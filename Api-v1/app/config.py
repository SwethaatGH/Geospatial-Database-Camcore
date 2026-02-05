class Settings:
    # Database URLs for different regions
    DATABASES = {
        "brazil": "postgresql+asyncpg://postgres:postgres@localhost:5433/covariablesv1",
        "indonesia": "postgresql+asyncpg://postgres:postgres@localhost:5433/covariables_indonesia"
    }
    
    # Default database (for backwards compatibility)
    DATABASE_URL = DATABASES["brazil"]

settings = Settings()
