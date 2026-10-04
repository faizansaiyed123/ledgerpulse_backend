from backend.database import db, TimestampMixin


class ActivityLog(db.Model, TimestampMixin):
    __tablename__ = "activity_logs"

    id = db.Column(db.String(100), primary_key=True)
    org_id = db.Column(db.String(100), db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(128), nullable=True)
    user_email = db.Column(db.String(255), nullable=True)
    user_name = db.Column(db.String(255), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.String(100), nullable=True)
    details = db.Column(db.Text, nullable=True)

    organization = db.relationship("Organization", back_populates="activities")

    def to_dict(self):
        return {
            "id": self.id,
            "orgId": self.org_id,
            "userId": self.user_id or "",
            "userEmail": self.user_email or "",
            "action": self.action,
            "entityType": self.entity_type or "organization",
            "entityId": self.entity_id or "",
            "details": self.details or "",
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
