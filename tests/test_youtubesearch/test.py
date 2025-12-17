from components.Search.YoutubeSearch.YoutubeSearch import YoutubeSearch

def test_youtubesearch():

    yts = YoutubeSearch()
    results = yts.search("Elon Musk launching rockets", max_results=3)

    print("Youtube Search Results:")
    for r in results: print(r)


    # Download the first video from the search results
    if results:
        first_video_url = results[0]['url']
        save_path = "volume/output/ytsearch/elon_musk_launch"
        downloaded_file = yts.download_video(first_video_url, save_path)
        print(f"Video downloaded to: {downloaded_file}")