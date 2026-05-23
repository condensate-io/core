import os
import json
import logging

logger = logging.getLogger(__name__)

class SynapseConfig:
    def __init__(self):
        self.config_path = "synapse_config.json"
        self._load()

    def _load(self):
        # Default from env
        self.ENABLED = os.getenv("SYNAPSE_ENGINE_ENABLED", "true").lower() == "true"
        self.LEARNING_RATE = float(os.getenv("SYNAPSE_LEARNING_RATE", "0.08"))
        self.DECAY_RATE = float(os.getenv("SYNAPSE_DECAY_RATE", "0.995"))
        self.PRUNE_THRESHOLD = float(os.getenv("SYNAPSE_PRUNE_THRESHOLD", "0.05"))
        self.CONSOLIDATION_THRESHOLD = float(os.getenv("SYNAPSE_CONSOLIDATION_THRESHOLD", "0.75"))
        self.DECAY_INTERVAL_HOURS = int(os.getenv("SYNAPSE_DECAY_INTERVAL_HOURS", "24"))

        # Override from file if exists
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    self.ENABLED = data.get("enabled", self.ENABLED)
                    self.LEARNING_RATE = data.get("learning_rate", self.LEARNING_RATE)
                    self.DECAY_RATE = data.get("decay_rate", self.DECAY_RATE)
                    self.PRUNE_THRESHOLD = data.get("prune_threshold", self.PRUNE_THRESHOLD)
                    self.CONSOLIDATION_THRESHOLD = data.get("consolidation_threshold", self.CONSOLIDATION_THRESHOLD)
                    self.DECAY_INTERVAL_HOURS = data.get("decay_interval_hours", self.DECAY_INTERVAL_HOURS)
            except Exception as e:
                logger.warning("Failed to load synapse_config.json: %s", e)

    def refresh(self):
        self._load()

synapse_config = SynapseConfig()
