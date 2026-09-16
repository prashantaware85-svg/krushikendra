from fastapi import APIRouter

from app.api.v1.endpoints import health, health_db
from app.modules.auth.router import router as auth_router
from app.modules.farmers.router import router as farmers_router
from app.modules.farms.router import router as farms_router
from app.modules.crops.router import router as crops_router
from app.modules.activities.router import router as activities_router
from app.modules.weather.router import router as weather_router
from app.modules.market.router import router as market_router
from app.modules.ai.router import router as ai_router
from app.modules.fertilizers.router import router as fertilizers_router
from app.modules.health.router import router as health_router
from app.modules.soil.router import router as soil_router
from app.modules.vision.router import router as vision_router
from app.modules.store.router import router as store_router
from app.modules.commerce.router import router as commerce_router
from app.modules.payments.router import router as payments_router
from app.modules.khata.router import router as khata_router
from app.modules.suppliers.router import router as suppliers_router
from app.modules.purchases.router import router as purchases_router
from app.modules.inventory.router import router as inventory_router
from app.modules.staff.router import router as staff_router
from app.modules.pos.router import router as pos_router

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(health_db.router)
api_router.include_router(auth_router)
api_router.include_router(farmers_router)
api_router.include_router(farms_router)
api_router.include_router(crops_router)
api_router.include_router(activities_router)
api_router.include_router(weather_router)
api_router.include_router(market_router)
api_router.include_router(ai_router)
api_router.include_router(vision_router)
api_router.include_router(soil_router)
api_router.include_router(fertilizers_router)
api_router.include_router(health_router)
api_router.include_router(store_router)
api_router.include_router(commerce_router)
api_router.include_router(payments_router)
api_router.include_router(khata_router)
api_router.include_router(suppliers_router)
api_router.include_router(purchases_router)
api_router.include_router(inventory_router)
api_router.include_router(staff_router)
api_router.include_router(pos_router)