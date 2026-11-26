from flask import Blueprint

bp = Blueprint('sources', __name__)
from app.sources import routes
