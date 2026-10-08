"""Export display-only English names keyed by the existing catalog identities."""

from __future__ import annotations

from mhwilds_skill_sim.catalog.model import Catalog


def build_english_names(*, catalog: Catalog, english_catalog: Catalog) -> dict:
    """Require a matching English name for every searchable catalog item.

    This sidecar never changes the solver catalog, inventory IDs or revision.
    A missing translation fails the release instead of silently shipping a
    partly translated production catalog. Clients still tolerate a failed
    optional sidecar request without making the core application unusable.
    """
    names = {}
    for collection, identity in (
        ("skills", "skill_id"),
        ("equipment", "equipment_id"),
        ("decorations", "decoration_id"),
    ):
        translated = {
            getattr(item, identity): item.display_name
            for item in getattr(english_catalog, collection)
            if isinstance(item.display_name, str) and item.display_name.strip()
        }
        required = {getattr(item, identity) for item in getattr(catalog, collection)}
        missing = sorted(required - translated.keys())
        if missing:
            raise ValueError(
                f"English {collection} names missing for {len(missing)} IDs: "
                + ", ".join(missing[:3])
            )
        names[collection] = {key: translated[key] for key in sorted(required)}
    return {"schema_version": 1, "locale": "en", "names": names}
