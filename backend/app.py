from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from extensions import db, jwt
from routes import auth_bp, content_bp, dashboard_bp
from seed import ensure_demo_catalog, seed_if_empty
import classroom_models


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if app.config.get('PUBLIC_DEPLOYMENT'):
        secret = app.config.get('JWT_SECRET_KEY', '')
        if len(secret) < 40 or not app.config.get('PUBLIC_ORIGINS') or app.config.get('SEED_ON_STARTUP'):
            raise RuntimeError('公网部署必须配置强JWT密钥、PUBLIC_ORIGINS并关闭SEED_ON_STARTUP')
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
        CORS(app, origins=app.config['PUBLIC_ORIGINS'])
    else:
        CORS(app)
    from services.public_access import install_policy
    install_policy(app)

    db.init_app(app)
    jwt.init_app(app)

    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_payload):
        return jsonify(message='登录状态已失效，请重新登录', code='token_expired'), 401

    @jwt.invalid_token_loader
    def invalid_token(_reason):
        return jsonify(message='登录状态无效，请重新登录', code='token_invalid'), 401

    @jwt.unauthorized_loader
    def missing_token(_reason):
        return jsonify(message='请先登录', code='token_missing'), 401

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', version='competition-20260914')

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(content_bp)
    from classroom_routes import register_classroom
    register_classroom(app)

    @app.before_request
    def classroom_single_process():
        if not app.config.get('TESTING'):
            from services.classroom_locks import claim_server
            try:
                claim_server()
            except ValueError as error:
                return jsonify(message=str(error)), 503

    return app


app = create_app()


def _ensure_columns():
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    specs = [
        ('ai_feedbacks', 'report_json', 'TEXT'),
        ('users', 'bio', 'TEXT'),
        ('users', 'school', 'VARCHAR(128)'),
        ('users', 'major', 'VARCHAR(128)'),
        ('users', 'grade', 'VARCHAR(32)'),
        ('users', 'level', 'INTEGER'),
        ('users', 'xp', 'INTEGER'),
        ('users', 'badges_json', 'TEXT'),
        ('courses', 'stage', 'VARCHAR(32)'),
        ('courses', 'outline', 'TEXT'),
        ('courses', 'source', 'VARCHAR(128)'),
        ('courses', 'source_url', 'VARCHAR(255)'),
    ]
    tables = set(inspector.get_table_names())
    for table, column, ddl in specs:
        if table not in tables:
            continue
        names = {item['name'] for item in inspector.get_columns(table)}
        if column in names:
            continue
        db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'))
    db.session.commit()


def init_db():
    with app.app_context():
        db.create_all()
        _ensure_columns()
        if app.config.get('SEED_ON_STARTUP'):
            seed_if_empty()
            ensure_demo_catalog()


if __name__ == '__main__':
    from services.classroom_locks import claim_server
    claim_server()
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=False)
