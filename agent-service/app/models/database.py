from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config.settings import settings


engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    channel = Column(String(32), nullable=False)
    status = Column(String(32), default="active")
    current_intent = Column(String(64))
    pending_intent = Column(String(64), nullable=True)
    missing_slots = Column(JSON, nullable=True)
    context_data = Column(JSON, nullable=True)
    summary = Column(Text)
    assigned_agent_id = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True)
    conversation_id = Column(String(64), nullable=False, index=True)
    sender_type = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


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


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(64), primary_key=True)
    order_no = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    payment_status = Column(String(32), default="paid")
    logistics_status = Column(String(32), default="pending")
    tracking_no = Column(String(64))
    carrier = Column(String(64))
    refund_status = Column(String(32), default="none")
    total_amount = Column(Float, nullable=False, default=0)
    currency = Column(String(16), default="CNY")
    shipping_address = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String(64), primary_key=True)
    order_id = Column(String(64), ForeignKey("orders.id"), nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    sku = Column(String(64))
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False)
    source_type = Column(String(64), nullable=False)
    status = Column(String(32), default="active")
    version = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    embedding_id = Column(String(128))
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    name = Column(String(128))
    email = Column(String(128))
    role = Column(String(32), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
