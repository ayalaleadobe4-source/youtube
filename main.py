from fastapi import FastAPI, Query, BackgroundTasks
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import yt_dlp
import os
import json

app = FastAPI()

# הגדרות Google Drive (נשאר כפי שהיה)
SCOPES = ['https://www.googleapis.com/auth/drive']
credentials_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT"])
credentials = service_account.Credentials.from_service_account_info(
    credentials_json, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)
FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# הפונקציה הכבדה - לא השתנתה הרבה, רק הוספתי הדפסות (Print) כדי שתראה לוגים ב-Railway
def download_and_upload(url: str, quality: str):
    try:
        print(f"Starting process for: {url}")
        ydl_opts = {
            "format": quality,
            "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        print(f"Download finished: {filename}. Starting upload to Drive...")

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

        os.remove(filename)
        print(f"Successfully uploaded! Drive ID: {file.get('id')}")

    except Exception as e:
        print(f"Error in background task: {str(e)}")

# ה-Endpoint החדש
@app.get("/download")
async def download_endpoint(
    background_tasks: BackgroundTasks, 
    url: str = Query(...), 
    quality: str = Query("best")
):
    # כאן קורה הקסם: הפונקציה נשלחת לתור של משימות רקע
    background_tasks.add_task(download_and_upload, url, quality)
    
    # השרת מחזיר תשובה מיד למשתמש
    return {"status": "success", "message": "ההורדה התחילה ברקע, הקובץ יופיע בדרייב בסיום"}
