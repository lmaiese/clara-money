from app.auth.service import hash_password, verify_password, create_token, decode_token
import uuid

def test_hash_and_verify_password():
    pw = "SecurePass123"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)

def test_create_and_decode_token():
    user_id = uuid.uuid4()
    token = create_token(user_id)
    decoded = decode_token(token)
    assert decoded == user_id

def test_decode_invalid_token_raises():
    import pytest
    from jose import JWTError
    with pytest.raises(JWTError):
        decode_token("not.a.valid.token")
