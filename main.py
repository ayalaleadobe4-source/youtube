from fastapi import FastAPI, Query, BackgroundTasks
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import yt_dlp
import os
import json

app = FastAPI()

# ----------------------------
#  Google Drive Setup
# ----------------------------
SCOPES = ['https://www.googleapis.com/auth/drive']

# טעינת הרשאות ממשתנה הסביבה
try:
    credentials_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT"])
    credentials = service_account.Credentials.from_service_account_info(
        credentials_json, scopes=SCOPES
    )
    drive_service = build('drive', 'v3', credentials=credentials)
    FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]
except Exception as e:
    print(f"Critial Error: Could not initialize Google Drive: {e}")

# תיקיית הורדות זמנית
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ----------------------------
#  פונקציית העבודה (רצה ברקע)
# ----------------------------
def download_and_upload(url: str, quality: str):
    try:
        print(f"--- Starting background job for: {url} ---")
        
        ydl_opts = {
            "format": quality,
            "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
            "noplaylist": True,
        }

        # שלב ההורדה
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        print(f"Download complete: {filename}")

        # שלב ההעלאה לדרייב
        file_metadata = {
            'name': os.path.basename(filename),
            'parents': [FOLDER_ID]
        }
        media = MediaFileUpload(filename, resumable=True)
        
        print("Uploading to Google Drive...")
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        # ניקוי קבצים מהשרת
        if os.path.exists(filename):
            os.remove(filename)
            
        print(f"--- Process finished! Drive ID: {file.get('id')} ---")

    except Exception as e:
        print(f"--- Error in background process: {str(e)} ---")

# ----------------------------
#  Endpoint
# ----------------------------
@app.get("/download")
async def download_endpoint(
    url: str = Query(...),
    quality: str = Query("best"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # שולח את המשימה לרשימת ההמתנה וממשיך הלאה מיד
    background_tasks.add_task(download_and_upload, url, quality)
    
    return {
        "status": "processing",
        "message": "The download has started in the background. Check your Drive in a few minutes.",
        "details": {
            "url": url,
            "quality": quality
        }
    }
