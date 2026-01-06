"""
Автоматические миграции базы данных
"""

import logging
from pathlib import Path

from bot.database.connection import get_pool

logger = logging.getLogger(__name__)

# Путь к папке с миграциями
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


async def run_migrations():
    """Выполнить все SQL-миграции из папки migrations/"""
    pool = await get_pool()
    
    if not MIGRATIONS_DIR.exists():
        logger.warning(f"Папка миграций не найдена: {MIGRATIONS_DIR}")
        return
    
    # Получаем все .sql файлы, отсортированные по имени
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    
    if not sql_files:
        logger.info("Миграции не найдены")
        return
    
    async with pool.acquire() as conn:
        for sql_file in sql_files:
            logger.info(f"Выполняю миграцию: {sql_file.name}")
            try:
                sql_content = sql_file.read_text(encoding="utf-8")
                await conn.execute(sql_content)
                logger.info(f"✓ Миграция {sql_file.name} выполнена")
            except Exception as e:
                # Игнорируем ошибки "already exists" — это нормально при повторных запусках
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info(f"✓ Миграция {sql_file.name} уже применена")
                else:
                    logger.error(f"✗ Ошибка в {sql_file.name}: {e}")
                    raise
