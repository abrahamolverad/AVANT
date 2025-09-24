from alembic import op
import sqlalchemy as sa

revision = '0001_base'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('company',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('website', sa.String(255)),
        sa.Column('country', sa.String(64)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now())
    )
    op.create_index('ix_company_name', 'company', ['name'])

    op.create_table('contact',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('company.id')),
        sa.Column('full_name', sa.String(255)),
        sa.Column('role', sa.String(255)),
        sa.Column('email', sa.String(255)),
        sa.Column('phone', sa.String(64)),
        sa.Column('socials', sa.JSON),
        sa.Column('consent_status', sa.String(32)),
        sa.Column('channel_opt_in', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now())
    )
    op.create_index('ix_contact_email', 'contact', ['email'])

    op.create_table('lead',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('company.id')),
        sa.Column('contact_id', sa.Integer, sa.ForeignKey('contact.id')),
        sa.Column('source', sa.String(64)),
        sa.Column('status', sa.String(64)),
        sa.Column('score', sa.Integer),
        sa.Column('notes', sa.Text),
        sa.Column('attribution', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now())
    )
    op.create_index('idx_lead_status', 'lead', ['status'])

    op.create_table('interaction',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('lead_id', sa.Integer, sa.ForeignKey('lead.id')),
        sa.Column('channel', sa.String(32), nullable=False),
        sa.Column('direction', sa.String(16)),
        sa.Column('template_id', sa.String(128)),
        sa.Column('body', sa.Text),
        sa.Column('meta', sa.JSON),
        sa.Column('message_id_ext', sa.String(128)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    op.create_index('idx_interaction_lead_created', 'interaction', ['lead_id', 'created_at'])

    op.create_table('campaign',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('objective', sa.String(255)),
        sa.Column('channel', sa.String(32)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now())
    )

    op.create_table('sequence_step',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('campaign_id', sa.Integer, sa.ForeignKey('campaign.id'), nullable=False),
        sa.Column('step_no', sa.Integer, nullable=False),
        sa.Column('channel', sa.String(32), nullable=False),
        sa.Column('template_id', sa.String(128)),
        sa.Column('wait_hours', sa.Integer, nullable=False),
        sa.Column('rules', sa.JSON)
    )

    op.create_table('message',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('lead_id', sa.Integer, sa.ForeignKey('lead.id')),
        sa.Column('step_id', sa.Integer, sa.ForeignKey('sequence_step.id')),
        sa.Column('channel', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('provider_ref', sa.String(128)),
        sa.Column('cost_cents', sa.Integer),
        sa.Column('tokens_in', sa.Integer),
        sa.Column('tokens_out', sa.Integer),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    op.create_index('idx_message_channel_status', 'message', ['channel', 'status'])

    op.create_table('consent',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('contact_id', sa.Integer, sa.ForeignKey('contact.id'), nullable=False),
        sa.Column('channel', sa.String(32), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('proof', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )

    op.create_table('content_item',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('type', sa.String(32), nullable=False),
        sa.Column('title', sa.String(255)),
        sa.Column('body', sa.Text),
        sa.Column('media_url', sa.String(255)),
        sa.Column('language', sa.String(16)),
        sa.Column('tags', sa.String(255)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now())
    )

def downgrade():
    op.drop_table('content_item')
    op.drop_table('consent')
    op.drop_index('idx_message_channel_status', table_name='message')
    op.drop_table('message')
    op.drop_table('sequence_step')
    op.drop_table('campaign')
    op.drop_index('idx_interaction_lead_created', table_name='interaction')
    op.drop_table('interaction')
    op.drop_index('idx_lead_status', table_name='lead')
    op.drop_table('lead')
    op.drop_index('ix_contact_email', table_name='contact')
    op.drop_table('contact')
    op.drop_index('ix_company_name', table_name='company')
    op.drop_table('company')
