## version 1
from __future__ import annotations

from seed_category_fields_v1 import SCHEMA


def seed_category_fields_if_missing(db_session, CustomFieldDefinition) -> int:
    existing = {row.name: row for row in CustomFieldDefinition.query.all()}
    changed = 0
    sort_order = 1000

    for category_slug, groups in SCHEMA.items():
        for group_key, fields in groups.items():
            for field_key, label, field_type, placeholder in fields:
                name = f"{category_slug}__{group_key}__{field_key}"
                row = existing.get(name)
                if row is None:
                    row = CustomFieldDefinition(
                        name=name,
                        label=label,
                        field_type=field_type,
                        placeholder=placeholder,
                        sort_order=sort_order,
                    )
                    db_session.add(row)
                    changed += 1
                else:
                    updated = False
                    if row.label != label:
                        row.label = label
                        updated = True
                    if row.field_type != field_type:
                        row.field_type = field_type
                        updated = True
                    if (row.placeholder or "") != (placeholder or ""):
                        row.placeholder = placeholder
                        updated = True
                    if row.sort_order != sort_order:
                        row.sort_order = sort_order
                        updated = True
                    if updated:
                        changed += 1
                sort_order += 10

    if changed:
        db_session.commit()
    return changed
