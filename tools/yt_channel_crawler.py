from datetime import datetime
import sys
from zeeguu.logging import log
import logging
import xml.etree.ElementTree as ET
from zeeguu.core.model import Video, YTChannel, db
import requests


# ------------------------------------------------------------
# This code is taken from article_crawler.py (START)
# ------------------------------------------------------------
logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
logging.getLogger("zeeguu.core").setLevel(logging.INFO)

start = datetime.now()
log(f"started at: {datetime.now()}")

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

if len(sys.argv) > 1:
    retrieve_videos_for_language(sys.argv[1])
else:
    retrieve_videos_from_all_feeds()

end = datetime.now()
log(f"done at: {end}")
log(f"total duration: {end - start}")

# ------------------------------------------------------------
# This code is taken from article_crawler.py (END)
# ------------------------------------------------------------

db_session = db.session


def retrive_videos_for_language(language_code: str):
    
    channels = YTChannel.query.filter_by(should_crawl=1, language_id=language_code).all()
    
    for channel in channels:


def get_yt_channels_to_crawl(language_code=None) -> list:
    if language_code:
        return YTChannel.query.filter_by(should_crawl=1, language_id=language_code).all()
    else:
        return YTChannel.query.filter_by(should_crawl=1).all()


def crawl_youtube_channel(channel_id: str, last_crawled: datetime):
    
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    try:
        response = requests.get(url)
        
        if response.status_code != 200:
            handle_broken_rss(channel_id, response.status_code)
            return 0
            
        root = ET.fromstring(response.content)
        new_videos_count = 0
        
        for video in root.findall('{http://www.w3.org/2005/Atom}entry'):
            published_str = video.find('{http://www.w3.org/2005/Atom}published').text
            published_at = datetime.strptime(published_str, '%Y-%m-%dT%H:%M:%S%z')
            
            if published_at > last_crawled:
                video_id = video.find('{http://www.youtube.com/xml/schemas/2015}videoId').text
                title = video.find('{http://www.w3.org/2005/Atom}title').text
                
                # Handle missing description
                description_element = video.find('{http://search.yahoo.com/mrss/}description')
                description = description_element.text if description_element is not None else ""
                
                # Get thumbnail URL from media:group/media:thumbnail
                media_group = video.find('{http://search.yahoo.com/mrss/}group')
                thumbnail_url = ""
                if media_group is not None:
                    thumbnail = media_group.find('{http://search.yahoo.com/mrss/}thumbnail')
                    if thumbnail is not None:
                        thumbnail_url = thumbnail.get('url', "")
                
                Video.find_or_create(
                    session=db_session,
                    video_id=video_id,
                    title=title,
                    description=description,
                    published_at=published_at,
                    channel=channel_id,
                    thumbnail_url=thumbnail_url,
                    duration=None,
                    language_id=None,
                    vtt=None,
                    plain_text=None
                )
                
                print(f"Created video: {title}")
                new_videos_count += 1
        
        return new_videos_count
        
    except Exception as e:
        register_broken_rss(channel_id, "Exception", str(e))
        return 0


def handle_broken_rss(channel_id):
    pass

    # TODO: Implement logging or database recording of the broken RSS feed
    # For example, you might want to:
    # - Log to a file
    # - Update a status field in the yt_channel table
    # - Send an alert email
    # - etc.


# Example usage
if __name__ == "__main__":
    channel_id = "UCfpCQ89W9wjkHc8J_6eTbBg"  # Example channel ID
    last_crawled = datetime(2025, 3, 1)
    new_videos = crawl_youtube_channel(channel_id, last_crawled)
    print(f"Added {new_videos} new videos from channel {channel_id}")