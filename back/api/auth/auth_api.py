import re
from flask import jsonify, Blueprint, request
from database.init import db
from api.users.users_models import User

auth_api = Blueprint('auth', __name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _json_body() -> dict:
    # renvoie {} si le body n'est pas du JSON valide, sinon request.json plantait en 500
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


@auth_api.route('/login', methods=['POST'])
def login():
    body = _json_body()
    if not isinstance(body.get("email"), str):
        return {'error': 'Missing email'}, 400
    if not isinstance(body.get("password"), str):
        return {'error': 'Missing password'}, 400

    # Fix : un seul message d'erreur, sinon on peut tester quels emails sont inscrits
    user: User = User.query.where(User.email == body["email"]).first()
    if not user or not user.is_valid_password(body["password"]):
        return {'error': 'Invalid credentials'}, 401

    # commit au cas où le hash MD5 a été migré en scrypt dans is_valid_password
    db.session.commit()

    return jsonify({})


@auth_api.route('/register', methods=['POST'])
def create_account():
    body = _json_body()
    if not isinstance(body.get("name"), str) or not body["name"].strip():
        return {'error': 'Missing name'}, 400
    if not isinstance(body.get("email"), str) or not EMAIL_PATTERN.fullmatch(body["email"]):
        return {'error': 'Missing email'}, 400
    if not isinstance(body.get("password"), str):
        return {'error': 'Missing password'}, 400
    if len(body["password"]) < 12:
        return {'error': 'Password must be at least 12 characters long'}, 400

    # Error if user already exists
    existing_user: User = User.query.where(User.email == body["email"]).first()
    if existing_user:
        return {'error': 'User with same email already exists'}, 409

    user = User(
        name=body["name"].strip(),
        email=body["email"],
    )

    user.set_password(body["password"])

    # Create user in database
    db.session.add(user)
    db.session.commit()

    return jsonify({})
