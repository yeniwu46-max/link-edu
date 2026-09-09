"""Text-only generation in an isolated app, preserving the existing test ledger."""
from copy import deepcopy
import os
import secrets
import tempfile
from unittest.mock import patch
from evals.dataset import ROOT, fingerprint


def validate_generation_config(limit):
    # This is the only existing dedicated test account; DeepSeek's default key is not one.
    from services.classroom_providers import llm_provider, key, model
    from services.classroom_budget import price
    if llm_provider() != 'openai_next':
        raise ValueError('generate 首版要求 CLASSROOM_LLM_PROVIDER=openai_next 的独立测试账户')
    key('OPENAI_NEXT_TEST_API_KEY')
    if os.getenv('OPENAI_NEXT_PRICING_CONFIRMED', '').lower() != 'true':
        raise ValueError('须先核对 OPENAI_NEXT_PRICING_CONFIRMED 和测试模型单价')
    if model('dialogue') != 'deepseek-v4-flash':
        raise ValueError('文本生成测试通道仅核验了 deepseek-v4-flash')
    if os.getenv('OPENAI_NEXT_BASE_URL', 'https://api.openai-next.com/v1').rstrip('/') != 'https://api.openai-next.com/v1':
        raise ValueError('测试通道端点无效')
    price('OPENAI_NEXT_DIALOGUE_INPUT_USD_PER_MILLION')
    price('OPENAI_NEXT_DIALOGUE_OUTPUT_USD_PER_MILLION')
    from evals.judge import positive
    positive(limit)


def generate_case(case, *, paid=False):
    if not paid:
        raise ValueError('generate 须显式 --paid')
    from services.classroom_runtime import STUDENT_SYSTEM, STUDENTS
    from services.classroom_dialogue_stream import chat_stream
    from services.classroom_stream import StreamControl
    from services.classroom_reports import REPORT_SYSTEM
    from services.classroom_motion import motion_evidence
    from services.classroom_providers import chat
    if case['kind'] == 'report':
        return chat(REPORT_SYSTEM, {'events': case['events'], 'references': case['references'],
                    'motion_evidence': motion_evidence(case['events']),
                    'teacher_objection': case['teacher_objection']}, max_tokens=4000, test=True)
    payload = deepcopy(case['payload'])
    payload['students'] = STUDENTS
    return chat_stream(STUDENT_SYSTEM, payload, None, StreamControl(), lambda draft: None)


def generate_records(cases, directory, limit, *, paid=False):
    if not paid:
        raise ValueError('generate 须显式 --paid')
    validate_generation_config(limit)
    from flask import Flask
    from config import Config
    from extensions import db
    from services import classroom_credits as credits
    from services.classroom_providers import model
    from services.classroom_budget import price
    from evals.judge import Budget, BudgetExceeded
    from evals.runner import write_json
    from services.classroom_runtime import STUDENT_SYSTEM
    from services.classroom_reports import REPORT_SYSTEM
    budget = Budget(limit, lambda entries: write_json(directory / 'generator-budget.json', entries))
    # Only the existing CreditUsage ledger is touched in this app; no create_all/seed here.
    ledger_app = Flask('eval_ledger', root_path=str(ROOT / 'backend'), instance_path=str(ROOT / 'backend/instance'))
    ledger_app.config.from_object(Config)
    db.init_app(ledger_app)
    with ledger_app.app_context():
        ledger_engine = db.engine
    original_reserve, original_settle = credits.reserve, credits.settle
    reservations, records = {}, []
    exhausted = False
    def reserve(account, service, selected_model, amount, session_id=None):
        if account != 'test' or session_id is not None:
            raise ValueError('离线生成只允许测试账户且不绑定真实场次')
        local_id = budget.reserve(amount)
        usage_id = original_reserve(account, service, selected_model, amount, None)
        reservations[usage_id] = local_id
        return usage_id
    def settle(usage_id, charge, units):
        original_settle(usage_id, charge, units)
        budget.settle(reservations[usage_id], units, price('OPENAI_NEXT_DIALOGUE_INPUT_USD_PER_MILLION'),
                      price('OPENAI_NEXT_DIALOGUE_OUTPUT_USD_PER_MILLION'))
    try:
        with tempfile.TemporaryDirectory(prefix='classroom-eval-') as temp:
            app = Flask('offline_eval', instance_path=temp)
            app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///' + temp.replace('\\', '/') + '/eval.db',
                              SQLALCHEMY_TRACK_MODIFICATIONS=False, JWT_SECRET_KEY=secrets.token_hex(32),
                              CLASSROOM_API_PROFILE='test', OPENAI_NEXT_LEDGER_ENGINE=ledger_engine)
            db.init_app(app)
            with app.app_context(), patch.object(credits, 'reserve', reserve), patch.object(credits, 'settle', settle):
                db.create_all()  # Isolated, disposable business database only.
                try:
                    for case in cases:
                        if not case['examples']:
                            continue
                        record = {'case_id': case['id'], 'variant': 'generated', 'generator_model': model('dialogue'),
                                  'generation_prompt_hash': fingerprint(REPORT_SYSTEM if case['kind'] == 'report' else STUDENT_SYSTEM),
                                  'review_status': 'pending_human_review', 'output': None}
                        try:
                            if exhausted:
                                raise BudgetExceeded('预算不足')
                            record['output'] = generate_case(case, paid=True)
                        except BudgetExceeded:
                            exhausted = True
                            record['generation_error'] = '本次生成预算不足，后续请求已停止'
                        except Exception as exc:
                            # Stop the generation batch on provider/ledger errors; never retry silently.
                            exhausted = True
                            record['generation_error'] = '生成或测试账本异常：' + type(exc).__name__
                        records.append(record)
                        write_json(directory / 'generation-checkpoint.json', records)
                finally:
                    db.session.remove()
                    db.engine.dispose()
    finally:
        ledger_engine.dispose()
    return records, {'ceiling': budget.ceiling, 'spent_and_reserved': budget.total}
