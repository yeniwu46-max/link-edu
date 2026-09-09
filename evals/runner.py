"""Local dataset/rules runner. Importing this module does not import DeepEval or app."""
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from evals.dataset import ROOT, fingerprint, load_dataset
from evals.rules import inspect_output


def write_json(path, value):
    # Atomic artifact replacement; no business files are written.
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def summarize(rows):
    counts = Counter(r['status'] for r in rows)
    result = {s: counts[s] for s in ('pass', 'fail', 'error', 'not_evaluated', 'not_applicable')}
    result.update(total=len(rows), judged=counts['pass'] + counts['fail'])
    result['pass_rate'] = counts['pass'] / result['judged'] if result['judged'] else None
    return result


def compare_runs(current, baseline):
    keys = ('dataset_hash', 'rules_hash', 'judge_model')
    mismatch = [key for key in keys if not current.get(key) or current.get(key) != baseline.get(key)]
    # Two offline runs without a Judge remain comparable.
    if current.get('judge_model') is None and baseline.get('judge_model') is None:
        mismatch = [k for k in mismatch if k != 'judge_model']
    if current.get('judge_identity') != baseline.get('judge_identity'):
        mismatch.append('judge_identity')
    if mismatch:
        return {'comparable': False, 'reason': '版本或 Judge 不一致：' + ', '.join(mismatch), 'changes': []}
    def indexed(run):
        return {(r['case_id'], r['variant'], r['stage'], r['metric']): r['status'] for r in run['results']}
    before, after = indexed(baseline), indexed(current)
    changes = [{'case_id': k[0], 'variant': k[1], 'stage': k[2], 'metric': k[3],
                'before': before.get(k, 'not_evaluated'), 'after': after.get(k, 'not_evaluated')}
               for k in sorted(before.keys() | after.keys()) if before.get(k) != after.get(k)]
    return {'comparable': True, 'changes': changes}


def load_records(path, dataset):
    if path is None:
        return [{'case_id': c['id'], 'variant': e['variant'], 'output': e['output'],
                 'generator_model': 'authored_synthetic', 'generation_prompt_hash': None,
                 'review_status': e['review_status'], 'label': e['label']}
                for c in dataset['cases'] for e in c['examples']]
    bundle = json.loads(Path(path).read_text(encoding='utf-8'))
    if bundle.get('dataset_hash') != dataset['hash']:
        raise ValueError('回放数据版本不一致，请按当前用例上下文重新导出')
    if bundle.get('provenance') not in ('synthetic', 'anonymized'):
        raise ValueError('回放必须声明 synthetic 或 anonymized 来源')
    known = {c['id'] for c in dataset['cases'] if c['examples']}
    records, seen = bundle.get('records'), set()
    if not isinstance(records, list) or not records:
        raise ValueError('回放 records 必须为非空数组')
    for record in records:
        if not isinstance(record, dict) or record.get('case_id') not in known:
            raise ValueError('回放场景编号未知或不支持模型评测')
        variant = record.get('variant')
        if not isinstance(variant, str) or not variant.strip() or len(variant) > 80:
            raise ValueError('回放 variant 必须为1–80字字符串')
        key = (record['case_id'], variant)
        if key in seen:
            raise ValueError('回放 case_id + variant 重复')
        seen.add(key)
        if 'output' not in record:
            if 'raw_output' not in record:
                raise ValueError('回放记录缺少 output')
            record['output'] = record['raw_output']
        record.setdefault('generator_model', 'unknown')
        record.setdefault('generation_prompt_hash', None)
        if not isinstance(record['generator_model'], str):
            raise ValueError('generator_model 必须为字符串')
    return records


