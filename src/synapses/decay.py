from sqlalchemy.orm import Session
from sqlalchemy import update, delete
from datetime import datetime
from src.synapses.models import Synapse
from src.synapses.config import synapse_config

def run_synapse_decay_cycle(db: Session):
    """
    Background maintenance task to decay synapse weights and prune weak connections.
    """
    if not synapse_config.ENABLED:
        return

    # 1. Decay all weights
    # weight = weight * decay_rate
    db.query(Synapse).update(
        {Synapse.weight: Synapse.weight * synapse_config.DECAY_RATE},
        synchronize_session=False
    )
    
    # 2. Prune weights below threshold
    # ARCHIVE OR DELETE
    db.query(Synapse).filter(Synapse.weight < synapse_config.PRUNE_THRESHOLD).delete(
        synchronize_session=False
    )
    
    db.commit()
