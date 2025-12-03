class Settings:
    # Default database (Brazil/Latin America)
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/covariablesv1"
    # Indonesia database
    DATABASE_URL_INDONESIA = "postgresql+asyncpg://postgres:postgres@localhost:5433/covariables_indonesia"

settings = Settings()
