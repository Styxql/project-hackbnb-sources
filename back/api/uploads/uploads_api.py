import os
from flask import Blueprint, request, send_from_directory, abort

uploads_api = Blueprint('uploads', __name__)

UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads'))
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


@uploads_api.route('/')
def get_upload():
   name = request.args.get("name", "")

   # Fix path traversal : name=../app.py permettait de lire tout le serveur.
   # On accepte seulement un nom de fichier sans dossier, avec une extension d'image
   if not name or os.path.basename(name) != name or os.path.splitext(name)[1].lower() not in ALLOWED_EXTENSIONS:
      abort(404)

   # send_from_directory refuse aussi de sortir du dossier (safe_join), on ajoute donc une double protection
   return send_from_directory(UPLOADS_DIR, name)
