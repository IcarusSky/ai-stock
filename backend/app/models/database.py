"""
AI Stock - 数据库连接管理
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as aioredis

from app.core.config import settings

# PostgreSQL
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# MongoDB
mongo_client: AsyncIOMotorClient = None


async def init_tables():
    """初始化 PostgreSQL 表结构（开发阶段直接使用 create_all）"""
    # 确保所有 ORM 模型都注册到 Base.metadata
    from app.models import stock  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_postgres():
    """初始化 PostgreSQL"""
    await init_tables()


async def close_postgres():
    """关闭 PostgreSQL"""
    await engine.dispose()


async def init_mongodb():
    """初始化 MongoDB"""
    global mongo_client
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)


async def close_mongodb():
    """关闭 MongoDB"""
    global mongo_client
    if mongo_client:
        mongo_client.close()


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with async_session_maker() as session:
        yield session


def get_mongo_db():
    """获取 MongoDB 数据库"""
    global mongo_client
    return mongo_client["aistock"]


# Redis 连接池
redis_pool: aioredis.ConnectionPool = None


async def init_redis():
    """初始化 Redis"""
    global redis_pool
    redis_pool = aioredis.ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=10,
        decode_responses=True
    )


async def close_redis():
    """关闭 Redis"""
    global redis_pool
    if redis_pool:
        await redis_pool.disconnect()


async def get_redis() -> aioredis.Redis:
    """获取 Redis 客户端"""
    return aioredis.Redis(connection_pool=redis_pool)