def code_checks(cases, output):
    nodes = sorted({f'backend/tests/{n}' for c in cases for n in c['test_nodes']})
    xml = output / 'tests.xml'
    env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONUTF8': '1',
           'DEEPEVAL_TELEMETRY_OPT_OUT': 'YES', 'DEEPEVAL_UPDATE_WARNING_OPT_IN': '0'}
    process = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'evals.offline_guard',
                              'evals/tests/test_dataset.py', *nodes, '-q', f'--junitxml={xml}'],
                             cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', timeout=180)
    (output / 'tests.txt').write_text(process.stdout + process.stderr, encoding='utf-8')
    tests = list(ET.parse(xml).iter('testcase')) if xml.exists() else []
    rows = []
    for case in cases:
        for node in case['test_nodes']:
            filename, name = node.split('::')
            matching = [t for t in tests if t.get('name', '').split('[')[0] == name and
                        t.get('classname', '').endswith(filename[:-3])]
            status = 'pass' if matching else 'error'
            if any(t.find('error') is not None for t in matching):
                status = 'error'
            elif any(t.find('failure') is not None for t in matching):
                status = 'fail'
            elif any(t.find('skipped') is not None for t in matching):
                status = 'not_evaluated'
            rows.append({'case_id': case['id'], 'variant': 'contract', 'stage': 'code',
                         'metric': node, 'status': status, 'reason': '局部代码契约测试；不代表完整链路验收'})
    rows.append({'case_id': 'HARNESS', 'variant': 'contract', 'stage': 'code', 'metric': 'test_suite',
                 'status': 'pass' if process.returncode == 0 else 'error', 'reason': '详见 tests.txt'})
    return rows


