"""One-shot database bootstrap command used by Docker Compose."""

import asyncio

from app.core.database import engine, initialize_database


async def main() -> None:
    await initialize_database()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
