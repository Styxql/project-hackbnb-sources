import hmac
import secrets
import string
from datetime import date
from flask import jsonify, Blueprint, request

from database.init import db
from api.rooms.rooms_models import Room
from services.stripe import create_checkout, get_checkout_lines, is_checkout_paid
from .bookings_models import Booking
from sqlalchemy.orm import joinedload

bookings_api = Blueprint('bookings', __name__)

BOOKING_REFERENCE_ALPHABET = string.ascii_uppercase + string.digits


def _json_body() -> dict:
    # renvoie {} si le body n'est pas du JSON valide, sinon request.json plantait en 500
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


@bookings_api.route('/<reference>', methods=['GET'])
def get_booking_details(reference: str):
    """
    Get booking details
    """

    booking = Booking.query.options(joinedload(Booking.room)).filter_by(reference=reference).first()
    if not booking:
        return {'error': 'Booking not found'}, 404

    return jsonify(booking.to_dict())


@bookings_api.route('/<reference>/checkout-lines', methods=['GET'])
def get_booking_checkout_lines(reference: str):
    """
    Get booking checkout lines
    """

    booking = Booking.query.options(joinedload(Booking.room)).filter_by(reference=reference).first()
    if not booking:
        return {'error': 'Booking not found'}, 404

    if not booking.is_paid:
        return {'error': 'Cannot get checkout lines without payment'}, 422

    # Fix : avant on prenait checkout_session_id dans l'URL, ce qui permettait d'appeler
    # n'importe quel endpoint Stripe avec notre clé. On utilise l'ID stocké en base.
    try:
        return jsonify(get_checkout_lines(booking.stripe_checkout_session_id))
    except Exception:
        return {'error': 'Unable to retrieve checkout lines'}, 404


@bookings_api.route('/', methods=['POST'])
def new_booking():
    """
    Register a new booking for a room
    """

    body = _json_body()

    # Check room exists
    room_id = body.get("roomId")
    if room_id is None:
        return {'error': 'Missing room'}, 400
    room = Room.query.filter_by(id=room_id).first()
    if not room:
        return {'error': 'Room not found'}, 404

    # Check arrival date is format YYYY-MM-DD
    try:
        arrival_date = date.fromisoformat(body.get("arrivalDate"))
    except (TypeError, ValueError):
        return {'error': 'Invalid arrival date'}, 400

    # Check departure date is format YYYY-MM-DD
    try:
        departure_date = date.fromisoformat(body.get("departureDate"))
    except (TypeError, ValueError):
        return {'error': 'Invalid departure date'}, 400

    # pas de réservation dans le passé
    if arrival_date < date.today():
        return {'error': 'Invalid arrival date'}, 400

    # Check departure date is later than arrival date
    if departure_date <= arrival_date:
        return {'error': 'Invalid departure date'}, 400

    # Check guests count is valid and <= 10 guests
    # (on exclut bool car True passe le isinstance int en python)
    guests_count = body.get("guestsCount")
    if isinstance(guests_count, bool) or not isinstance(guests_count, int) or guests_count < 1 or guests_count > 10:
        return {'error': 'Invalid guests count'}, 400

    # Determine how many days is the booking for (max 1 an)
    booking_duration_in_days = (departure_date - arrival_date).days
    if booking_duration_in_days < 1 or booking_duration_in_days > 365:
        return {'error': 'Invalid booking duration'}, 400

    # Determine the booking total price
    booking_price = room.price * booking_duration_in_days

    # Fix : secrets au lieu de random,
    # 12 caractères et on vérifie que la référence n'existe pas déjà
    while True:
        booking_reference = ''.join(secrets.choice(BOOKING_REFERENCE_ALPHABET) for _ in range(12))
        if not Booking.query.filter_by(reference=booking_reference).first():
            break

    # Fix : avant c'était sha512(timestamp), donc facile à retrouver en bruteforçant l'heure.
    # token_hex(32) = 32 octets vraiment aléatoires
    checkout_confirmation_secret = secrets.token_hex(32)

    # Create Stripe checkout session
    checkout_session = create_checkout(
        reference=booking_reference,
        name=f"{booking_duration_in_days} nuit{'s' if booking_duration_in_days > 1 else ''} à {room.title} ({room.city})",
        unit_price=room.price,
        quantity=booking_duration_in_days,
        confirmation_secret=checkout_confirmation_secret,
    )

    # Create booking
    db.session.add(Booking(
        reference=booking_reference,
        arrival_date=arrival_date.isoformat(),
        departure_date=departure_date.isoformat(),
        guests_count=guests_count,
        total_price=booking_price,
        checkout_confirmation_secret=checkout_confirmation_secret,
        stripe_checkout_session_id=checkout_session.id,
        is_paid=False,
        room_id=room.id,
    ))
    db.session.commit()

    return jsonify({
        "reference": booking_reference,
        "duration_in_days": booking_duration_in_days,
        "price": booking_price,
        "checkout_url": checkout_session.url,
    })


@bookings_api.route('/<reference>/confirm-checkout', methods=['POST'])
def confirm_booking_checkout(reference: str):
    """
    Confirm checkout payment for a booking
    """

    booking = Booking.query.filter_by(reference=reference).first()
    if not booking:
        return {'error': 'Booking not found'}, 404

    if booking.is_paid:
        return jsonify({"success": True})

    # compare_digest pour comparer en temps constant (timing attack)
    confirmation_secret = _json_body().get("confirmationSecret")
    if not isinstance(confirmation_secret, str) or not hmac.compare_digest(
        booking.checkout_confirmation_secret.encode(), confirmation_secret.encode()
    ):
        return {'error': 'Invalid confirmation secret'}, 422

    # Fix : le secret seul ne suffit plus, on demande à Stripe si la session est vraiment payée
    try:
        paid = is_checkout_paid(booking.stripe_checkout_session_id)
    except Exception:
        return {'error': 'Unable to verify payment'}, 502
    if not paid:
        return {'error': 'Payment not completed'}, 402

    booking.is_paid = True
    db.session.commit()

    return jsonify({
        "success": True,
    })
