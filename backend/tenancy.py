"""Tenant identity, membership and request-scoped tenant selection.

The tenant ID supplied by a client is only a selector: every selection is checked
against the authenticated user's membership before it is accepted.
"""
from datetime import datetime

import uuid

from flask import Blueprint, abort, g, jsonify, request
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from sqlalchemy import UniqueConstraint

from extensions import db


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(24), nullable=False, default='personal')
    status = db.Column(db.String(20), nullable=False, default='active', index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    memberships = db.relationship('TenantMembership', back_populates='tenant', cascade='all, delete-orphan')

    def to_dict(self, role=None):
        return {'id': self.id, 'name': self.name, 'slug': self.slug, 'kind': self.kind,
                'role': role, 'status': self.status}


class TenantMembership(db.Model):
    __tablename__ = 'tenant_memberships'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(24), nullable=False, default='student')
    status = db.Column(db.String(20), nullable=False, default='active', index=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    tenant = db.relationship('Tenant', back_populates='memberships')
    __table_args__ = (UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_membership'),)


def personal_tenant_for(user, *, commit=False):
    """Return/create an account's initial personal workspace."""
    membership = TenantMembership.query.filter_by(user_id=user.id, status='active').order_by(
        TenantMembership.id).first()
    if membership:
        return membership.tenant
    tenant = Tenant(name=f'{user.name}的工作区', slug=f'user-{user.id}', kind='personal', created_by=user.id)
    db.session.add(tenant)
    db.session.flush()
    db.session.add(TenantMembership(tenant_id=tenant.id, user_id=user.id,
                                    role=user.role if user.role in ('teacher', 'student') else 'student'))
    if commit:
        db.session.commit()
    return tenant


def current_tenant(user=None, *, required=True):
    """Resolve X-Tenant-ID after checking active membership; never trust the header alone."""
    cached = getattr(g, 'active_tenant', None)
    if cached is not None:
        return cached
    if user is None:
        identity = get_jwt_identity()
        if identity is None:
            if required:
                abort(401)
            return None
        from models import User
        user = db.session.get(User, int(identity))
    if user is None:
        if required:
            abort(401)
        return None
    memberships = TenantMembership.query.filter_by(user_id=user.id, status='active').all()
    if not memberships:
        tenant = personal_tenant_for(user, commit=True)
        memberships = TenantMembership.query.filter_by(user_id=user.id, tenant_id=tenant.id,
                                                       status='active').all()
    selected = request.headers.get('X-Tenant-ID')
    if selected:
        try:
            selected_id = int(selected)
        except (TypeError, ValueError):
            abort(400, description='X-Tenant-ID 必须是有效的机构编号')
        membership = next((item for item in memberships if item.tenant_id == selected_id), None)
        if membership is None:
            abort(403, description='你不是该机构的有效成员')
    else:
        membership = memberships[0]
    if membership.tenant.status != 'active':
        abort(403, description='该机构当前不可用')
    g.active_tenant = membership.tenant
    g.active_membership = membership
    return membership.tenant


def tenant_id_for_request(user=None):
    tenant = current_tenant(user)
    return tenant.id


def membership_role(user=None):
    current_tenant(user)
    return g.active_membership.role


def ensure_user_workspaces():
    """Backfill development/demo users created after a clean-schema seed."""
    from models import User, TrainingSession, AiFeedback, TrainingJournal
    from classroom_models import Classroom, PracticePlan, ApiUsage, CreditUsage
    for user in User.query.all():
        tenant = personal_tenant_for(user)
        for model in (TrainingSession, AiFeedback, TrainingJournal, Classroom, PracticePlan):
            model.query.filter_by(user_id=user.id, tenant_id=None).update(
                {'tenant_id': tenant.id}, synchronize_session=False)
        session_ids = db.session.query(TrainingSession.id).filter_by(user_id=user.id).subquery()
        for model in (ApiUsage, CreditUsage):
            model.query.filter(model.session_id.in_(session_ids), model.tenant_id.is_(None)).update(
                {'tenant_id': tenant.id}, synchronize_session=False)
    db.session.commit()


bp = Blueprint('tenants', __name__, url_prefix='/api/tenants')


def _current_user():
    from models import User
    identity = get_jwt_identity()
    return db.session.get(User, int(identity)) if identity is not None else None


@bp.get('')
@jwt_required()
def list_tenants():
    user = _current_user()
    rows = TenantMembership.query.filter_by(user_id=user.id, status='active').order_by(
        TenantMembership.id).all()
    if not rows:
        personal_tenant_for(user, commit=True)
        rows = TenantMembership.query.filter_by(user_id=user.id, status='active').order_by(
            TenantMembership.id).all()
    selected = current_tenant(user).id
    return jsonify(items=[{**row.tenant.to_dict(row.role), 'active': row.tenant_id == selected}
                          for row in rows])


@bp.post('')
@jwt_required()
def create_tenant():
    user = _current_user()
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        return jsonify(message='机构名称必填且不超过120字'), 400
    if TenantMembership.query.filter_by(user_id=user.id, status='active').count() >= 10:
        return jsonify(message='单个账号最多加入10个机构'), 409
    slug = f"org-{uuid.uuid4().hex[:16]}"
    tenant = Tenant(name=name.strip(), slug=slug,
                    kind='school' if data.get('kind') == 'school' else 'organization', created_by=user.id)
    db.session.add(tenant)
    db.session.flush()
    db.session.add(TenantMembership(tenant_id=tenant.id, user_id=user.id, role='owner'))
    db.session.commit()
    return jsonify(tenant=tenant.to_dict('owner')), 201


@bp.post('/<int:tenant_id>/members')
@jwt_required()
def add_member(tenant_id):
    user = _current_user()
    membership = TenantMembership.query.filter_by(tenant_id=tenant_id, user_id=user.id,
                                                   status='active').first()
    if membership is None or membership.role not in ('owner', 'admin'):
        return jsonify(message='只有机构所有者或管理员可以添加成员'), 403
    tenant = db.session.get(Tenant, tenant_id)
    if TenantMembership.query.filter_by(tenant_id=tenant_id, status='active').count() >= 100:
        return jsonify(message='试点机构当前最多支持100名成员'), 409
    data = request.get_json(silent=True) or {}
    account = data.get('account')
    role = data.get('role', 'student')
    if not isinstance(account, str) or role not in ('teacher', 'student', 'admin'):
        return jsonify(message='请提供已注册账号及有效机构角色'), 400
    from models import User
    invitee = User.query.filter_by(account=account.strip()).first()
    if invitee is None:
        return jsonify(message='请先让成员注册 LINK 账号，再添加到机构'), 404
    existing = TenantMembership.query.filter_by(tenant_id=tenant_id, user_id=invitee.id).first()
    if existing and existing.status == 'active':
        return jsonify(message='该账号已经是机构成员'), 409
    if existing:
        existing.role, existing.status = role, 'active'
    else:
        db.session.add(TenantMembership(tenant_id=tenant_id, user_id=invitee.id, role=role))
    db.session.commit()
    return jsonify(member={'account': invitee.account, 'name': invitee.name, 'role': role}), 201


@bp.get('/<int:tenant_id>/members')
@jwt_required()
def list_members(tenant_id):
    actor = _current_user()
    membership = TenantMembership.query.filter_by(tenant_id=tenant_id, user_id=actor.id,
                                                   status='active').first()
    if membership is None or membership.role not in ('owner', 'admin'):
        return jsonify(message='只有机构所有者或管理员可以查看成员目录'), 403
    from models import User
    rows = (db.session.query(TenantMembership, User)
            .join(User, TenantMembership.user_id == User.id)
            .filter(TenantMembership.tenant_id == tenant_id, TenantMembership.status == 'active')
            .order_by(TenantMembership.id).all())
    return jsonify(items=[{'user_id': member.user_id, 'account': user.account,
                           'name': user.name, 'role': member.role,
                           'joined_at': member.joined_at.isoformat()} for member, user in rows])


@bp.delete('/<int:tenant_id>/members/<int:user_id>')
@jwt_required()
def remove_member(tenant_id, user_id):
    actor = _current_user()
    owner = TenantMembership.query.filter_by(tenant_id=tenant_id, user_id=actor.id,
                                             status='active').first()
    target = TenantMembership.query.filter_by(tenant_id=tenant_id, user_id=user_id,
                                              status='active').first()
    if owner is None or owner.role not in ('owner', 'admin') or target is None:
        return jsonify(message='无权移除该机构成员'), 403
    if target.role == 'owner':
        return jsonify(message='请先移交机构所有权'), 409
    target.status = 'removed'
    db.session.commit()
    return jsonify(message='成员已移出机构')
