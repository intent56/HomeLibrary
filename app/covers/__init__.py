from flask import Blueprint

bp = Blueprint('covers', __name__)

from app.covers import routes
