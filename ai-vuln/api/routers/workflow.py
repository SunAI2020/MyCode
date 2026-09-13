# -*- coding: utf-8 -*-
"""漏洞处置工作流 API"""
from fastapi import APIRouter, Depends, Query

from api.dependencies import get_db, require_role, get_current_user
from api.models import DispositionCreate, WorkflowTransition, APIResponse
from workflow import VulnWorkflow

router = APIRouter()


@router.get('/workflow/states', response_model=APIResponse)
def list_states(_=Depends(get_current_user)):
    return APIResponse(data={'states': VulnWorkflow.STATES,
                             'terminal': list(VulnWorkflow.TERMINAL_STATES)})


@router.get('/workflow/dispositions', response_model=APIResponse)
def list_dispositions(status: str = Query(None), assignee: str = Query(None),
                      db=Depends(get_db), _=Depends(get_current_user)):
    return APIResponse(data=db.get_dispositions(status=status, assignee=assignee))


@router.post('/workflow/dispositions', status_code=201, response_model=APIResponse)
def create_disposition(body: DispositionCreate, db=Depends(get_db),
                       _=Depends(require_role('admin', 'analyst'))):
    wid = db.create_disposition(body.vuln_ref, vuln_title=body.vuln_title,
                                severity=body.severity, assignee=body.assignee,
                                source=body.source)
    db.add_audit_log('create_disposition', 'disposition', wid, body.vuln_ref)
    return APIResponse(data={'id': wid}, message='Created')


@router.post('/workflow/dispositions/{disposition_id}/transition', response_model=APIResponse)
def transition(disposition_id: int, body: WorkflowTransition, db=Depends(get_db),
               _=Depends(require_role('admin', 'analyst'))):
    """执行状态流转（非法流转被状态机拒绝）"""
    wf = VulnWorkflow(db=db)
    result = wf.transition(disposition_id, body.to_status, assignee=body.assignee,
                           note=body.note, reopen_reason=body.reopen_reason)
    return APIResponse(success=result['success'], data=result,
                       message=result.get('reason', '流转成功'))
