"""
Database models and connection for Instagram AI Agent
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional, Dict, Any
import json

Base = declarative_base()

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    instagram_user_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    last_message_time = Column(DateTime, default=datetime.utcnow)
    conversation_context = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False)
    instagram_message_id = Column(String, nullable=False)
    sender_username = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String, default="text")  # text, image, video, etc.
    is_from_agent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class TargetAccount(Base):
    __tablename__ = "target_accounts"
    
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    bio = Column(Text)
    follower_count = Column(Integer)
    following_count = Column(Integer)
    post_count = Column(Integer)
    is_verified = Column(Boolean, default=False)
    is_business = Column(Boolean, default=False)
    category = Column(String)  # real_estate, property, etc.
    location = Column(String)
    contact_info = Column(JSON)
    last_contacted = Column(DateTime)
    contact_attempts = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, contacted, responded, converted, blocked
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    target_industry = Column(String, nullable=False)
    target_location = Column(String, nullable=False)
    message_template = Column(Text, nullable=False)
    status = Column(String, default="active")  # active, paused, completed
    accounts_targeted = Column(Integer, default=0)
    responses_received = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def get_conversation(self, instagram_user_id: str) -> Optional[Conversation]:
        return self.session.query(Conversation).filter_by(
            instagram_user_id=instagram_user_id
        ).first()
    
    def create_conversation(self, instagram_user_id: str, username: str, context: Dict[str, Any] = None) -> Conversation:
        conversation = Conversation(
            instagram_user_id=instagram_user_id,
            username=username,
            conversation_context=context or {}
        )
        self.session.add(conversation)
        self.session.commit()
        return conversation
    
    def update_conversation_context(self, conversation_id: int, context: Dict[str, Any]):
        conversation = self.session.query(Conversation).filter_by(id=conversation_id).first()
        if conversation:
            conversation.conversation_context = context
            conversation.updated_at = datetime.utcnow()
            self.session.commit()
    
    def add_message(self, conversation_id: int, instagram_message_id: str, 
                   sender_username: str, content: str, message_type: str = "text", 
                   is_from_agent: bool = False) -> Message:
        message = Message(
            conversation_id=conversation_id,
            instagram_message_id=instagram_message_id,
            sender_username=sender_username,
            content=content,
            message_type=message_type,
            is_from_agent=is_from_agent
        )
        self.session.add(message)
        self.session.commit()
        return message
    
    def get_target_accounts(self, industry: str = None, location: str = None, 
                          status: str = None) -> List[TargetAccount]:
        query = self.session.query(TargetAccount)
        if industry:
            query = query.filter(TargetAccount.category == industry)
        if location:
            query = query.filter(TargetAccount.location.contains(location))
        if status:
            query = query.filter(TargetAccount.status == status)
        return query.all()
    
    def add_target_account(self, username: str, **kwargs) -> TargetAccount:
        account = TargetAccount(username=username, **kwargs)
        self.session.add(account)
        self.session.commit()
        return account
    
    def update_target_account(self, username: str, **kwargs):
        account = self.session.query(TargetAccount).filter_by(username=username).first()
        if account:
            for key, value in kwargs.items():
                setattr(account, key, value)
            account.updated_at = datetime.utcnow()
            self.session.commit()
    
    def create_outreach_campaign(self, name: str, target_industry: str, 
                               target_location: str, message_template: str) -> OutreachCampaign:
        campaign = OutreachCampaign(
            name=name,
            target_industry=target_industry,
            target_location=target_location,
            message_template=message_template
        )
        self.session.add(campaign)
        self.session.commit()
        return campaign
    
    def close(self):
        self.session.close()
