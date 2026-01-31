import asyncpg
from dataclasses import dataclass

@dataclass(frozen=True)
class PgConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    sslmode: str = "disable"

def _ssl_arg(sslmode: str):
    return None if sslmode == "disable" else True

async def create_pool(cfg: PgConfig) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=cfg.host,
        port=cfg.port,
        database=cfg.database,
        user=cfg.user,
        password=cfg.password,
        ssl=_ssl_arg(cfg.sslmode),
        min_size=1,
        max_size=10,
        command_timeout=30,
    )

