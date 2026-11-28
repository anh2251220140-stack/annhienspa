"""Shared copy of the public catalog for guest HTML on Vercel Production."""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone

from config.blob_media import blob_sdk
from .catalog_data import catalog, promotions


PATH = "public-catalog/v1/current.json"
MAX_BYTES = 512 * 1024
LOCK = "annhien_public_catalog_v1"
logger = logging.getLogger(__name__)


def _read(sdk):
    with sdk.stream_blob(PATH, access="private") as download:
        body = bytearray()
        for chunk in download:
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise ValueError("Public catalog exceeds size limit.")
    data, offers = json.loads(body)
    if (not isinstance(data, dict) or not isinstance(offers, dict)
            or set(data) != {"services", "products", "staff", "relations"}
            or not all(isinstance(rows, list) for rows in data.values())
            or not isinstance(offers.get("items"), list)
            or not isinstance(offers.get("expiringWithinDays"), int)
            or any(not isinstance(offer, dict)
                   or not isinstance(offer.get("startDate"), str)
                   or not isinstance(offer.get("endDate"), str) for offer in offers["items"])):
        raise ValueError("Invalid public catalog schema.")
    return data, offers


def _build():
    return catalog(), promotions(promotion_page=True, include_scheduled=True)


def _put(sdk, snapshot, *, overwrite):
    content = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode()
    if len(content) > MAX_BYTES:
        raise ValueError("Public catalog exceeds size limit.")
    sdk.put_blob(PATH, content, access="private", content_type="application/json",
                 cache_control_max_age=60, add_random_suffix=False, allow_overwrite=overwrite)


def load_or_initialize():
    missing = False
    try:
        sdk = blob_sdk()
        try:
            data, offers = _read(sdk)
            return data, offers, "blob"
        except sdk.BlobNotFoundError:
            missing = True
    except Exception:
        logger.warning("Public catalog snapshot unavailable. Falling back to MySQL.")

    data, offers = _build()
    if missing:
        try:
            # A first visitor can initialize the object but cannot overwrite a
            # newer copy written by another worker or by an Admin update.
            _put(sdk, (data, offers), overwrite=False)
        except Exception:
            logger.warning("Could not initialize the shared public catalog snapshot.")
    return data, offers, "mysql"


def _publish():
    # Serialize publishers after their catalog writes have committed so a
    # concurrent edit cannot be replaced with a previously read snapshot.
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, %s)", [LOCK, 5])
            if cursor.fetchone()[0] != 1:
                logger.warning("Public catalog publish lock was unavailable.")
                return
            try:
                _put(blob_sdk(), _build(), overwrite=True)
            finally:
                cursor.execute("SELECT RELEASE_LOCK(%s)", [LOCK])
        cache.delete(f"frontend-public-catalog:{timezone.localdate().isoformat()}")
    except Exception:
        logger.warning("Could not publish the updated public catalog snapshot.")


def publish_after_commit():
    if settings.PUBLIC_CATALOG_BLOB_ENABLED:
        transaction.on_commit(_publish)
