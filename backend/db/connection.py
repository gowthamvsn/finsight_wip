import asyncpg
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

_pool = None


async def create_pool():
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=os.getenv("DATABASE_URL"),
        min_size=5,
        max_size=20,
        command_timeout=60
    )
    return _pool


def get_pool():
    return _pool


async def fetch_one(query, *args):
    async with _pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch_all(query, *args):
    async with _pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def execute(query, *args):
    async with _pool.acquire() as conn:
        return await conn.execute(query, *args)
