from __future__ import annotations
from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email = Column(String(255), nullable=False)
    credential_sent = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="email_logs")

    def __repr__(self) -> str:
        return f"<EmailLog(user_id={self.user_id}, email={self.email}, credential_sent={self.credential_sent})>"
