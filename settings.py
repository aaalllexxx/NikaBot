import os
from aiogram import Bot, Dispatcher
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import dotenv


dotenv.load_dotenv(".env")

bot = Bot(os.environ.get("TOKEN"))
dp = Dispatcher(bot, storage=MemoryStorage())
engine = create_engine("sqlite:///db.db")
Session = sessionmaker(bind=engine)
Base = declarative_base()
session = Session()
