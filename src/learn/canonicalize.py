import uuid
from typing import Dict, List

from sqlalchemy import cast, exists, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from src.db.models import Entity
from src.llm.schemas import ExtractedEntity


def _normalize(name: str) -> str:
    n = name.lower().strip()
    if n.startswith("the "):
        n = n[4:]
    return n


def _normalize_sql(expr):
    return func.regexp_replace(func.btrim(func.lower(expr)), r"^the\s+", "")


class EntityCanonicalizer:
    def __init__(self, db: Session):
        self.db = db

    def resolve(self, project_id: str, extracted_entities: List[ExtractedEntity]) -> Dict[str, str]:
        """
        Resolves a list of ExtractedEntity objects to persistent Entity IDs.
        Returns a mapping of { extracted_name: entity_uuid }.

        Only entities whose canonical_name or aliases overlap with the current
        batch's candidate terms are fetched from the DB, instead of loading the
        entire project's entity table on every call (O(project_size) -> O(batch_size)).
        """
        resolution_map: Dict[str, str] = {}

        if not extracted_entities:
            return resolution_map

        raw_names_to_check = [e.name.strip() for e in extracted_entities if e.name and e.name.strip()]
        raw_aliases_to_check = [
            alias.strip()
            for e in extracted_entities
            for alias in e.aliases
            if alias and alias.strip()
        ]
        names_to_check = [_normalize(name) for name in raw_names_to_check]
        aliases_to_check = [_normalize(alias) for alias in raw_aliases_to_check]
        all_terms = list({t for t in (names_to_check + aliases_to_check) if t})
        raw_terms = list({t for t in (raw_names_to_check + raw_aliases_to_check) if t})

        existing_entities = []
        if all_terms:
            alias_terms = func.jsonb_array_elements_text(
                func.coalesce(Entity.aliases, cast("[]", JSONB))
            ).table_valued("value")
            predicates = [
                _normalize_sql(Entity.canonical_name).in_(all_terms),
                exists(
                    select(1)
                    .select_from(alias_terms)
                    .where(_normalize_sql(alias_terms.c.value).in_(all_terms))
                ),
            ]
            if raw_terms:
                predicates.append(Entity.aliases.op("?|")(raw_terms))

            stmt = select(Entity).where(
                Entity.project_id == project_id,
                or_(*predicates),
            )
            existing_entities = self.db.execute(stmt).scalars().all()

        # Build lookup index
        lookup: Dict[str, Entity] = {}
        for ent in existing_entities:
            lookup[_normalize(ent.canonical_name)] = ent
            if ent.aliases:
                for alias in ent.aliases:
                    lookup[_normalize(alias)] = ent

        new_entities: List[Entity] = []

        # 2. Process each extracted entity
        for ext in extracted_entities:
            key = _normalize(ext.name)

            # Match found?
            match = lookup.get(key)
            if match is not None:
                resolution_map[ext.name] = str(match.id)

                # Merge new aliases if any
                updated = False
                current_aliases = set(match.aliases or [])
                current_lower = {a.lower() for a in current_aliases}
                for new_alias in ext.aliases:
                    if new_alias.lower() not in current_lower:
                        current_aliases.add(new_alias)
                        current_lower.add(new_alias.lower())
                        updated = True

                if updated:
                    match.aliases = list(current_aliases)
                    self.db.add(match)

            else:
                # No match -> Create New Entity
                new_ent_id = uuid.uuid4()
                new_entity = Entity(
                    id=new_ent_id,
                    project_id=project_id,
                    type=ext.type,
                    canonical_name=ext.name,
                    aliases=ext.aliases,
                    confidence=ext.confidence,
                )
                new_entities.append(new_entity)

                # Update lookup so duplicate mentions within the same batch
                # resolve to the same (not-yet-flushed) entity.
                lookup[key] = new_entity
                for a in ext.aliases:
                    lookup[_normalize(a)] = new_entity

                resolution_map[ext.name] = str(new_entity.id)

        if new_entities:
            # Bulk add + a single flush to obtain IDs, instead of one
            # add()+flush() round trip per new entity.
            self.db.add_all(new_entities)
            self.db.flush()

        self.db.commit()
        return resolution_map
