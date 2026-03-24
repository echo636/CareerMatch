from flask import Blueprint

from .gap import gap_bp
from .health import health_bp
from .matches import matches_bp
from .resumes import resumes_bp

api_bp = Blueprint("api", __name__)
api_bp.register_blueprint(health_bp)
api_bp.register_blueprint(resumes_bp, url_prefix="/resumes")
api_bp.register_blueprint(matches_bp, url_prefix="/matches")
api_bp.register_blueprint(gap_bp, url_prefix="/gap")
