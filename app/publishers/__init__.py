from flask import Blueprint

bp = Blueprint('publishers', __name__)

from app.publishers import routes
