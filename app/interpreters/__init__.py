from flask import Blueprint

bp = Blueprint('interpreters', __name__)

from app.interpreters import routes
