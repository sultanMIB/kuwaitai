from fastapi import FastAPI, APIRouter, Depends
import os
from helper.config import get_settings, Settings
router_base = APIRouter(
    prefix="/base",
    tags=["base"],
    responses={404: {"description": "Not found"}},
)

@router_base.get("/")
async def read_base(app_settings:Settings=Depends(get_settings)):
    app_name = app_settings.APP_NAME
    app_version = app_settings.APP_VERSION
    return {"message": f"Welcome to the base route {app_name},{app_version}!"}
