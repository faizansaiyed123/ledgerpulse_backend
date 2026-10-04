"""Initial LedgerPulse schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255)),
        sa.Column("tax_id", sa.String(100)),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("postal_code", sa.String(30)),
        sa.Column("country", sa.String(100)),
        sa.Column("phone", sa.String(50)),
        sa.Column("email", sa.String(255)),
        sa.Column("website", sa.String(255)),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("logo_url", sa.Text()),
        sa.Column("fiscal_year_start", sa.String(20)),
        sa.Column("default_payment_terms", sa.Integer(), nullable=False),
        sa.Column("invoice_notes", sa.Text()),
        sa.Column("invoice_terms", sa.Text()),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("invoice_sequence", sa.Integer(), nullable=False),
        sa.Column("invoice_sequence_year", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_created_by", "organizations", ["created_by"])

    op.create_table(
        "organization_members",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("org_id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(128)),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("user_name", sa.String(255)),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("invitation_token_hash", sa.String(128), unique=True),
        sa.Column("invitation_expires_at", sa.DateTime(timezone=True)),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_member_user"),
        sa.UniqueConstraint("org_id", "invitation_token_hash", name="uq_org_invitation_token"),
    )
    op.create_index("ix_organization_members_org_id", "organization_members", ["org_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])
    op.create_index("ix_organization_members_user_email", "organization_members", ["user_email"])

    op.create_table(
        "customers",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("org_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("company_name", sa.String(255)),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("tax_id", sa.String(100)),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("payment_terms", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_customers_org_id", "customers", ["org_id"])

    op.create_table(
        "vendors",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("org_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("company", sa.String(255)),
        sa.Column("tax_id", sa.String(100)),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_vendors_org_id", "vendors", ["org_id"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("org_id", sa.String(100), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(100), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(255)),
        sa.Column("issue_date", sa.String(20), nullable=False),
        sa.Column("due_date", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(7, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_rate", sa.Numeric(7, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("balance_due", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("terms", sa.Text()),
        sa.Column("recurring_id", sa.String(100)),
        sa.Column("created_by", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("org_id", "invoice_number", name="uq_invoice_org_number"),
    )
    for name, cols in [
        ("ix_invoices_org_id", ["org_id"]),
        ("ix_invoices_invoice_number", ["invoice_number"]),
        ("ix_invoices_customer_id", ["customer_id"]),
        ("ix_invoices_status", ["status"]),
    ]:
        op.create_index(name, "invoices", cols)

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("invoice_id", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(7, 2), nullable=False),
        sa.Column("tax_rate_percent", sa.Numeric(7, 2), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    op.create_table(
        "recurring_invoices",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("org_id", sa.String(100), nullable=False),
        sa.Column("template_invoice_number", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(100), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("next_run_date", sa.String(20), nullable=False),
        sa.Column("last_run_date", sa.String(20)),
        sa.Column("occurrences", sa.Integer(), nullable=False),
        sa.Column("max_occurrences", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("terms", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_recurring_invoices_org_id", "recurring_invoices", ["org_id"])
    op.create_index("ix_recurring_invoices_customer_id", "recurring_invoices", ["customer_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("org_id", sa.String(100), nullable=False),
        sa.Column("invoice_id", sa.String(100), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(100), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_date", sa.String(20), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column("reference", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_payments_org_id", "payments", ["org_id"])
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    op.create_index("ix_payments_customer_id", "payments", ["customer_id"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("org_id", sa.String(100), nullable=False),
        sa.Column("vendor_id", sa.String(100)),
        sa.Column("vendor_name", sa.String(255)),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("date", sa.String(20), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column("reimbursable", sa.Boolean(), nullable=False),
        sa.Column("receipt_url", sa.Text()),
        sa.Column("receipt_name", sa.String(255)),
        sa.Column("notes", sa.Text()),
        sa.Column("recurring", sa.Boolean(), nullable=False),
        sa.Column("recurring_interval", sa.String(20)),
        sa.Column("tax_deductible", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_by", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_expenses_org_id", "expenses", ["org_id"])
    op.create_index("ix_expenses_vendor_id", "expenses", ["vendor_id"])

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("org_id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(128)),
        sa.Column("user_email", sa.String(255)),
        sa.Column("user_name", sa.String(255)),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.String(100)),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_activity_logs_org_id", "activity_logs", ["org_id"])


def downgrade():
    for name in ["ix_activity_logs_org_id"]:
        op.drop_index(name, table_name="activity_logs")
    op.drop_table("activity_logs")
    for name in ["ix_expenses_vendor_id", "ix_expenses_org_id"]:
        op.drop_index(name, table_name="expenses")
    op.drop_table("expenses")
    for name in ["ix_payments_customer_id", "ix_payments_invoice_id", "ix_payments_org_id"]:
        op.drop_index(name, table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_recurring_invoices_customer_id", table_name="recurring_invoices")
    op.drop_index("ix_recurring_invoices_org_id", table_name="recurring_invoices")
    op.drop_table("recurring_invoices")
    op.drop_index("ix_invoice_items_invoice_id", table_name="invoice_items")
    op.drop_table("invoice_items")
    for name in ["ix_invoices_status", "ix_invoices_customer_id", "ix_invoices_invoice_number", "ix_invoices_org_id"]:
        op.drop_index(name, table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_vendors_org_id", table_name="vendors")
    op.drop_table("vendors")
    op.drop_index("ix_customers_org_id", table_name="customers")
    op.drop_table("customers")
    for name in ["ix_organization_members_user_email", "ix_organization_members_user_id", "ix_organization_members_org_id"]:
        op.drop_index(name, table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_index("ix_organizations_created_by", table_name="organizations")
    op.drop_table("organizations")
