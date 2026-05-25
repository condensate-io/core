import pytest
from unittest.mock import MagicMock
from src.db.models import ApiKey
from src.server.security import hash_key, verify_key
from src.server.admin import get_api_key
from fastapi import HTTPException

def test_key_hashing_and_verification():
    plain = "sk-5b074364-a89a-486c-94ff-79ad7daf6326"
    hashed = hash_key(plain)
    
    # Prefix must be of length 12
    assert plain[:12] == "sk-5b074364-"
    assert hashed != plain
    
    # Verification should succeed
    assert verify_key(plain, hashed) is True
    
    # Verification with incorrect key should fail
    assert verify_key("sk-wrong", hashed) is False

def test_legacy_unhashed_key_verification():
    plain = "sk-legacy-plain-key"
    assert verify_key(plain, plain) is True
    assert verify_key("sk-wrong", plain) is False

def test_get_api_key_dependency_hashed():
    # Mock database and session
    mock_db = MagicMock()
    
    plain_key = "sk-5b074364-a89a-486c-94ff-79ad7daf6326"
    hashed = hash_key(plain_key)
    prefix = plain_key[:12]
    
    api_key_record = ApiKey(key=hashed, prefix=prefix, name="test-key", is_active=True)
    
    # Mock the database query
    mock_db.execute.return_value.scalars.return_value.all.return_value = [api_key_record]
    
    # Verify authentication works with Bearer token
    result = get_api_key(auth_header=f"Bearer {plain_key}", x_api_header=None, db=mock_db)
    assert result == api_key_record

def test_get_api_key_dependency_legacy():
    mock_db = MagicMock()
    
    plain_key = "sk-legacy-key"
    api_key_record = ApiKey(key=plain_key, prefix=None, name="legacy-key", is_active=True)
    
    mock_db.execute.return_value.scalars.return_value.all.return_value = [api_key_record]
    
    # Verify auth works with legacy plain-text key
    result = get_api_key(auth_header=f"Bearer {plain_key}", x_api_header=None, db=mock_db)
    assert result == api_key_record

def test_get_api_key_invalid():
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    
    with pytest.raises(HTTPException) as exc_info:
        get_api_key(auth_header="Bearer sk-invalid", x_api_header=None, db=mock_db)
    assert exc_info.value.status_code == 401
