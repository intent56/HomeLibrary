from flask import Blueprint

bp = Blueprint('sources', __name__, url_prefix='/api')
from app.sources import routes
