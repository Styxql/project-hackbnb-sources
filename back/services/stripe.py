import os
import re
import stripe

# format d'un ID de session checkout Stripe (cs_test_xxx / cs_live_xxx)
# ça bloque les payloads du type ../../customers/... vus dans les logs
CHECKOUT_SESSION_ID_PATTERN = re.compile(r"^cs_(test|live)_[A-Za-z0-9]+$")


def _configure_stripe():
    # clé lue dans l'env, on plante clairement si elle n'est pas définie
    api_key = os.getenv('STRIPE_API_KEY')
    if not api_key:
        raise RuntimeError("STRIPE_API_KEY is not set")
    stripe.api_key = api_key


def _validate_checkout_session_id(checkout_session_id) -> str:
    if not isinstance(checkout_session_id, str) or not CHECKOUT_SESSION_ID_PATTERN.fullmatch(checkout_session_id):
        raise ValueError("Invalid checkout session ID")
    return checkout_session_id


def _to_dict(stripe_object) -> dict:
    if hasattr(stripe_object, "to_dict"):
        return stripe_object.to_dict()
    return dict(stripe_object)


def create_checkout(reference, name, unit_price, quantity, confirmation_secret):
    """
        Create Stripe checkout
        Documentation: https://docs.stripe.com/checkout/quickstart?client=react&lang=python
    """

    _configure_stripe()
    origin_host = os.getenv('APP_ORIGIN_HOST')
    return stripe.checkout.Session.create(
        mode='payment',
        success_url=f"{origin_host}/booking/{reference}?checkout_confirmation_secret={confirmation_secret}",
        cancel_url=origin_host,
        line_items=[
            {
                'quantity': quantity,
                'price_data': {
                    'currency': 'EUR',
                    'unit_amount': round(unit_price * 100),
                    'product_data': {
                        'name': name,
                    },
                },
            },
        ],
    )


def is_checkout_paid(checkout_session_id) -> bool:
    """
        Vérifie auprès de Stripe que la session a bien été payée
    """

    _configure_stripe()
    session = stripe.checkout.Session.retrieve(_validate_checkout_session_id(checkout_session_id))
    return session.payment_status == "paid"


def get_checkout_lines(checkout_session_id):
    """
        Get checkout session line items
        Fix : on utilise le SDK au lieu de construire l'URL à la main avec requests,
        c'est ce qui permettait de taper sur /customers/.../payment_methods
    """

    _configure_stripe()
    line_items = _to_dict(stripe.checkout.Session.list_line_items(_validate_checkout_session_id(checkout_session_id)))

    # on renvoie seulement ce que le front affiche
    return [
        {
            "description": item.get("description"),
            "quantity": item.get("quantity"),
            "currency": item.get("currency"),
            "amount_total": item.get("amount_total"),
            "price": {"unit_amount": (item.get("price") or {}).get("unit_amount")},
        }
        for item in line_items.get("data", [])
    ]
