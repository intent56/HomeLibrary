from app.errors import bp
from app import db
from flask import render_template


@bp.app_errorhandler(404)
def handle_404(err):
    return render_template("errors/404.html"), 404


@bp.app_errorhandler(500)
def handle_500(err):
    db.session.rollback()
    return render_template("errors/500.html"), 500
