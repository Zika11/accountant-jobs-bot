import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Accountant Jobs Tracker").sheet1

def log_application(job_id, user_id, status="pending"):
    sheet.append_row([job_id, user_id, status, datetime.now().isoformat()])
