import os

import aiohttp

from utils.errors import YoutubeFetchFailure

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


async def fetch_last_video(youtube_id: str) -> str:
    async with aiohttp.ClientSession() as session:
        r = await session.get(
            "https://www.googleapis.com/youtube/v3/activities",
            params={
                "key": GOOGLE_API_KEY,
                "part": "contentDetails",
                "channelId": youtube_id,
                "maxResults": 1,
            },
        )
        if r.status == 200:
            try:
                data = await r.json()
                return data["items"][0]["contentDetails"]["upload"]["videoId"]
            except KeyError:
                raise YoutubeFetchFailure(youtube_id)
        else:
            raise YoutubeFetchFailure(youtube_id)
