import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test_conn():
    # Use asyncpg scheme
    url_pooler = "postgresql+asyncpg://postgres.opxhdedjjvpbwzyprfrx:dailyassist2312@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
    url_direct = "postgresql+asyncpg://postgres:dailyassist2312@db.opxhdedjjvpbwzyprfrx.supabase.co:5432/postgres"

    print("Testing Pooler Connection (Port 6543)...")
    try:
        engine1 = create_async_engine(url_pooler)
        async with engine1.connect() as conn:
            print("✅ Pooler connection successful!")
    except Exception as e:
        print(f"❌ Pooler connection failed: {e}")

    print("\nTesting Direct Connection (Port 5432)...")
    try:
        engine2 = create_async_engine(url_direct)
        async with engine2.connect() as conn:
            print("✅ Direct connection successful!")
    except Exception as e:
        print(f"❌ Direct connection failed: {e}")

asyncio.run(test_conn())
