"""
filename: elasticsearch_client.py
description: Elasticsearch connection helper.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from elasticsearch import Elasticsearch

from app.config import settings


def get_client() -> Elasticsearch:
    if settings.elasticsearch_password:
        return Elasticsearch(
            settings.elasticsearch_url,
            basic_auth=(settings.elasticsearch_username, settings.elasticsearch_password),
        )
    return Elasticsearch(settings.elasticsearch_url)
