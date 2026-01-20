import asyncio
import asyncpg

async def test():
    try:
        pool = await asyncpg.create_pool(
            'postgresql://postgres:S27052007s@localhost:5432/couch_breath_test',
            min_size=1,
            max_size=2
        )
        result = await pool.fetchval('SELECT 1')
        print(f"Connection OK! Result: {result}")
        await pool.close()
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
