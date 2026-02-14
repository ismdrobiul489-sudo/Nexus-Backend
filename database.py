from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import os

# SQLite Database Name - Allow override for cloud persistence
# Default: sqlite+aiosqlite:///./nexus_v2.db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nexus_v2.db")
SYNC_DB_URL = DATABASE_URL.replace("+aiosqlite", "")

# Create Sync Engine (for migrations/initial setup)
engine = create_engine(
    SYNC_DB_URL, 
    connect_args={"check_same_thread": False, "timeout": 30}
)

# Create Async Engine (for FastAPI usage)
async_engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    connect_args={"check_same_thread": False, "timeout": 30}
)

# Async Session Factory
async_session = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Alias for backwards compatibility / execution_pipeline usage
AsyncSessionLocal = async_session

# Sync Session Factory (for scheduler/sync contexts)
sync_session = sessionmaker(
    engine, expire_on_commit=False
)



from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

# For async engine, we need to handle it slightly differently depending on driver, 
# but aiosqlite usually respects the pragma if set on the connection.
@event.listens_for(async_engine.sync_engine, "connect")
def set_async_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

async def init_db():
    async with async_engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
