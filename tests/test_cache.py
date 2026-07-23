import os
import pytest
from storage.cache import SemanticCache

@pytest.fixture
def cache():
    db_path = "./test_semantic_cache.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    c = SemanticCache(db_path=db_path)
    yield c
    c.close()
    if os.path.exists(db_path):
        os.remove(db_path)

def test_semantic_cache(cache):
    # Set cached answer
    cache.set_cached_answer("How to fetch user?", "repo-a", "Use get_user()", ["main.py"])
    
    # Exact query match
    res1 = cache.get_cached_answer("How to fetch user?", "repo-a")
    assert res1 is not None
    assert res1["answer"] == "Use get_user()"
    assert res1["sources"] == ["main.py"]
    
    # Very similar query match
    res2 = cache.get_cached_answer("how do I fetch a user?", "repo-a")
    assert res2 is not None
    assert res2["answer"] == "Use get_user()"
    assert "similarity" in res2
    
    # Different repo match (should fail)
    res3 = cache.get_cached_answer("How to fetch user?", "repo-b")
    assert res3 is None
    # completely different query
    res4 = cache.get_cached_answer("How to configure database?", "repo-a")
    assert res4 is None

def test_cache_clear(cache):
    # Set cached answer
    cache.set_cached_answer("How to fetch user?", "repo-a", "Use get_user()", ["main.py"])
    
    # Exact query match before clear
    res1 = cache.get_cached_answer("How to fetch user?", "repo-a")
    assert res1 is not None
    
    # Clear cache
    cache.clear()
    
    # Check that it's empty
    res2 = cache.get_cached_answer("How to fetch user?", "repo-a")
    assert res2 is None
