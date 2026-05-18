from django.conf import settings
from django.core.cache import cache


def cache_get(key: str):
    return cache.get(key)


def cache_set(key: str, value):
    cache.set(key, value, timeout=getattr(settings, "CACHE_TTL", 21600))
