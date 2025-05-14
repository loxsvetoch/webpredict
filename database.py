from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:1@localhost/webpredict"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

Base.metadata.drop_all(bind=engine)

# Потом создаём их заново уже с новыми типами (BigInteger и т.п.)
Base.metadata.create_all(bind=engine)
