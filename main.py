from fastapi import FastAPI, Query, BackgroundTasks
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import yt_dlp
import os

app = FastAPI()

# ----------------------------
#  Google Drive Setup (OAuth2)
# ----------------------------
def get_drive_service():
    # קבלת המפתחות ממשתני הסביבה ב-Railway
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    
    # ריענון הטוקן אם הוא פג (קורה אוטומטית)
    if not creds.valid:
        creds.refresh(Request())
        
    return build('drive', 'v3', credentials=creds)

FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ----------------------------
#  פונקציית העבודה (רצה ברקע)
# ----------------------------
def download_and_upload(url: str, quality: str):
    try:
        print(f"--- Starting process for: {url} ---", flush=True)
        
        # התחברות לדרייב
        drive_service = get_drive_service()
        
        ydl_opts = {
            "format": quality,
            "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
            "noplaylist": True,
        }

        # שלב ההורדה מהמקור
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("Starting download to server...", flush=True)
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        print(f"File ready: {os.path.basename(filename)}. Starting upload to Drive...", flush=True)

        file_metadata = {
            'name': os.path.basename(filename),
            'parents': [FOLDER_ID]
        }
        
        media = MediaFileUpload(filename, resumable=True)
        request = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        )

        # מעקב התקדמות בלוגים
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%", flush=True)

        # ניקוי קבצים מהשרת בסיום
        if os.path.exists(filename):
            os.remove(filename)
            
        print(f"--- SUCCESS! Drive ID: {response.get('id')} ---", flush=True)

    except Exception as e:
        print(f"--- ERROR in background task: {str(e)} ---", flush=True)

# ----------------------------
#  Endpoint
# ----------------------------
@app.get("/download")
async def download_endpoint(
    url: str = Query(...),
    quality: str = Query("best"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # הפעלת המשימה ברקע
    background_tasks.add_task(download_and_upload, url, quality)
    
    return {
        "status": "started",
        "message": "The process has started. You can close this page and check your Drive later."
    }
