import requests
import json
import os
from dotenv import load_dotenv
import datetime

# Get API key from .env file
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

# Calculate the date one month ago in RFC 3339 format
published_after = (datetime.datetime.now() - datetime.timedelta(days=365)).isoformat() + "Z"

# YouTube API endpoint
url = "https://www.googleapis.com/youtube/v3/search"

# Request parameters
params = {
    "key": API_KEY,
    "part": "snippet",
    "maxResults": 50, # Max per request is 50, default is 5
    "topicId": "/m/09s1f",
    # "order": "viewCount", #  This will break the language search and return the most viewed v"ideos in ALL LANGUAGES
    "order": "relevance", # relevance is default
    # "publishedAfter": "2025-01-01T00:00:00Z", # This returns english videos if the datetime is not minimum 5 years ago
    "relevanceLanguage": "en",
    "regionCode": "US", # Adding this might make a difference
    "type": "video",
    "videoCaption": "closedCaption",
    # "videoCategoryId": "25",
    "videoDuration": "medium",
    "videoEmbeddable": "true",
}

# Make the API request
response = requests.get(url, params=params)
data = response.json()

# Save response to a JSON file
output_file = "/Users/martin/Documents/GitHub/Zeeguu/api/tools/yt_search_response.json"
with open(output_file, "w", encoding="utf-8") as json_file:
    json.dump(data, json_file, indent=4, ensure_ascii=False)

print(f"Response saved to {output_file}")
