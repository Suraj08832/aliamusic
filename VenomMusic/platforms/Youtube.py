import asyncio
import os
import re
import json
import random
from typing import Union

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from VenomMusic.utils.database import is_on_off
from VenomMusic.utils.formatters import time_to_seconds

# Updated API endpoint — no API key needed anymore
NEW_API_URL = "https://apikeyreal.vercel.app/api"

def cookie_txt_file():
    cookie_dir = os.path.join(os.getcwd(), "cookies")
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    return os.path.join(cookie_dir, random.choice(cookies_files))

async def search_song_api(query: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{NEW_API_URL}/search?q={query}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[0] if data else None
    except Exception as e:
        print(f"Error searching with new API: {e}")
    return None

async def download_song_new_api(video_id: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{NEW_API_URL}/download/{video_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "success":
                        return data.get("url")
    except Exception as e:
        print(f"Error downloading with new API: {e}")
    return None

async def download_song(link: str):
    video_id = link.split('v=')[-1].split('&')[0]
    download_folder = "downloads"
    os.makedirs(download_folder, exist_ok=True)

    for ext in ["mp3", "m4a", "webm"]:
        path = os.path.join(download_folder, f"{video_id}.{ext}")
        if os.path.exists(path):
            return path

    # Try new API first
    try:
        dl_url = await download_song_new_api(video_id)
        if dl_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(dl_url) as resp:
                    if resp.status == 200:
                        file_path = os.path.join(download_folder, f"{video_id}.mp3")
                        with open(file_path, "wb") as f:
                            while chunk := await resp.content.read(8192):
                                f.write(chunk)
                        return file_path
    except Exception as e:
        print(f"New API failed, cannot download via API: {e}")

    # If both API paths fail, return None
    return None

async def check_file_size(link: str):
    async def get_info():
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--cookies", cookie_txt_file(), "-J", link,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return None if proc.returncode != 0 else json.loads(stdout.decode())

    info = await get_info()
    if not info or not (formats := info.get("formats")):
        return None

    return sum(fmt.get("filesize", 0) for fmt in formats)

async def shell_cmd(cmd: str):
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    return out.decode() if not err else err.decode()

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        link = self.base + link if videoid else link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type in (MessageEntityType.URL,):
                    return text[ent.offset:ent.offset + ent.length]
            for ent in entities:
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        video_id = link.split("v=")[-1].split("&")[0] if "watch?v=" in link else link
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{NEW_API_URL}/info/{video_id}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "success":
                            info = data.get("data", {})
                            duration = info.get("duration", "0:00")
                            duration_sec = int(time_to_seconds(duration)) if duration and duration != "None" else 0
                            return info.get("title", ""), duration, duration_sec, info.get("thumbnail", ""), video_id
        except Exception as e:
            print(f"New API details failed: {e}")

        results = await VideosSearch(link, limit=1).next()
        res = results["result"][0]
        duration = res["duration"] or "0:00"
        seconds = int(time_to_seconds(duration)) if duration != "None" else 0
        return res["title"], duration, seconds, res["thumbnails"][0]["url"].split("?")[0], res["id"]

    async def title(self, link: str, videoid: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        try:
            vid = link.split("v=")[-1].split("&")[0]
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{NEW_API_URL}/info/{vid}") as resp:
                    if resp.status == 200 and (data := await resp.json()).get("status") == "success":
                        return data["data"].get("title", "")
        except Exception as e:
            print(f"New API title failed: {e}")
        res = await VideosSearch(link, limit=1).next()
        return res["result"][0]["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        try:
            vid = link.split("v=")[-1].split("&")[0]
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{NEW_API_URL}/info/{vid}") as resp:
                    if resp.status == 200 and (data := await resp.json()).get("status") == "success":
                        return data["data"].get("duration", "0:00")
        except Exception as e:
            print(f"New API duration failed: {e}")
        res = await VideosSearch(link, limit=1).next()
        return res["result"][0]["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        try:
            vid = link.split("v=")[-1].split("&")[0]
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{NEW_API_URL}/info/{vid}") as resp:
                    if resp.status == 200 and (data := await resp.json()).get("status") == "success":
                        return data["data"].get("thumbnail", "")
        except Exception as e:
            print(f"New API thumbnail failed: {e}")
        res = await VideosSearch(link, limit=1).next()
        return res["result"][0]["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        vid = link.split("v=")[-1].split("&")[0]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{NEW_API_URL}/stream/{vid}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "success":
                            return 1, data.get("url", "")
        except Exception as e:
            print(f"New API stream failed: {e}")

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--cookies", cookie_txt_file(), "-g",
            "-f", "best[height<=?720][width<=?1280]", link,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return (1, out.decode().splitlines()[0]) if out else (0, err.decode())

    async def playlist(self, link: str, limit: int, user_id, videoid: Union[bool, str] = None):
        link = (self.listbase + link) if videoid else link
        cmd = f'yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download "{link}"'
        playlist = await shell_cmd(cmd)
        return [ln for ln in playlist.splitlines() if ln]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        vid = link.split("v=")[-1].split("&")[0]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{NEW_API_URL}/info/{vid}") as resp:
                    if resp.status == 200 and (data := await resp.json()).get("status") == "success":
                        info = data["data"]
                        return ({ "title": info.get("title", ""),
                                  "link": f"https://www.youtube.com/watch?v={vid}",
                                  "vidid": vid,
                                  "duration_min": info.get("duration", "0:00"),
                                  "thumb": info.get("thumbnail", "") }, vid)
        except Exception as e:
            print(f"New API track failed: {e}")

        res = await VideosSearch(link, limit=1).next()
        r = res["result"][0]
        return ({ "title": r["title"], "link": r["link"], "vidid": r["id"],
                  "duration_min": r["duration"], "thumb": r["thumbnails"][0]["url"].split("?")[0] }, r["id"])

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        ydl_opts = {"quiet": True, "cookiefile" : cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ydl_opts)
        info = ydl.extract_info(link, download=False)
        fmts = []
        for fmt in info.get("formats", []):
            if 'dash' not in fmt.get("format", "").lower():
                keys = ("format", "filesize", "format_id", "ext", "format_note")
                if all(k in fmt for k in keys):
                    fmts.append({
                        k: fmt[k] for k in keys
                    } | {"yturl": link})
        return fmts, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{NEW_API_URL}/search?q={link}&limit=10") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if len(data) > query_type:
                            r = data[query_type]
                            return r.get("title", ""), r.get("duration", "0:00"), r.get("thumbnail", ""), r.get("video_id", "")
        except Exception as e:
            print(f"New API slider failed: {e}")

        res = await VideosSearch(link, limit=10).next()["result"][query_type]
        return res["title"], res["duration"], res["thumbnails"][0]["url"].split("?")[0], res["id"]

    async def download(self, link: str, mystic, video: Union[bool, str] = None,
                        videoid: Union[bool, str] = None,
                        songaudio: Union[bool, str] = None,
                        songvideo: Union[bool, str] = None,
                        format_id: Union[bool, str] = None,
                        title: Union[bool, str] = None):
        link = (self.base + link) if videoid else link
        loop = asyncio.get_running_loop()

        def dl_audio():
            opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            ydl = yt_dlp.YoutubeDL(opts)
            i = ydl.extract_info(link, download=False)
            path = os.path.join("downloads", f"{i['id']}.{i['ext']}")
            if os.path.exists(path):
                return path
            ydl.download([link])
            return path

        def dl_video():
            opts = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            ydl = yt_dlp.YoutubeDL(opts)
            i = ydl.extract_info(link, download=False)
            path = os.path.join("downloads", f"{i['id']}.{i['ext']}")
            if os.path.exists(path):
                return path
            ydl.download([link])
            return path

        if songvideo or songaudio:
            result = await download_song(link)
            if result:
                return result
            func = dl_video if songvideo else dl_audio
            return await loop.run_in_executor(None, func)

        if video:
            direct = True
            result = await download_song(link)
            if not result:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp", "--cookies", cookie_txt_file(), "-g", "-f", "best[height<=?720][width<=?1280]", link,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                out, err = await proc.communicate()
                if out:
                    return out.decode().splitlines()[0], False
                size = await check_file_size(link)
                if size and (size_mb := size / (1024 ** 2)) <= 100:
                    return await loop.run_in_executor(None, dl_video), True
            else:
                return result, direct

        result = await download_song(link)
        return (result or await loop.run_in_executor(None, dl_audio), True)
