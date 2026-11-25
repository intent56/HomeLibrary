# api.py

from flask import (Blueprint, 
                   request, 
                   jsonify, 
                   redirect,
                    flash,
                    url_for,)
import requests
import time
from app import db
from app.models.main import Book, Author, Interpreter, Genre, Publisher, Language, Cover, Format, Source, Aggregator
from sqlalchemy import or_
import urllib.parse


api = Blueprint('api', __name__, url_prefix='/api')

