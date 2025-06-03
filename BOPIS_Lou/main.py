from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles # Added
from app.api.endpoints import (
    auth_router,
    tenant_router,
    user_router,
    product_router,
    timeslot_router,
    lane_router,
    order_router,
    picker_router,
    counter_router,
    pos_router,
    notification_router # Added notification_router
)

app = FastAPI(
    title="BOPIS/POS API",
    description="API for Buy Online, Pick up In Store (BOPIS) and Point of Sale (POS) operations.",
    version="0.1.0"
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the BOPIS/POS API"}

app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
app.include_router(tenant_router.router, prefix="/tenants", tags=["Tenants & Staff"])
app.include_router(user_router.router, prefix="/users", tags=["Users"])
app.include_router(product_router.router, prefix="/products", tags=["Products"])
app.include_router(timeslot_router.router, prefix="/timeslots", tags=["Pickup Time Slots"])
app.include_router(lane_router.router, prefix="/lanes", tags=["Lanes & Staff Assignments"])
app.include_router(order_router.router, prefix="/orders", tags=["Orders & Cart"])
app.include_router(picker_router.router, prefix="/picker", tags=["Picker Workflow"])
app.include_router(counter_router.router, prefix="/counter", tags=["Counter Workflow"])
app.include_router(pos_router.router, prefix="/pos", tags=["Point of Sale (POS)"])
app.include_router(notification_router.router, prefix="/notifications", tags=["Notifications"])

# Static files
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/mockups", StaticFiles(directory="mockups", html=True), name="mockups")


# Further routers will be included here later
