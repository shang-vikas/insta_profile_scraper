from src.igscraper.utils import normalize_hashtags, criteria_example

def test_normalize_hashtags():
    caption = "This is a #test post with #multiple #hashtags"
    assert normalize_hashtags(caption) == ['#test', '#multiple', '#hashtags']

def test_criteria_example():
    metadata = {'likes': 150}
    assert criteria_example(metadata) == True
    
    metadata = {'likes': 50}
    assert criteria_example(metadata) == False
