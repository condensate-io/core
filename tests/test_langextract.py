import pytest
from unittest.mock import AsyncMock, patch
from src.agents.langextract import LangExtract

@pytest.mark.asyncio
async def test_langextract_extract_learnings():
    # Mock LLM Client
    with patch('src.agents.langextract.LLMClient') as MockLLM:
        mock_instance = MockLLM.return_value
        # Mock generate return
        mock_instance.generate = AsyncMock(return_value='[{"statement": "Test Learning", "confidence": 0.9}]')
        
        extractor = LangExtract()
        result = await extractor.extract_learnings("Some corpus text")
        
        assert len(result) == 1
        assert result[0]['statement'] == "Test Learning"
        assert result[0]['confidence'] == 0.9

@pytest.mark.asyncio
async def test_langextract_extract_triplets():
    with patch('src.agents.langextract.LLMClient') as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.generate = AsyncMock(return_value='[{"subject": "A", "predicate": "B", "object": "C"}]')
        
        extractor = LangExtract()
        result = await extractor.extract_triplets("A B C")
        
        assert len(result) == 1
        assert result[0]['subject'] == "A"
