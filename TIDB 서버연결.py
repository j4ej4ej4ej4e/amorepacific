import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv() # .env 파일의 변수 로드

def connect_db():
    return mysql.connector.connect(
        host=os.getenv("TIDB_HOST"),
        port=os.getenv("TIDB_PORT"),
        user=os.getenv("TIDB_USER"),
        password=os.getenv("TIDB_PASSWORD"),
        database=os.getenv("TIDB_DATABASE"),
        ssl_verify_cert=True
    )
