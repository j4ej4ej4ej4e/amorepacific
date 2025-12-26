"""
YouTube 검색 및 메타데이터 수집 모듈
yt-dlp를 활용하여 키워드 검색 및 영상 메타데이터를 수집합니다.
"""
import yt_dlp
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import time
import re


@dataclass
class VideoMeta:
    """영상 메타데이터"""
    video_id: str
    title: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    channel_id: str = ""
    channel_title: str = ""
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    upload_date: str = ""  # YYYYMMDD 형식
    duration: int = 0  # 초 단위
    thumbnail_url: str = ""
    
    @property
    def upload_datetime(self) -> Optional[datetime]:
        """업로드 날짜를 datetime으로 변환"""
        if self.upload_date and len(self.upload_date) == 8:
            try:
                return datetime.strptime(self.upload_date, '%Y%m%d')
            except ValueError:
                pass
        return None
    
    @property
    def days_since_upload(self) -> Optional[int]:
        """업로드 후 경과일"""
        dt = self.upload_datetime
        if dt:
            return (datetime.now() - dt).days
        return None
    
    def get_all_text(self) -> str:
        """키워드 추출용 전체 텍스트"""
        texts = [
            self.title,
            self.description,
            ' '.join(self.tags),
        ]
        return ' '.join(texts)


