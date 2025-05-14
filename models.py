from sqlalchemy import Column, Integer,BigInteger, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from database import Base 

class User(Base):
    __tablename__ = "user"
    id = Column(BigInteger, primary_key=True)
    phone_number = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    patronymic = Column(String)
    password = Column(String)

class Teacher(Base):
    __tablename__ = "teacher"
    id = Column(BigInteger, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    patronymic = Column(String)
    user_id = Column(BigInteger, ForeignKey("user.id"))
    user = relationship("User")

class Subject(Base):
    __tablename__ = "subject"
    id = Column(BigInteger, primary_key=True)
    title = Column(String)
    short_title = Column(String)
    user_id = Column(BigInteger, ForeignKey("user.id"))
    user = relationship("User")

class Group(Base):
    __tablename__ = "group"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("user.id"))
    start_year = Column(Integer)
    title = Column(String)
    user = relationship("User")

class Exam(Base):
    __tablename__ = "exam"
    id = Column(BigInteger, primary_key=True)
    academic_group_id = Column(BigInteger, ForeignKey("group.id"))
    teacher_id = Column(BigInteger, ForeignKey("teacher.id"))
    subject_id = Column(BigInteger, ForeignKey("subject.id"))
    user_id = Column(BigInteger, ForeignKey("user.id"))
    session_number = Column(Integer)
    exam_number = Column(Integer)
    success_count = Column(Integer)
    all_count = Column(Integer)
    group = relationship("Group")
    teacher = relationship("Teacher")
    subject = relationship("Subject")
    user = relationship("User")