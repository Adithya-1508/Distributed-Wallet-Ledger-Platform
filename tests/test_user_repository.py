from app.repositories.user_repo import UserRepository

def test_create_and_fetch_user(db):
    repo = UserRepository(db)

    user = repo.create(
        name= "Adithya", email="adithya@example.com", password_hash="hashed"
    )

    assert user.id is not True
    assert user.email == "adithya@example.com"

    fetched = repo.get_by_email("adithya@example.com")
    assert fetched is not None
    assert fetched.id == user.id

def test_get_by_email_returns_none_when_missing(db):
    repo = UserRepository(db)
    assert repo.get_by_email("nobody@example.com") is None    