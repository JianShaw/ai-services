import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.database import async_session_maker, init_db
from app.services.order_seed import seed_mock_orders


async def main():
    await init_db()
    async with async_session_maker() as session:
        order_numbers = await seed_mock_orders(session)

    print("Seeded mock orders:")
    for order_no in order_numbers:
        print(f"- {order_no}")


if __name__ == "__main__":
    asyncio.run(main())
