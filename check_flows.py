
import asyncio
from database import get_session
from models import FlowConfig
from sqlmodel import select

async def check_flows():
    async for session in get_session():
        result = await session.execute(select(FlowConfig))
        flows = result.scalars().all()
        print(f"Total Flows in DB: {len(flows)}")
        for f in flows:
            print(f" - {f.name} ({f.id}) [Active: {f.is_active}]")
            print(f"   Created At Type: {type(f.created_at)} Value: {f.created_at}")

if __name__ == "__main__":
    asyncio.run(check_flows())
