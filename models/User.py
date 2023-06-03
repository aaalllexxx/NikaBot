from sqlalchemy import Column, Integer, String, Date

from settings import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    firstname = Column(String(1024), nullable=False)
    lastname = Column(String(1024), nullable=True)
    chat_id = Column(Integer, nullable=False)
    dob = Column(String(11), nullable=True)
    phone = Column(String(1024), nullable=True)
    comp = Column(String(2**11), nullable=True)
    group = Column(String(20), nullable=True)
    level = Column(Integer, nullable=False, default=0)
    read_news = Column(String(2**13), nullable=True, default="")
    viewed_index = Column(Integer, default=0)
    want_find = Column(Integer, default=1)
    is_finding = Column(String(512), nullable=True)
    link = Column(String(256), nullable=True)
    last_published = Column(String(256), nullable=True)

