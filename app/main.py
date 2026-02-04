from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes import api, ui
from app.startup import init_database

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.state.templates = Jinja2Templates(directory="app/templates")

app.include_router(api.router)
app.include_router(ui.router)

app.add_event_handler("startup", init_database)
