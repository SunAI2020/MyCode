from fastapi import APIRouter

from app.api.v1 import auth, contracts, customers, services, work_orders
from app.utils.response import ok

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(contracts.contracts)
api_router.include_router(contracts.items)
api_router.include_router(contracts.cis)
api_router.include_router(work_orders.receives)
api_router.include_router(work_orders.router)
api_router.include_router(services.sla)
api_router.include_router(services.cycles)
api_router.include_router(services.reminders)


@api_router.get("/health")
def health() -> dict:
    return ok({"status": "healthy"})