class YouTubeSearcher:
    """
    yt-dlp 기반 YouTube 검색기
    
    키워드로 영상을 검색하고 메타데이터를 수집합니다.
    """
    
    def __init__(self, 
                 requests_per_minute: int = 30,
                 quiet: bool = True):
        """
        Args:
            requests_per_minute: 분당 최대 요청 수 (Rate Limiting)
            quiet: yt-dlp 출력 억제 여부
        """
        self.request_interval = 60 / requests_per_minute
        self.last_request_time = 0
        self.quiet = quiet
        
        self.base_opts = {
            'quiet': quiet,
            'no_warnings': quiet,
            'extract_flat': False,
            'ignoreerrors': True,
        }
    
    def _rate_limit(self):
        """Rate Limiting 적용"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self.last_request_time = time.time()
    
    def search(self, query: str, limit: int = 30) -> List[VideoMeta]:
        """
        키워드로 YouTube 검색
        
        Args:
            query: 검색 키워드
            limit: 최대 결과 수
            
        Returns:
            VideoMeta 리스트
        """
        self._rate_limit()
        
        opts = {
            **self.base_opts,
            'extract_flat': True,  # 빠른 검색을 위해 flat 모드
        }
        
        search_query = f"ytsearch{limit}:{query}"
        videos = []
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                result = ydl.extract_info(search_query, download=False)
                
                if not result or 'entries' not in result:
                    return videos
                
                for entry in result.get('entries', []):
                    if not entry:
                        continue
                    
                    # 기본 정보만 추출 (flat 모드)
                    video = VideoMeta(
                        video_id=entry.get('id', ''),
                        title=entry.get('title', ''),
                        channel_id=entry.get('channel_id', ''),
                        channel_title=entry.get('channel', '') or entry.get('uploader', ''),
                        view_count=entry.get('view_count', 0) or 0,
                        duration=entry.get('duration', 0) or 0,
                    )
                    videos.append(video)
                    
            except Exception as e:
                if not self.quiet:
                    print(f"[오류] 검색 실패 ({query}): {e}")
        
        return videos
    
    def get_video_details(self, video_id: str) -> Optional[VideoMeta]:
        """
        영상 상세 정보 수집
        
        Args:
            video_id: YouTube 영상 ID
            
        Returns:
            VideoMeta 또는 None
        """
        self._rate_limit()
        
        opts = {
            **self.base_opts,
            'extract_flat': False,
        }
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                return VideoMeta(
                    video_id=info.get('id', ''),
                    title=info.get('title', ''),
                    description=info.get('description', '') or '',
                    tags=info.get('tags', []) or [],
                    channel_id=info.get('channel_id', ''),
                    channel_title=info.get('channel', '') or info.get('uploader', ''),
                    view_count=info.get('view_count', 0) or 0,
                    like_count=info.get('like_count', 0) or 0,
                    comment_count=info.get('comment_count', 0) or 0,
                    upload_date=info.get('upload_date', ''),
                    duration=info.get('duration', 0) or 0,
                    thumbnail_url=info.get('thumbnail', ''),
                )
                
            except Exception as e:
                if not self.quiet:
                    print(f"[오류] 상세 정보 수집 실패 ({video_id}): {e}")
                return None
    
    def search_with_details(self, query: str, limit: int = 30, 
                            detail_limit: int = 10) -> List[VideoMeta]:
        """
        키워드 검색 후 상위 영상의 상세 정보까지 수집
        
        Args:
            query: 검색 키워드
            limit: 검색 결과 수
            detail_limit: 상세 정보 수집할 영상 수
            
        Returns:
            상세 정보가 포함된 VideoMeta 리스트
        """
        # 1. 기본 검색
        videos = self.search(query, limit=limit)
        
        if not videos:
            return []
        
        # 2. 상위 N개 영상의 상세 정보 수집
        detailed_videos = []
        for video in videos[:detail_limit]:
            detailed = self.get_video_details(video.video_id)
            if detailed:
                detailed_videos.append(detailed)
            else:
                detailed_videos.append(video)  # 실패 시 기본 정보 사용
        
        # 3. 나머지는 기본 정보만
        detailed_videos.extend(videos[detail_limit:])
        
        return detailed_videos
    
    def get_video_subtitles(self, video_id: str, lang: str = 'ko') -> Optional[str]:
        """
        영상 자막 추출 (키워드 채굴용)
        
        Args:
            video_id: YouTube 영상 ID
            lang: 자막 언어 코드
            
        Returns:
            자막 텍스트 또는 None
        """
        self._rate_limit()
        
        opts = {
            **self.base_opts,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': [lang, 'ko', 'en'],
            'skip_download': True,
        }
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # 자막 데이터 추출
                subtitles = info.get('subtitles', {}) or {}
                auto_subs = info.get('automatic_captions', {}) or {}
                
                # 수동 자막 우선
                sub_data = subtitles.get(lang) or subtitles.get('ko')
                if not sub_data:
                    # 자동 자막 사용
                    sub_data = auto_subs.get(lang) or auto_subs.get('ko')
                
                if sub_data:
                    # VTT 형식에서 텍스트만 추출
                    # (실제 구현에서는 자막 파일을 파싱해야 함)
                    return str(sub_data)
                    
            except Exception as e:
                if not self.quiet:
                    print(f"[오류] 자막 추출 실패 ({video_id}): {e}")
        
        return None
    
    def batch_search(self, queries: List[str], limit_per_query: int = 20) -> Dict[str, List[VideoMeta]]:
        """
        여러 키워드를 배치로 검색
        
        Args:
            queries: 검색 키워드 리스트
            limit_per_query: 키워드당 결과 수
            
        Returns:
            {키워드: VideoMeta 리스트} 딕셔너리
        """
        results = {}
        
        for i, query in enumerate(queries):
            if not self.quiet:
                print(f"[{i+1}/{len(queries)}] 검색 중: {query}")
            
            videos = self.search(query, limit=limit_per_query)
            results[query] = videos
        
        return results


if __name__ == "__main__":
    # 테스트
    searcher = YouTubeSearcher(quiet=False)
    
    print("=== YouTube 검색 테스트 ===")
    videos = searcher.search("허쉬컷 스타일링", limit=5)
    
    for v in videos:
        print(f"\n[{v.video_id}] {v.title}")
        print(f"  채널: {v.channel_title}")
        print(f"  조회수: {v.view_count:,}")
