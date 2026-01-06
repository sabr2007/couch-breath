"""
Пул соединений PostgreSQL
"""

import asyncpg
from typing import Optional

from bot.config import config


# Глобальный пул соединений
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Получить пул соединений (создаёт при первом вызове)"""
    global _pool
    
    if _pool is None:
        _pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=2,
            max_size=10
        )
    
    return _pool


async def close_pool():
    """Закрыть пул соединений"""
    global _pool
    
    if _pool:
        await _pool.close()
        _pool = None
