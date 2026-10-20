def auth_ui(request):
    """Only presentation data; no credentials, session ID, or authorization from JS."""
    user = request.user
    payload = None
    if user.is_authenticated:
        customer = getattr(user, "customer", None)
        payload = {"authenticated": True, "id": user.pk, "username": user.username,
                   "identifier": user.username, "email": user.email, "role": user.role,
                   "phone": customer.phone if customer else "", "name": customer.full_name if customer else user.username}
        if customer and user.role == "User" and not user.is_superuser:
            from .admin_views import customer_row
            payload["profile"] = customer_row(customer)
    return {"auth_ui": payload}
