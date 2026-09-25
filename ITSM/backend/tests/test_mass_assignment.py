"""防 mass-assignment：create schema 不得暴露状态/作者字段（客户端可控即绕过状态机/冒名）。"""
from app.schemas.change_order import ChangeOrderCreate
from app.schemas.onsite import OnsiteDailyReportCreate
from app.schemas.outsourcing import OutsourcingCreate


def test_create_schemas_forbid_status_and_author():
    assert "status" not in ChangeOrderCreate.model_fields
    assert "status" not in OutsourcingCreate.model_fields
    assert "user_id" not in OnsiteDailyReportCreate.model_fields
