"""Per-purpose USD budgets, with the same cross-process lock as the CNY ledger."""
import math
import os
from flask import current_app
from sqlalchemy import func, select
from extensions import db
from classroom_models import CreditUsage
from services.classroom_locks import budget_file_lock

ACCOUNTS = {'dialogue': ('模拟授课 / 评课', 30), 'vision': ('视觉', 40), 'test': ('测试', 30)}


def engine():
    # Isolated paid test apps share the main USD ledger, including in worker threads.
    return current_app.config.get('OPENAI_NEXT_LEDGER_ENGINE', db.engine)


def limit(account):
    if account not in ACCOUNTS:
        raise ValueError('未知美元预算用途')
    try:
        amount = float(os.getenv(f'OPENAI_NEXT_{account.upper()}_LIMIT_USD', ACCOUNTS[account][1]))
    except ValueError:
        raise ValueError('美元额度必须为有效非负数') from None
    if not math.isfinite(amount) or amount < 0:
        raise ValueError('美元额度必须为有效非负数')
    return amount


def total_query(account):
    return select(func.coalesce(func.sum(func.coalesce(
        CreditUsage.charged_usd, CreditUsage.reserved_usd)), 0)).where(CreditUsage.account == account)


def status():
    accounts = {}
    with engine().connect() as connection:
        for account, (label, _) in ACCOUNTS.items():
            total = float(connection.execute(total_query(account)).scalar())
            ceiling = limit(account)
            accounts[account] = {'label': label, 'limit_usd': ceiling, 'stop_usd': ceiling * .9,
                'spent_and_reserved_usd': round(total, 6), 'warning': total >= ceiling * .8,
                'stopped': total >= ceiling * .9}
    return {'currency': 'USD', 'accounts': accounts,
            'limit_usd': sum(a['limit_usd'] for a in accounts.values()),
            'spent_and_reserved_usd': round(sum(a['spent_and_reserved_usd'] for a in accounts.values()), 6),
            'pricing_confirmed': os.getenv('OPENAI_NEXT_PRICING_CONFIRMED', '').lower() == 'true'}


def reserve(account, service, model, amount, session_id=None):
    if os.getenv('OPENAI_NEXT_PRICING_CONFIRMED', '').lower() != 'true':
        raise ValueError('请先核对 OpenAI Next 美元单价并配置 OPENAI_NEXT_PRICING_CONFIRMED=true')
    ceiling = limit(account)
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError('美元预算预留无效')
    with budget_file_lock(), engine().begin() as connection:
        total = float(connection.execute(total_query(account)).scalar())
        if total + amount >= ceiling * .9:
            raise ValueError(f'{ACCOUNTS[account][0]}美元预算达到90%停止线，本次未发起云请求')
        from services.delivery_budget import check
        check(connection, amount, 'USD')
        result = connection.execute(CreditUsage.__table__.insert().values(account=account,
            service=service, model=model, session_id=session_id, reserved_usd=amount))
        return result.inserted_primary_key[0]


def settle(usage_id, charge, units):
    if not math.isfinite(charge) or charge < 0:
        raise ValueError('美元用量无效，保留原预留')
    with budget_file_lock(), engine().begin() as connection:
        connection.execute(CreditUsage.__table__.update().where(CreditUsage.id == usage_id).values(
            charged_usd=charge, units=units, state='settled'))
