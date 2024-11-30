import os
import time
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import subprocess
import concurrent.futures
from utils import progress_bar
from pyrogram import Client, filters
from pyrogram.types import Message

# Initialize logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Global variable
failed_counter = 0

def duration(filename):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", 
            "default=noprint_wrappers=1:nokey=1", filename],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return float(result.stdout)
    except Exception as e:
        logger.error(f"Error getting duration: {e}")
        return 0.0

def exec(cmd):
    try:
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = process.stdout.decode()
        logger.info(f"Command output: {output}")
        return output
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return None

def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        logger.info("Waiting for tasks to complete")
        executor.map(exec, cmds)

async def aio(url, name):
    k = f"{name}.pdf"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                async with aiofiles.open(k, mode="wb") as f:
                    await f.write(await resp.read())
    return k

async def download(url, name):
    ka = f"{name}.pdf"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                async with aiofiles.open(ka, mode="wb") as f:
                    await f.write(await resp.read())
    return ka

def parse_vid_info(info):
    info = info.strip().split("\n")
    new_info, temp = [], []
    for i in info:
        i = str(i).replace("  ", " ").strip()
        parts = i.split("|")[0].split(" ", 2)
        try:
            if "RESOLUTION" not in parts[2] and parts[2] not in temp and "audio" not in parts[2]:
                temp.append(parts[2])
                new_info.append((parts[0], parts[2]))
        except IndexError:
            pass
    return new_info

def vid_info(info):
    info = info.strip().split("\n")
    new_info, temp = {}, []
    for i in info:
        i = str(i).replace("  ", " ").strip()
        parts = i.split("|")[0].split(" ", 3)
        try:
            if "RESOLUTION" not in parts[2] and parts[2] not in temp and "audio" not in parts[2]:
                temp.append(parts[2])
                new_info[parts[2]] = parts[0]
        except IndexError:
            pass
    return new_info

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 1:
        return False
    return stdout.decode() if stdout else stderr.decode()

def old_download(url, file_name, chunk_size=1024 * 10):
    try:
        if os.path.exists(file_name):
            os.remove(file_name)
        r = requests.get(url, stream=True)
        with open(file_name, "wb") as fd:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    fd.write(chunk)
        return file_name
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

def human_readable_size(size, decimal_places=2):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0 or unit == "PB":
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now().strftime("%H%M%S")
    return f"{date} {now}.mp4"

async def download_video(url, cmd, name):
    global failed_counter
    download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'
    logger.info(f"Download command: {download_cmd}")
    k = subprocess.run(download_cmd, shell=True)
    if "visionias" in cmd and k.returncode != 0 and failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        await download_video(url, cmd, name)
    failed_counter = 0
    try:
        extensions = ["", ".webm", ".mkv", ".mp4", ".mp4.webm"]
        for ext in extensions:
            if os.path.isfile(f"{name}{ext}"):
                return f"{name}{ext}"
    except FileNotFoundError:
        return os.path.splitext(name)[0] + ".mp4"

async def send_doc(bot: Client, m: Message, cc, ka, cc1, prog, count, name):
    try:
        reply = await m.reply_text(f"**Uploading:** `{name}`\n**Made by Bhuriya Bot 😝.**")
        start_time = time.time()
        await m.reply_document(ka, caption=cc1, progress=progress_bar, progress_args=(reply, start_time))
        count += 1
        await reply.delete()
        os.remove(ka)
    except Exception as e:
        logger.error(f"Failed to send document: {e}")

async def send_vid(bot: Client, m: Message, cc, filename, thumb, name, prog):
    subprocess.run(f'ffmpeg -i "{filename}" -ss 00:01:00 -vframes 1 "{filename}.jpg"', shell=True)
    await prog.delete()
    reply = await m.reply_text(f"⬆️**Uploading:** `{name}`\n**Made by Bhuriya Bot 😝**")
    dur = int(duration(filename))
    try:
        thumbnail = thumb if thumb != "no" else f"{filename}.jpg"
        await m.reply_video(filename, caption=cc, supports_streaming=True, height=720, width=1280, thumb=thumbnail, duration=dur, progress=progress_bar, progress_args=(reply, time.time()))
    except Exception:
        await m.reply_document(filename, caption=cc, progress=progress_bar, progress_args=(reply, time.time()))
    finally:
        os.remove(filename)
        os.remove(f"{filename}.jpg")
        await reply.delete()
