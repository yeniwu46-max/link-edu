"""Additional release spending cap, preserving both original currency ledgers.

Run local validation with 70 CNY and public release with 30 CNY. A fixed, persisted
UTC start timestamp bounds new spend; never change it on restart or clear ledgers.
USD_CNY_BUDGET_RATE is a conservative budget conversion, not a quoted FX rate.
"""
import math
import os
from datetime import datetime
from sqlalchemy import select, func
from classroom_models import ApiUsage, CreditUsage


def config():
    value = os.getenv('DELIVERY_BUDGET_CNY', '')
    if not value:
        return None
    limit = float(value)
    rate = float(os.getenv('USD_CNY_BUDGET_RATE', '8'))
    start = datetime.fromisoformat(os.environ['DELIVERY_BUDGET_START'])
    if not math.isfinite(limit) or not 0 < limit <= 100 or not math.isfinite(rate) or rate < 1:
        raise ValueError('发布预算配置无效')
    return limit, rate, start


def total(connection, settings):
    _, rate, start = settings
    values = []
    for model, charged, reserved in [(ApiUsage, ApiUsage.charged_cny, ApiUsage.reserved_cny),
                                     (CreditUsage, CreditUsage.charged_usd, CreditUsage.reserved_usd)]:
        values.append(float(connection.execute(select(func.coalesce(func.sum(
            func.coalesce(charged, reserved)), 0)).where(model.created_at >= start)).scalar()))
    return values[0] + values[1] * rate


def check(connection, amount, currency='CNY'):
    settings = config()
    if settings and total(connection, settings) + amount * (settings[1] if currency == 'USD' else 1) > settings[0] * .9:
        raise ValueError('本轮体验预算已到停止线；已有报告仍可查看')


def status(connection):
    settings = config()
    if not settings:
        return None
    spent = total(connection, settings)
    return {'limit_cny': settings[0], 'spent_and_reserved_cny': round(spent, 4),
            'stopped': spent >= settings[0] * .9, 'warning': spent >= settings[0] * .8,
            'conversion_upper_cny_per_usd': settings[1]}
