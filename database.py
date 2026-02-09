from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# SQLite Database Name
DATABASE_URL = "sqlite+aiosqlite:///./nexus_v2.db"

# Create Sync Engine (for migrations/initial setup)
engine = create_engine("sqlite:///./nexus_v2.db", connect_args={"check_same_thread": False})

# Create Async Engine (for FastAPI usage)
async_engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

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


async def init_db():
    async with async_engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
