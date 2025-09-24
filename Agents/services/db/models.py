from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Text, Index, func

class Base(DeclarativeBase): pass

class Company(Base):
    __tablename__ = "company"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class Contact(Base):
    __tablename__ = "contact"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id"))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(64))
    socials: Mapped[dict | None] = mapped_column(JSON)
    consent_status: Mapped[str | None] = mapped_column(String(32))  # pending/opt_in/opt_out
    channel_opt_in: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class Lead(Base):
    __tablename__ = "lead"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contact.id"))
    source: Mapped[str | None] = mapped_column(String(64))  # inbound, ads, research, referral
    status: Mapped[str | None] = mapped_column(String(64))  # new, qualified, scheduled, no_show, won, lost
    score: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

Index("idx_lead_status", Lead.status)

class Interaction(Base):
    __tablename__ = "interaction"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("lead.id"))
    channel: Mapped[str] = mapped_column(String(32))          # whatsapp, instagram, email, web
    direction: Mapped[str] = mapped_column(String(16))         # inbound/outbound
    template_id: Mapped[str | None] = mapped_column(String(128))
    body: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSON)
    message_id_ext: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

Index("idx_interaction_lead_created", Interaction.lead_id, Interaction.created_at.desc())

class Campaign(Base):
    __tablename__ = "campaign"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    objective: Mapped[str | None] = mapped_column(String(255))
    channel: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class SequenceStep(Base):
    __tablename__ = "sequence_step"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"))
    step_no: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(32))
    template_id: Mapped[str | None] = mapped_column(String(128))
    wait_hours: Mapped[int] = mapped_column(Integer)
    rules: Mapped[dict | None] = mapped_column(JSON)

class Message(Base):
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("lead.id"))
    step_id: Mapped[int | None] = mapped_column(ForeignKey("sequence_step.id"))
    channel: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))  # queued, sent, delivered, failed
    provider_ref: Mapped[str | None] = mapped_column(String(128))
    cost_cents: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

Index("idx_message_channel_status", Message.channel, Message.status)

class Consent(Base):
    __tablename__ = "consent"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contact.id"))
    channel: Mapped[str] = mapped_column(String(32))  # whatsapp/email/instagram
    status: Mapped[str] = mapped_column(String(16))   # opt_in/opt_out
    proof: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class ContentItem(Base):
    __tablename__ = "content_item"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(32))     # template, caption, asset
    title: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(16))
    tags: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
