"""Single-process reservation ledger. Unknown/failed requests retain their reserve."""
import os
import math
import threading
from sqlalchemy import func, select
from extensions import db
from classroom_models import ApiUsage
from services.classroom_locks import budget_file_lock

lock = threading.RLock()


def status():
    total = float(db.session.query(func.coalesce(func.sum(
        func.coalesce(ApiUsage.charged_cny, ApiUsage.reserved_cny)), 0)).scalar())
    result = {'spent_and_reserved_cny': round(total, 4), 'warning': total >= 80,
            'stopped': total >= 90, 'limit_cny': 100, 'stop_cny': 90,
            'pricing_confirmed': os.getenv('AI_PRICING_CONFIRMED', '').lower() == 'true'}
    if os.getenv('CLASSROOM_LLM_PROVIDER', '').lower() == 'openai_next':
        from services.classroom_credits import status as credit_status
        result['credits'] = credit_status()
        result['pricing_confirmed'] = result['pricing_confirmed'] and result['credits']['pricing_confirmed']
        result['stopped'] = result['stopped'] or result['credits']['accounts']['dialogue']['stopped']
        result['warning'] = result['warning'] or any(a['warning'] for a in result['credits']['accounts'].values())
    from services import delivery_budget
    with db.engine.connect() as connection:
        release = delivery_budget.status(connection)
    if release:
        result['release'] = release
        result['stopped'] = result['stopped'] or release['stopped']
        result['warning'] = result['warning'] or release['warning']
    return result


def reserve(service, amount, session_id=None):
    if os.getenv('AI_PRICING_CONFIRMED', '').lower() != 'true':
        raise ValueError('请先核对云服务单价并配置 AI_PRICING_CONFIRMED=true')
    with lock, budget_file_lock():
        # A fresh transaction avoids a stale snapshot from the caller's earlier reads.
        with db.engine.begin() as connection:
            total = float(connection.execute(select(func.coalesce(func.sum(
                func.coalesce(ApiUsage.charged_cny, ApiUsage.reserved_cny)), 0))).scalar())
            if not math.isfinite(amount) or amount <= 0 or total + amount >= 90:
                raise ValueError('调用预算已到停止阈值，本次未发起云请求')
            from services.delivery_budget import check
            check(connection, amount)
            result = connection.execute(ApiUsage.__table__.insert().values(
                service=service, session_id=session_id, reserved_cny=amount))
            return result.inserted_primary_key[0]


def settle(usage_id, charge, units):
    if not math.isfinite(charge) or charge < 0:
        raise ValueError('人民币用量无效，保留原预留')
    with lock, budget_file_lock():
        with db.engine.begin() as connection:
            connection.execute(ApiUsage.__table__.update().where(ApiUsage.id == usage_id).values(
                charged_cny=max(0, float(charge)), units=units, state='settled'))


def price(name):
    try:
        value = float(os.getenv(name, '0'))
    except ValueError:
        raise ValueError(f'请配置有效单价 {name}') from None
    if not 0 < value < 10000:
        raise ValueError(f'请配置有效单价 {name}')
    return value
