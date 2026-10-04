from backend.database import db, TimestampMixin


class OrganizationMember(db.Model, TimestampMixin):
    __tablename__ = "organization_members"
    __table_args__ = (
        db.UniqueConstraint("org_id", "user_id", name="uq_org_member_user"),
        db.UniqueConstraint("org_id", "invitation_token_hash", name="uq_org_invitation_token"),
    )

    id = db.Column(db.String(100), primary_key=True)
    org_id = db.Column(db.String(100), db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(128), nullable=True, index=True)
    user_email = db.Column(db.String(255), nullable=False, index=True)
    user_name = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(30), nullable=False, default="staff")
    status = db.Column(db.String(30), nullable=False, default="active")
    invitation_token_hash = db.Column(db.String(128), nullable=True, unique=True)
    invitation_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    joined_at = db.Column(db.DateTime(timezone=True), nullable=True)

    organization = db.relationship("Organization", back_populates="members")

    def to_dict(self):
        return {
            "id": self.id,
            "orgId": self.org_id,
            "userId": self.user_id or "",
            "userEmail": self.user_email,
            "userName": self.user_name or "",
            "role": self.role,
            "status": self.status,
            "joinedAt": self.joined_at.isoformat() if self.joined_at else self.created_at.isoformat(),
        }
