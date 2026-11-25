from flask import Blueprint

bp = Blueprint('aggregators', __name__)

from app.aggregators import routes
