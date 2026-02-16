from fastapi import FastAPI, Query, BackgroundTasks, Response
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import yt_dlp
import os
import json
import asyncio

app = FastAPI()

# ----------------------------
#  Google Drive Setup
# ----------------------------
SCOPES = ['https://www.googleapis.com/auth/drive']

# חייבים להגדיר משתנה סביבה GOOGLE_SERVICE_ACCOUNT עם תוכן JSON
credentials_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT"])
credentials = service_account.Credentials.from_service_account_info(
    credentials_json, scopes=SCOPES
)

drive_service = build('drive', 'v3', credentials=credentials)
FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]

# ----------------------------
#  Download directory
# ----------------------------
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ----------------------------
#  פונקציה שמורידה ומעלה ל-Drive
# ----------------------------
def download_and_upload(url: str, quality: str) -> dict:
    ydl_opts = {
        "format": quality,
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    # Upload ל-Drive
    file_metadata = {
        'name': os.path.basename(filename),
        'parents': [FOLDER_ID]
    }
    media = MediaFileUpload(filename, resumable=True)
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    # מוחק מקומית
    os.remove(filename)

    return {
        "title": info["title"],
        "url": url,
        "filename": os.path.basename(filename),
        "quality": quality,
        "drive_file_id": file.get("id")
    }

# ----------------------------
#  Endpoint
# ----------------------------
@app.get("/download")
async def download_endpoint(
    url: str = Query(...),
    quality: str = Query("best"),
    background_tasks: BackgroundTasks = None
):
    try:
        # להריץ ב-background כדי לא לחסום את ה-request
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, download_and_upload, url, quality)

        # ליצור JS Module
        js_code = f"""
export const videoData = {{
    title: "{result['title']}",
    url: "{result['url']}",
    filename: "{result['filename']}",
    quality: "{result['quality']}",
    drive_file_id: "{result['drive_file_id']}"
}};
"""
        return Response(content=js_code, media_type="application/javascript")

    except Exception as e:
        error_js = f"""
export const videoData = {{
    error: "{str(e)}"
}};
"""
        return Response(content=error_js, media_type="application/javascript")
