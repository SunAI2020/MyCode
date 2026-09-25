from fastapi import APIRouter

from app.api.v1 import auth, contracts, customers, deliveries, issues, onsite, outsourcing, performance, services, work_orders
from app.utils.response import ok

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(contracts.contracts)
api_router.include_router(contracts.items)
api_router.include_router(contracts.cis)
api_router.include_router(work_orders.receives)
api_router.include_router(work_orders.router)
api_router.include_router(issues.router)
api_router.include_router(deliveries.router)
api_router.include_router(performance.router)
api_router.include_router(onsite.services)
api_router.include_router(onsite.reports)
api_router.include_router(outsourcing.users)
api_router.include_router(outsourcing.outsourcings)
api_router.include_router(outsourcing.reports)
api_router.include_router(services.sla)
api_router.include_router(services.cycles)
api_router.include_router(services.reminders)


@api_router.get("/health")
def health() -> dict:
    return ok({"status": "healthy"})
