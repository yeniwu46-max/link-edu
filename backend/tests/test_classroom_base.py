import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from app import create_app
from extensions import db
from services.classroom_budget import reserve, settle, status


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv('AI_PRICING_CONFIRMED', 'true')
    class Config:
        TESTING = True
        # File-backed connections match the real threaded report worker. In-memory
        # SQLite shares one connection and lets another thread roll back a test's transaction.
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{tmp_path / "test.db"}'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        JWT_SECRET_KEY = 'test-secret-at-least-thirty-two-characters'
    app = create_app(Config)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_budget_reserves_inflight_and_keeps_unknown(app):
    first = reserve('llm', 30)
    reserve('asr', 40)
    with pytest.raises(ValueError):
        reserve('tts', 20)
    settle(first, 1, {'tokens': 50})
    assert status()['spent_and_reserved_cny'] == 41


def test_unconfirmed_price_blocks_cloud(app, monkeypatch):
    monkeypatch.delenv('AI_PRICING_CONFIRMED')
    with pytest.raises(ValueError):
        reserve('llm', 1)
