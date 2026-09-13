# -*- coding: utf-8 -*-
"""合规检查 API（等保 / 关基 / 数据安全）"""
import logging

from fastapi import APIRouter, Depends

from api.dependencies import get_db
from api.auth import verify_api_key
from api.models import APIResponse, ComplianceCheckRequest, QuestionnaireAnswerBatch

from compliance_engine import ComplianceEngine, available_standards, build_evidence, load_catalog
from compliance_questionnaire import QuestionnaireEngine, system_scope_key

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get('/compliance/standards', response_model=APIResponse)
def compliance_standards(_=Depends(verify_api_key)):
    """可用的合规标准列表"""
    items = []
    for std in available_standards():
        try:
            cat = load_catalog(std)
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f'合规条款目录加载失败: {std} -> {e}')
            items.append({'standard': std, 'error': str(e)})
            continue
        items.append({'standard': std, 'standard_name': cat['standard_name'],
                      'version': cat['version'], 'total_controls': len(cat['controls'])})
    return APIResponse(data=items)


@router.get('/compliance/history', response_model=APIResponse)
def compliance_history(standard: str = None, limit: int = 100,
                       db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_compliance_history(standard, limit))


@router.get('/compliance/questionnaire/{standard}', response_model=APIResponse)
def compliance_questionnaire(standard: str, business_system: str = '', level: str = 'ALL',
                             db=Depends(get_db), _=Depends(verify_api_key)):
    """取问卷条款与已填答案"""
    try:
        q = QuestionnaireEngine(standard, db, level)
    except FileNotFoundError:
        return APIResponse(success=False, message=f'未知的合规标准: {standard}')
    return APIResponse(data={'progress': q.progress(business_system),
                             'rows': q.to_rows(business_system)})


@router.put('/compliance/questionnaire/{standard}', response_model=APIResponse)
def compliance_answer(standard: str, payload: QuestionnaireAnswerBatch,
                      db=Depends(get_db), _=Depends(verify_api_key)):
    """批量提交问卷答案。非法条款或状态会被拒绝并计入 rejected，不静默吞掉。"""
    try:
        q = QuestionnaireEngine(standard, db)
    except FileNotFoundError:
        return APIResponse(success=False, message=f'未知的合规标准: {standard}')
    answers = {a.control_id: {'status': a.status, 'note': a.note,
                              'evidence_ref': a.evidence_ref}
               for a in payload.answers}
    stats = q.save_answers(answers, payload.business_system, payload.answered_by)
    msg = 'ok' if not stats['rejected'] else f"{stats['rejected']} 条因条款不存在或状态非法被拒绝"
    return APIResponse(success=stats['rejected'] == 0,
                       data={**stats, 'progress': q.progress(payload.business_system)},
                       message=msg)


@router.post('/compliance/check', response_model=APIResponse)
def compliance_check(payload: ComplianceCheckRequest,
                     db=Depends(get_db), _=Depends(verify_api_key)):
    """执行一次合规检查。

    技术证据来自 scan_id 指定的历史扫描——本接口不会内联发起新扫描，
    避免一个 HTTP 请求里挂着几分钟的端口探测。未提供 scan_id 时，
    纯技术类条款会如实判为『证据不足』。
    """
    try:
        engine = ComplianceEngine(payload.standard)
    except FileNotFoundError:
        return APIResponse(success=False, message=f'未知的合规标准: {payload.standard}')

    scan_rows = None
    target = payload.target
    if payload.scan_id is not None:
        task = db.scan.get_task(payload.scan_id)
        if not task:
            return APIResponse(success=False, message=f'扫描任务不存在: {payload.scan_id}')
        scan_rows = db.scan.get_task_results(payload.scan_id)
        target = target or dict(task).get('target', '')

    scope_key = system_scope_key(payload.business_system)
    # Web 侧证据存在 web_scan_results 表，不随 scan_rows 一起来
    web_findings = []
    if target:
        try:
            web_findings = db.get_web_scan_results(target=target) or []
        except Exception as e:
            logger.error(f'读取 Web 扫描结果失败: {e}')
    evidence = build_evidence(scan_rows, target=target, scope_key=scope_key,
                              standard=payload.standard, level=payload.level,
                              web_findings=web_findings)
    answers = db.get_questionnaire_answers(payload.standard, scope_key, include_org=True)
    agg = engine.evaluate(evidence, answers=answers, level=payload.level)
    history_id = db.save_compliance_result(agg, ai_enabled=False)

    return APIResponse(data={
        'history_id': history_id,
        'standard': agg['standard'],
        'standard_name': agg['standard_name'],
        'level': agg['level'],
        'scope_key': scope_key,
        'compliance_rate': agg['compliance_rate'],
        'score': agg['score'],
        'counts': agg['counts'],
        'auto_ratio': agg['auto_ratio'],
        'questionnaire_completion': agg['questionnaire_completion'],
        'evidence_used': scan_rows is not None,
    })


@router.get('/compliance/{history_id}', response_model=APIResponse)
def compliance_detail(history_id: int, db=Depends(get_db), _=Depends(verify_api_key)):
    detail = db.get_compliance_detail(history_id)
    if detail is None:
        return APIResponse(success=False, message='Not found')
    return APIResponse(data=detail)
