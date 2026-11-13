from os import path, getenv

basedir = path.abspath(path.dirname(__file__))

# origines CORS lues depuis l'env (séparées par des virgules), localhost par défaut pour le dev
CORS_ORIGINS = [o.strip() for o in getenv("CORS_ORIGINS", "http://localhost:9000").split(",") if o.strip()]

SQLALCHEMY_DATABASE_URI = "sqlite:///./database.sqlite"
SQLALCHEMY_TRACK_MODIFICATIONS = False
