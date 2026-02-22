from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from src.db.models import Entity, Project
from src.llm.schemas import ExtractedEntity
import uuid

class EntityCanonicalizer:
    def __init__(self, db: Session):
        self.db = db

    def resolve(self, project_id: str, extracted_entities: List[ExtractedEntity]) -> Dict[str, str]:
        """
        Resolves a list of ExtractedEntity objects to persistent Entity IDs.
        Returns a mapping of { extracted_name: entity_uuid }.
        """
        resolution_map = {}
        
        # 1. Fetch potential matches from DB
        def normalize(name: str):
            n = name.lower().strip()
            if n.startswith("the "):
                n = n[4:]
            return n

        names_to_check = [normalize(e.name) for e in extracted_entities]
        aliases_to_check = [normalize(a) for e in extracted_entities for a in e.aliases]
        all_terms = set(names_to_check + aliases_to_check)

        # Naive matching: Exact match on name or alias (Case Insensitive)
        # In a real system, this would use a Vectorized Entity Store for fuzzy matching
        stmt = select(Entity).where(
            Entity.project_id == project_id,
            or_(
                Entity.canonical_name.in_(all_terms),
                Entity.aliases.contains(all_terms) # JSONB contains check (simplified)
            )
        )
        # SQLAlchemy's .contains for PG arrays/JSONB works differently, 
        # for now let's iterate to be safe and predictable in Python due to complexity of JSONB array overlap in SQL
        
        existing_entities = self.db.execute(select(Entity).where(Entity.project_id == project_id)).scalars().all()
        
        # Build lookup index
        lookup: Dict[str, Entity] = {}
        for ent in existing_entities:
            lookup[normalize(ent.canonical_name)] = ent
            if ent.aliases:
                for alias in ent.aliases:
                    lookup[normalize(alias)] = ent

        # 2. Process each extracted entity
        for ext in extracted_entities:
            key = normalize(ext.name)
            
            # Match found?
            if key in lookup:
                match = lookup[key]
                resolution_map[ext.name] = str(match.id)
                
                # Merge new aliases if any
                updated = False
                current_aliases = set(match.aliases or [])
                for idx, new_alias in enumerate(ext.aliases):
                    if new_alias.lower() not in [a.lower() for a in current_aliases]:
                        current_aliases.add(new_alias)
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
                    # description removed as it is not in the model
                    confidence=ext.confidence
                )
                self.db.add(new_entity)
                self.db.flush() # Get ID ready
                
                # Update lookup
                lookup[key] = new_entity
                for a in ext.aliases:
                    lookup[a.lower()] = new_entity
                
                resolution_map[ext.name] = str(new_entity.id)

        self.db.commit()
        return resolution_map
