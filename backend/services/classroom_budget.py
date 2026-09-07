"""Single-process reservation ledger. Unknown/failed requests retain their reserve."""
import os
import threading
from sqlalchemy import func
from extensions import db
from classroom_models import ApiUsage

lock = threading.RLock()


def status():
    total = float(db.session.query(func.coalesce(func.sum(
        func.coalesce(ApiUsage.charged_cny, ApiUsage.reserved_cny)), 0)).scalar())
    return {'spent_and_reserved_cny': round(total, 4), 'warning': total >= 80,
            'stopped': total >= 90, 'limit_cny': 100, 'stop_cny': 90,
            'pricing_confirmed': os.getenv('AI_PRICING_CONFIRMED', '').lower() == 'true'}


def reserve(service, amount, session_id=None):
    if not status()['pricing_confirmed']:
        raise ValueError('请先核对云服务单价并配置 AI_PRICING_CONFIRMED=true')
    with lock:
        if amount <= 0 or status()['spent_and_reserved_cny'] + amount >= 90:
            raise ValueError('调用预算已到停止阈值，本次未发起云请求')
        row = ApiUsage(service=service, session_id=session_id, reserved_cny=amount)
        db.session.add(row)
        db.session.commit()
        return row.id


def settle(usage_id, charge, units):
    with lock:
        row = db.session.get(ApiUsage, usage_id)
        row.charged_cny = max(0, float(charge))
        row.units = units
        row.state = 'settled'
        db.session.commit()


def price(name):
    value = float(os.getenv(name, '0'))
    if not 0 < value < 10000:
        raise ValueError(f'请配置有效单价 {name}')
    return value