def save_report(directory, report):
    report['summary'] = summarize(report['results'])
    report['by_stage'] = {stage: summarize([r for r in report['results'] if r['stage'] == stage])
                          for stage in sorted({r['stage'] for r in report['results']})}
    write_json(directory / 'results.json', report)
    lines = ['# 离线课堂评测', '', f'运行：{report["run_id"]} · 模式：{report["mode"]}', '',
             '合成标签待人工复核；规则测试、语义评审和真实课堂验收互不替代。', '',
             f'Judge：{report["judge_model"] or "未调用"}；生成模型：{", ".join(report["generator_models"]) or "未调用"}', '',
             '| 阶段 | 通过 | 失败 | 错误 | 未评估 | 不适用 | 总数 | 已判定分母 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for stage, count in report['by_stage'].items():
        lines.append(f'| {stage} | ' + ' | '.join(str(count[k]) for k in
                     ('pass', 'fail', 'error', 'not_evaluated', 'not_applicable', 'total', 'judged')) + ' |')
    lines += ['', '通过率仅以通过＋失败为分母；错误和未评估必须同时查看。', '',
              f'耗时：{report.get("seconds", 0)} 秒；费用及在途预留（USD）：{json.dumps(report.get("costs", {}), ensure_ascii=False)}', '',
              '## 问题与未评估项', '']
    for row in report['results']:
        if row['status'] in ('fail', 'error', 'not_evaluated'):
            reason = str(row.get('reason', '')).replace('\n', ' ').replace('<', '&lt;')
            lines.append(f'- {row["case_id"]}/{row["variant"]}/{row["stage"]}/{row["metric"]}: {row["status"]} — {reason}')
    comparison = report.get('comparison')
    if comparison:
        lines += ['', '## 基线对比', '', '可直接比较' if comparison['comparable'] else comparison['reason']]
        for item in comparison['changes']:
            lines.append(f'- {item["case_id"]}/{item["variant"]}/{item["stage"]}/{item["metric"]}: {item["before"]} → {item["after"]}')
    (directory / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def run(mode='check', *, output_root=None, input_path=None, baseline=None, case_ids=None,
        paid=False, judge_limit=None, generator_limit=None):
    if mode not in ('check', 'replay', 'generate'):
        raise ValueError('未知评测模式')
    if mode == 'generate' and not paid:
        raise ValueError('generate 须显式 --paid')
    if mode == 'check' and paid:
        raise ValueError('check 模式禁止 --paid')
    data = load_dataset()
    selected = set(case_ids or [c['id'] for c in data['cases']])
    if selected - {c['id'] for c in data['cases']}:
        raise ValueError('未知场景编号')
    cases = [c for c in data['cases'] if c['id'] in selected]
    model, judge_budget = None, None
    if paid:
        from evals.judge import Budget, JudgeConfig, JudgeModel
        judge_budget = Budget(judge_limit)
        model = JudgeModel(JudgeConfig.from_env(), judge_budget, paid=True)
    # All config checks precede paid requests; generation never borrows dialogue keys.
    if mode == 'generate':
        from evals.generation import validate_generation_config
        validate_generation_config(generator_limit)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:10]
    directory = Path(output_root or ROOT / 'artifacts/private/classroom-eval') / run_id
    directory.mkdir(parents=True, exist_ok=False)
    if judge_budget:
        judge_budget.checkpoint = lambda entries: write_json(directory / 'judge-budget.json', entries)
    from services.classroom_runtime import STUDENT_SYSTEM, STUDENTS
    from services.classroom_reports import REPORT_SYSTEM
    rules_hash = fingerprint({p: (ROOT / 'evals' / p).read_text(encoding='utf-8')
                              for p in ('judge.py', 'rules.py', 'runner.py', 'generation.py')})
    report = {'run_id': run_id, 'mode': mode, 'dataset_version': data['version'], 'dataset_hash': data['hash'],
              'rules_hash': rules_hash, 'provenance': 'synthetic', 'review_status': 'pending_human_review',
              'prompt_hashes': {'student': fingerprint(STUDENT_SYSTEM), 'report': fingerprint(REPORT_SYSTEM)},
              'judge_model': model.get_model_name() if model else None, 'generator_models': [], 'records': [], 'results': [],
              'judge_identity': fingerprint([model.config.base_url, model.config.model]) if model else None,
              'rule_version': '1.0.0', 'costs': {}, 'independent_validation_claimed': False}
    try:
        report['deepeval_version'] = importlib.metadata.version('deepeval')
    except importlib.metadata.PackageNotFoundError:
        report['deepeval_version'] = None
    started = time.monotonic()
    if mode == 'check':
        report['results'] += code_checks(cases, directory)
        records = []
    elif mode == 'generate':
        from evals.generation import generate_records
        records, report['costs']['generator'] = generate_records(cases, directory, generator_limit, paid=paid)
    else:
        records = load_records(input_path, data)
        if input_path:
            report['provenance'] = json.loads(Path(input_path).read_text(encoding='utf-8'))['provenance']
    by_id = {c['id']: c for c in cases}
    for record in records:
        if record['case_id'] not in by_id:
            continue
        case = by_id[record['case_id']]
        case['payload']['students'] = STUDENTS
        detail = inspect_output(case, record['output'])
        report['records'].append({**record, **detail})
        common = {'case_id': case['id'], 'variant': record['variant']}
        if record.get('generation_error'):
            report['results'].append({**common, 'stage': 'generation', 'metric': 'provider',
                                      'status': 'error', 'reason': record['generation_error']})
        for name, passed in detail['checks'].items():
            report['results'].append({**common, 'stage': 'code', 'metric': name, 'status': 'pass' if passed else 'fail'})
        stages = [('raw', detail['raw_output'])]
        if case['kind'] == 'report':
            stages.append(('validated', detail['validated_output']))
        for stage, output in stages:
            if model and output is not None and not record.get('generation_error'):
                from evals.judge import judge_case
                rows = judge_case(case, output, model)
            else:
                rows = [{'metric': name, 'status': 'not_evaluated', 'reason': '未启用付费 Judge 或缺少有效输出'}
                        for name in case['metrics']]
            report['results'] += [{**common, 'stage': stage, **r} for r in rows]
        report['generator_models'] = sorted({r['generator_model'] for r in report['records']})
        if judge_budget:
            report['costs']['judge'] = {'ceiling': judge_budget.ceiling, 'spent_and_reserved': judge_budget.total}
        save_report(directory, report)
    evaluated = {r['case_id'] for r in report['records']}
    for case in cases:
        if case['id'] not in evaluated and case['metrics']:
            report['results'] += [{'case_id': case['id'], 'variant': 'coverage', 'stage': 'raw', 'metric': name,
                                  'status': 'not_evaluated', 'reason': '本次未提供模型输出'} for name in case['metrics']]
        if case['manual']:
            report['results'].append({'case_id': case['id'], 'variant': 'coverage', 'stage': 'manual',
                                      'metric': 'end_to_end', 'status': 'not_evaluated', 'reason': case['manual']})
        if mode != 'check' and case['test_nodes']:
            report['results'].append({'case_id': case['id'], 'variant': 'coverage', 'stage': 'code',
                                      'metric': 'contracts', 'status': 'not_evaluated', 'reason': '请运行 check 执行代码契约测试'})
    report['seconds'] = round(time.monotonic() - started, 3)
    if baseline:
        report['comparison'] = compare_runs(report, json.loads(Path(baseline).read_text(encoding='utf-8')))
    save_report(directory, report)
    return report
