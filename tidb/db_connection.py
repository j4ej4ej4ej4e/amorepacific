"""
TiDB Cloud 데이터베이스 연결 모듈
"""
import os
import mysql.connector
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


def get_connection():
    """
    TiDB Cloud 데이터베이스 연결을 생성하고 반환합니다.
    
    Returns:
        mysql.connector.connection: 데이터베이스 연결 객체
    """
    try:
        connection = mysql.connector.connect(
            host=os.getenv('TIDB_HOST'),
            port=int(os.getenv('TIDB_PORT', 4000)),
            user=os.getenv('TIDB_USER'),
            password=os.getenv('TIDB_PASSWORD'),
            database=os.getenv('TIDB_DATABASE', 'test'),
            ssl_disabled=False,
            ssl_verify_cert=False,
            ssl_verify_identity=False
        )
        return connection
    except mysql.connector.Error as e:
        print(f"DB connection failed: {e}")
        raise


def test_connection():
    """
    TiDB Cloud 연결을 테스트합니다.
    """
    connection = None
    cursor = None
    
    try:
        connection = get_connection()
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"[SUCCESS] TiDB server version {db_info} connected successfully.")
            
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION();")
            record = cursor.fetchone()
            print(f"[INFO] Current database version: {record[0]}")
            
            return True
            
    except mysql.connector.Error as e:
        print(f"[ERROR] Connection failed: {e}")
        return False
        
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            print("[INFO] Connection closed.")


def execute_query(query, params=None, fetch=True):
    """
    SQL 쿼리를 실행합니다.
    
    Args:
        query (str): 실행할 SQL 쿼리
        params (tuple, optional): 쿼리 파라미터
        fetch (bool): 결과를 반환할지 여부 (SELECT 쿼리의 경우 True)
    
    Returns:
        list: fetch=True일 경우 쿼리 결과, 그렇지 않으면 None
    """
    connection = None
    cursor = None
    
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(query, params)
        
        if fetch:
            result = cursor.fetchall()
            return result
        else:
            connection.commit()
            return cursor.rowcount
            
    except mysql.connector.Error as e:
        print(f"Query execution failed: {e}")
        if connection:
            connection.rollback()
        raise
        
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    # 연결 테스트 실행
    test_connection()
