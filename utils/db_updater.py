import asyncpg
from asyncpg.transaction import Transaction
from exencolorlogs import Logger
from utils.enums import FetchMode

VERSION = 1


async def update_db(db):
    log = Logger("DB_UPDATER")
    log.info("Checking database version incompatibilities...")
    _con: asyncpg.Connection = await db.pool.acquire()
    db_version = await db.execute(
        "SELECT version FROM version", fetch_mode=FetchMode.VAL
    )
    log.info("DB version: %s | Required version: %s", db_version, VERSION)
    try:
        while db_version < VERSION:
            db_version += 1
            log.info("Executing compatibility script #%s", db_version)
            async with _con.transaction():
                transaction: Transaction
                match db_version:
                    case 1:
                        await _con.execute(
                            "ALTER TABLE scores ADD COLUMN score_daily INT DEFAULT 0"
                        )

                # noinspection SqlWithoutWhere
                await _con.execute("UPDATE version SET version = $1", db_version)
            log.ok("Compatibility script #%s was executed successfully", db_version)
        log.ok("Database is at latest version")
    except Exception as e:
        log.error(
            "Failed to execute compatibility script %s, rolled back to %s",
            db_version,
            db_version - 1,
            exc_info=e,
        )
    finally:
        await _con.close()
