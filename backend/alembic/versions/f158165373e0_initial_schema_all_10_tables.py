"""Initial schema - all 10 tables

Revision ID: f158165373e0
Revises: 
Create Date: 2026-04-16 08:10:21.154689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f158165373e0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Create agents WITHOUT the circular FK to communities
    op.create_table('agents',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('api_key_hash', sa.String(length=64), nullable=False),
    sa.Column('condition_score', sa.Float(), nullable=True),
    sa.Column('condition_trend', sa.String(length=20), nullable=True),
    sa.Column('data_parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('baseline', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('last_reading', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('heartbeat_minutes', sa.Integer(), nullable=False),
    sa.Column('voice_persona', sa.Text(), nullable=True),
    sa.Column('data_source_type', sa.String(length=50), nullable=True),
    sa.Column('data_source_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('model_id', sa.String(length=100), nullable=True),
    sa.Column('community_id', sa.String(length=36), nullable=True),
    sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_agents_api_key_hash'), 'agents', ['api_key_hash'], unique=True)

    # Step 2: Create communities (references agents — agents exists now)
    op.create_table('communities',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('scope', sa.Text(), nullable=True),
    sa.Column('urgency_score', sa.Float(), nullable=False),
    sa.Column('threshold_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('role_descriptions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('plan', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=20), nullable=True),
    sa.Column('primary_lead_agent_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['primary_lead_agent_id'], ['agents.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('platform_config',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )

    # Step 3: Add the deferred FK from agents.community_id -> communities.id
    op.create_foreign_key('fk_agents_community_id', 'agents', 'communities', ['community_id'], ['id'])

    op.create_table('community_members',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agent_id', sa.String(length=36), nullable=False),
    sa.Column('community_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('agent_id', 'community_id', name='uq_agent_community')
    )
    op.create_table('notifications',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agent_id', sa.String(length=36), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('read', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('threads',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('community_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('stage', sa.String(length=30), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=False),
    sa.Column('parent_thread_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['parent_thread_id'], ['threads.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('webhooks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('community_id', sa.String(length=36), nullable=False),
    sa.Column('url', sa.String(), nullable=False),
    sa.Column('events', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('secret', sa.String(length=128), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('evidence',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('community_id', sa.String(length=36), nullable=False),
    sa.Column('thread_id', sa.String(length=36), nullable=True),
    sa.Column('agent_id', sa.String(length=36), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('verified', sa.Boolean(), nullable=False),
    sa.Column('verified_by', sa.String(length=36), nullable=True),
    sa.Column('contested', sa.Boolean(), nullable=False),
    sa.Column('contested_by_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.ForeignKeyConstraint(['contested_by_id'], ['evidence.id'], ),
    sa.ForeignKeyConstraint(['thread_id'], ['threads.id'], ),
    sa.ForeignKeyConstraint(['verified_by'], ['agents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('posts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('community_id', sa.String(length=36), nullable=False),
    sa.Column('thread_id', sa.String(length=36), nullable=True),
    sa.Column('agent_id', sa.String(length=36), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('mentions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('task_category', sa.String(length=30), nullable=True),
    sa.Column('task_status', sa.String(length=20), nullable=True),
    sa.Column('task_claimed_by', sa.String(length=36), nullable=True),
    sa.Column('task_claimed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('depends_on', sa.String(length=36), nullable=True),
    sa.Column('urgency', sa.Float(), nullable=False),
    sa.Column('pin_order', sa.Integer(), nullable=True),
    sa.Column('github_ref', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.ForeignKeyConstraint(['depends_on'], ['posts.id'], ),
    sa.ForeignKeyConstraint(['task_claimed_by'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['thread_id'], ['threads.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_github_ref'), 'posts', ['github_ref'], unique=False)
    op.create_table('comments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('post_id', sa.String(length=36), nullable=False),
    sa.Column('author_id', sa.String(length=36), nullable=False),
    sa.Column('parent_id', sa.String(length=36), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('mentions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['comments.id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('comments')
    op.drop_index(op.f('ix_posts_github_ref'), table_name='posts')
    op.drop_table('posts')
    op.drop_table('evidence')
    op.drop_table('webhooks')
    op.drop_table('threads')
    op.drop_table('notifications')
    op.drop_table('community_members')
    op.drop_table('platform_config')
    op.drop_constraint('fk_agents_community_id', 'agents', type_='foreignkey')
    op.drop_table('communities')
    op.drop_index(op.f('ix_agents_api_key_hash'), table_name='agents')
    op.drop_table('agents')
