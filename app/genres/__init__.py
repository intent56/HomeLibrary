from flask import Blueprint

bp = Blueprint('genres', __name__)

from app.genres import routes
