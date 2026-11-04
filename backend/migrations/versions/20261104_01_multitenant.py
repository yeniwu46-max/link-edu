"""Add tenant ownership and visibility scopes.

Revision ID: 20261104_01
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '20261104_01'
down_revision = None
branch_labels = None
depends_on = None


TENANT_COLUMNS = {
    'courses': [('tenant_id', sa.Integer())],
    'training_sessions': [('tenant_id', sa.Integer())],
    'ai_feedbacks': [('tenant_id', sa.Integer())],
    'resources': [('tenant_id', sa.Integer())],
    'training_journals': [('tenant_id', sa.Integer())],
    'classrooms': [('tenant_id', sa.Integer())],
    'classroom_api_usage': [('tenant_id', sa.Integer())],
    'classroom_credit_usage': [('tenant_id', sa.Integer())],
    'classroom_practice_plans': [('tenant_id', sa.Integer())],
    'kb_documents': [('tenant_id', sa.Integer()), ('visibility', sa.String(16), "'public'"),
                     ('source_url', sa.String(500))],
}


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table):
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if 'users' not in _tables():
        raise RuntimeError('Existing LINK schema is missing users; initialize the application schema first.')
    if 'tenants' not in _tables():
        op.create_table('tenants',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('slug', sa.String(80), nullable=False),
            sa.Column('kind', sa.String(24), nullable=False, server_default='personal'),
            sa.Column('status', sa.String(20), nullable=False, server_default='active'),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
        op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True)
        op.create_index('ix_tenants_status', 'tenants', ['status'])
    if 'tenant_memberships' not in _tables():
        op.create_table('tenant_memberships',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('role', sa.String(24), nullable=False, server_default='student'),
            sa.Column('status', sa.String(20), nullable=False, server_default='active'),
            sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_membership'))
        op.create_index('ix_tenant_memberships_tenant_id', 'tenant_memberships', ['tenant_id'])
        op.create_index('ix_tenant_memberships_user_id', 'tenant_memberships', ['user_id'])
        op.create_index('ix_tenant_memberships_status', 'tenant_memberships', ['status'])

    tables = _tables()
    for table, specs in TENANT_COLUMNS.items():
        if table not in tables:
            continue
        names = _columns(table)
        for spec in specs:
            name, kind, *default = spec
            if name not in names:
                op.add_column(table, sa.Column(name, kind, nullable=True,
                                               server_default=default[0] if default else None))
        if table != 'kb_documents':
            op.create_index(f'ix_{table}_tenant_id', table, ['tenant_id'])
        if table != 'kb_documents' and op.get_bind().dialect.name != 'sqlite':
            op.create_foreign_key(f'fk_{table}_tenant_id', table, 'tenants', ['tenant_id'], ['id'])
    if 'kb_documents' in tables:
        # Retain legacy documents as explicitly public corpus entries. New uploads default to tenant scope.
        constraints = sa.inspect(op.get_bind()).get_unique_constraints('kb_documents')
        sha_constraints = [constraint for constraint in constraints
                           if 'sha256' in constraint.get('column_names', [])]
        if op.get_bind().dialect.name == 'sqlite' and sha_constraints:
            with op.batch_alter_table('kb_documents', naming_convention={
                    'uq': 'uq_%(table_name)s_%(column_0_name)s'}) as batch:
                for constraint in sha_constraints:
                    batch.drop_constraint(constraint.get('name') or 'uq_kb_documents_sha256', type_='unique')
                batch.create_unique_constraint('uq_kb_scope_sha',
                    ['tenant_id', 'visibility', 'uploaded_by', 'sha256'])
        else:
            for constraint in sha_constraints:
                op.drop_constraint(constraint['name'], 'kb_documents', type_='unique')
            op.create_unique_constraint('uq_kb_scope_sha', 'kb_documents',
                                        ['tenant_id', 'visibility', 'uploaded_by', 'sha256'])
        if op.get_bind().dialect.name != 'sqlite':
            op.create_foreign_key('fk_kb_documents_tenant_id', 'kb_documents', 'tenants', ['tenant_id'], ['id'])
        op.create_index('ix_kb_documents_tenant_id', 'kb_documents', ['tenant_id'])
        op.create_index('ix_kb_documents_visibility', 'kb_documents', ['visibility'])

    # Each existing account becomes the owner of its own initial workspace; private history stays private.
    bind = op.get_bind()
    users = sa.table('users', sa.column('id', sa.Integer()), sa.column('name', sa.String()),
                     sa.column('role', sa.String()))
    tenants = sa.table('tenants', sa.column('id', sa.Integer()), sa.column('name', sa.String()),
                       sa.column('slug', sa.String()), sa.column('kind', sa.String()),
                       sa.column('status', sa.String()), sa.column('created_by', sa.Integer()),
                       sa.column('created_at', sa.DateTime()))
    memberships = sa.table('tenant_memberships', sa.column('tenant_id', sa.Integer()),
                           sa.column('user_id', sa.Integer()), sa.column('role', sa.String()),
                           sa.column('status', sa.String()), sa.column('joined_at', sa.DateTime()))
    for row in bind.execute(sa.select(users.c.id, users.c.name, users.c.role)).mappings():
        slug = f"legacy-user-{row['id']}"
        tenant_id = bind.execute(sa.select(tenants.c.id).where(tenants.c.slug == slug)).scalar_one_or_none()
        if tenant_id is None:
            bind.execute(tenants.insert().values(name=f"{row['name']}的工作区", slug=slug,
                kind='personal', status='active', created_by=row['id'], created_at=sa.func.now()))
            tenant_id = bind.execute(sa.select(tenants.c.id).where(tenants.c.slug == slug)).scalar_one()
        has_membership = bind.execute(sa.select(memberships.c.tenant_id).where(
            memberships.c.tenant_id == tenant_id, memberships.c.user_id == row['id'])).first()
        if not has_membership:
            bind.execute(memberships.insert().values(tenant_id=tenant_id, user_id=row['id'],
                role=row['role'] if row['role'] in ('teacher', 'student') else 'student',
                status='active', joined_at=sa.func.now()))
        for table in ('training_sessions', 'ai_feedbacks', 'training_journals', 'classrooms',
                      'classroom_practice_plans'):
            if table in tables and 'user_id' in _columns(table):
                bind.execute(sa.text(f'UPDATE {table} SET tenant_id=:tenant WHERE user_id=:user AND tenant_id IS NULL'),
                             {'tenant': tenant_id, 'user': row['id']})
        for table in ('classroom_api_usage', 'classroom_credit_usage'):
            if table in tables and 'session_id' in _columns(table) and 'training_sessions' in tables:
                bind.execute(sa.text(f'''UPDATE {table} SET tenant_id=:tenant WHERE session_id IN
                    (SELECT id FROM training_sessions WHERE user_id=:user) AND tenant_id IS NULL'''),
                             {'tenant': tenant_id, 'user': row['id']})


def downgrade():
    # Tenant ownership is data-bearing; downgrade intentionally refuses destructive removal.
    raise RuntimeError('Tenant migration downgrade would erase ownership metadata; restore a database backup instead.')
