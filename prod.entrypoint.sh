apache2ctl -D FOREGROUND &

# Fix D8 : Flask servi par gunicorn en prod au lieu du serveur de dev Werkzeug.
# --preload charge l'app (et le seed de la base) une seule fois avant de lancer les workers
exec gunicorn --workers 2 --preload --bind 127.0.0.1:9001 app:app
