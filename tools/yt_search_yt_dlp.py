import yt_dlp
import json

SEARCH_QUERY = "Danish animation"
FILTERS = "filter:medium filter:week filter:hd"

search_url = f"ytsearch10:{SEARCH_QUERY} {FILTERS}"

ydl_opts = {"quiet": True, "extract_flat": True}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    search_results = ydl.extract_info(search_url, download=False)
    
# print(search_results)

output_file = "/Users/martin/Documents/GitHub/Zeeguu/api/tools/yt_search_response.json"
with open(output_file, "w", encoding="utf-8") as json_file:
    json.dump(search_results, json_file, indent=4, ensure_ascii=False)

print(f"Response saved to {output_file}")
