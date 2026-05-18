import json
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_EE_READY = False
_EE_ATTEMPTED = False


def initialize_ee() -> bool:
    global _EE_READY, _EE_ATTEMPTED
    if _EE_READY:
        return True
    if _EE_ATTEMPTED:
        return False

    _EE_ATTEMPTED = True

    try:
        import ee
    except Exception as exc:
        logger.warning("Earth Engine SDK unavailable: %s", exc)
        return False

    try:
        key_file = getattr(settings, "GOOGLE_EARTH_ENGINE_KEY", "")
        project_id = settings.__dict__.get("GEE_PROJECT_ID", "")

        if key_file:
            key_path = Path(key_file)
            if key_path.exists():
                payload = json.loads(key_path.read_text())
                service_account = payload.get("client_email")
                credentials = ee.ServiceAccountCredentials(service_account, str(key_path))
                ee.Initialize(credentials=credentials, project=project_id or None)
            else:
                logger.warning("GEE key file configured but not found: %s", key_file)
                return False
        else:
            ee.Initialize(project=project_id or None)

        _EE_READY = True
        return True
    except Exception as exc:
        logger.warning("Earth Engine initialization failed: %s", exc)
        return False
