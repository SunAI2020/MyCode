# -*- coding: utf-8 -*-
"""auth_rbac 认证与 RBAC 单元测试"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth_rbac
from auth_rbac import hash_password, verify_password, generate_token, verify_token, has_permission, ROLES


class TestPasswordHash:
    def test_hash_and_verify(self):
        h = hash_password('S3cret!pass')
        assert h.startswith('pbkdf2_sha256$')
        assert verify_password('S3cret!pass', h)
        assert not verify_password('wrong', h)

    def test_hash_unique_per_call(self):
        assert hash_password('same') != hash_password('same')

    def test_verify_garbage_returns_false(self):
        assert not verify_password('x', 'not-a-valid-hash')
        assert not verify_password('x', '')


class TestToken:
    def test_generate_and_verify(self):
        token = generate_token('alice', 'analyst')
        payload = verify_token(token)
        assert payload is not None
        assert payload['sub'] == 'alice'
        assert payload['role'] == 'analyst'
        assert payload['exp'] > payload['iat']

    def test_wrong_secret_rejected(self):
        token = generate_token('alice', 'analyst', secret='secret-a')
        assert verify_token(token, secret='secret-b') is None

    def test_expired_token_rejected(self):
        token = generate_token('alice', 'analyst', ttl_seconds=-10)
        assert verify_token(token) is None

    def test_garbage_token_rejected(self):
        assert verify_token('garbage.token.here') is None
        assert verify_token('') is None


class TestRBAC:
    def test_roles_defined(self):
        assert set(ROLES.keys()) >= {'admin', 'analyst', 'auditor', 'viewer'}

    def test_admin_has_all(self):
        assert has_permission('admin', 'anything.at.all')

    def test_viewer_readonly(self):
        assert has_permission('viewer', 'scan:read')
        assert not has_permission('viewer', 'scan:write')
        assert not has_permission('viewer', 'workflow:write')

    def test_analyst_scan(self):
        assert has_permission('analyst', 'web:scan')
        assert has_permission('analyst', 'weakpass:scan')
        assert has_permission('analyst', 'workflow:write')

    def test_unknown_role_no_permission(self):
        assert not has_permission('hacker', 'scan:read')


class TestUserDB:
    def test_seeded_admin_exists(self, db):
        admin = db.get_user_by_username('admin')
        assert admin is not None
        assert admin['role'] == 'admin'
        assert verify_password('admin123', admin['password_hash'])
        assert admin['must_change_password'] == 1

    def test_create_user(self, db):
        uid = db.create_user('bob', hash_password('bobpass'), role='analyst',
                             email='bob@example.com', full_name='Bob')
        assert uid > 0
        u = db.get_user_by_username('bob')
        assert u['role'] == 'analyst'
        assert verify_password('bobpass', u['password_hash'])

    def test_create_duplicate_username(self, db):
        db.create_user('carol', hash_password('x'), role='viewer')
        assert db.create_user('carol', hash_password('y'), role='viewer') == -1

    def test_update_user_role(self, db):
        uid = db.create_user('dave', hash_password('x'), role='viewer')
        db.update_user(uid, role='auditor')
        assert db.get_user(uid)['role'] == 'auditor'

    def test_roles_seeded(self, db):
        roles = db.get_roles()
        names = {r['name'] for r in roles}
        assert 'admin' in names and 'viewer' in names
