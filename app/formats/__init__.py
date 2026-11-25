from flask import Blueprint

bp = Blueprint('formats', __name__)

from app.formats import routes
