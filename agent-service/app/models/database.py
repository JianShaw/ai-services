from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, String, DateTime, Text, JSON
from datetime import datetime
from app.config.settings import settings

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

# 创建异步会话工厂
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base类
Base = declarative_base()


# 会话表
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    channel = Column(String(32), nullable=False)
    status = Column(String(32), default="active")
    current_intent = Column(String(64))
    summary = Column(Text)
    assigned_agent_id = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 消息表
class Message(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True)
    conversation_id = Column(String(64), nullable=False, index=True)
    sender_type = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    meta_data = Column(JSON)  # metadata是保留字，改用meta_data
    created_at = Column(DateTime, default=datetime.utcnow)


# 工单表
class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(64), primary_key=True)
    conversation_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    type = Column(String(64), nullable=False)
    priority = Column(String(32), default="medium")
    status = Column(String(32), default="open")
    description = Column(Text)
    assigned_to = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 知识库文档表
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False)
    source_type = Column(String(64), nullable=False)
    status = Column(String(32), default="active")
    version = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 用户表
class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    name = Column(String(128))
    email = Column(String(128))
    role = Column(String(32), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)


# 初始化数据库
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# 获取数据库会话
async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()