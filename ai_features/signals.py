"""Commit-aware invalidation. Catalog writes never invoke a paid provider."""
import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save

from .config import enabled


def invalidate(sender, instance, **kwargs):
    if not enabled("AI_RAG_ENABLED") or kwargs.get("raw"):
        return
    kinds = {"service": "service", "servicecategory": "category", "careproduct": "product", "promotion": "promotion"}
    kind = kinds[sender._meta.model_name]
    key = f"{kind}:{instance.pk}"

    def after_commit():
        try:
            from .rag import vector_index
            vector_index().invalidate([key])
        except Exception:
            # Catalog persistence must not fail because an auxiliary index is unavailable.
            logging.getLogger(__name__).warning("RAG invalidation unavailable; live content hashes remain authoritative")
    transaction.on_commit(after_commit, using=kwargs.get("using", "default"))


def connect():
    from products.models import CareProduct
    from promotions.models import Promotion
    from services.models import Service, ServiceCategory
    for sender in (Service, ServiceCategory, CareProduct, Promotion):
        for signal in (post_save, post_delete):
            signal.connect(invalidate, sender=sender, dispatch_uid=f"rag.{signal}.{sender._meta.label}", weak=False)
