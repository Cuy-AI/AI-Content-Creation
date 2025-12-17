from components.Search.YoutubeSearch.YoutubeSearch import YoutubeSearch

def test_youtubesearch():

    yts = YoutubeSearch()
    results = yts.search("Elon Musk launching rockets", max_results=3)

    print("Youtube Search Results:")
    for r in results: print(r)