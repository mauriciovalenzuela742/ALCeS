'''Capa 5 — Procedencia: tagging, manifiesto y reproducibilidad de cada corrida.'''

from .tagger import RunTag, tag_run, collect_campaign_tags  # noqa: F401

__all__ = ["RunTag", "tag_run", "collect_campaign_tags"]
