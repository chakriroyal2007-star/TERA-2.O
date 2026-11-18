"""Optimization multi patient schema, capacity, and index updates.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0023'
down_revision = '0022'


def upgrade():
    # 1. Add capacity, equipment and live coordinates to ambulances
    with op.batch_alter_table("ambulances") as batch_op:
        batch_op.add_column(sa.Column("patient_capacity", sa.Integer(), nullable=False, server_default="2"))
        batch_op.add_column(sa.Column("equipment_level", sa.String(50), nullable=True, server_default="ALS"))
        batch_op.add_column(sa.Column("current_latitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("current_longitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("current_speed", sa.Float(), nullable=True))

    # 2. Add priority_score and priority_breakdown to incidents
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.add_column(sa.Column("priority_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("priority_breakdown", sa.JSON(), nullable=True))

    # 3. Create optimization_executions table
    op.create_table(
        "optimization_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("algorithm", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="completed", nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=True),
        sa.Column("output_summary", sa.JSON(), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_opt_exec_created_at", "optimization_executions", ["created_at"])

    # 4. Drop unique constraint uq_active_mission_per_incident if present to allow multi-ambulance dispatch
    op.execute(sa.text("DROP INDEX IF EXISTS uq_active_mission_per_incident"))

    # 5. Register permissions for optimization endpoints
    opt_actions = [
        "GET /api/v1/optimization/priority-ranking",
        "GET /api/v1/optimization/weights",
        "PATCH /api/v1/optimization/weights",
        "POST /api/v1/optimization/allocate-ambulances",
        "GET /api/v1/optimization/hospital-ranking/{incident_id}",
        "POST /api/v1/optimization/dijkstra-route",
        "GET /api/v1/optimization/baseline-vs-optimized",
        "POST /api/v1/optimization/demo-simulation/load",
        "POST /api/v1/optimization/demo-simulation/reset",
    ]
    for action in opt_actions:
        op.execute(sa.text(f"INSERT INTO permissions (action) VALUES ('{action}') ON CONFLICT DO NOTHING"))

    for role in ["operator", "admin", "analyst", "responder", "hospital"]:
        for action in opt_actions:
            op.execute(sa.text(f"INSERT INTO role_permissions (role_id, action) VALUES ('{role}', '{action}') ON CONFLICT DO NOTHING"))


def downgrade():
    try:
        op.drop_table("optimization_executions")
    except Exception:
        pass

    with op.batch_alter_table("incidents") as batch_op:
        batch_op.drop_column("priority_breakdown")
        batch_op.drop_column("priority_score")

    with op.batch_alter_table("ambulances") as batch_op:
        batch_op.drop_column("current_speed")
        batch_op.drop_column("current_longitude")
        batch_op.drop_column("current_latitude")
        batch_op.drop_column("equipment_level")
        batch_op.drop_column("patient_capacity")
