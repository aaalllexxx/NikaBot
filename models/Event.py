from sqlalchemy import Column, Integer, String, Date

from settings import Base


class Event(Base):
    __tablename__ = "events"
    id = Column(String(1024), primary_key=True)
    text = Column(String(2**12))
    tags = Column(String(2**12))
