"""
YouTube 채널 및 영상 데이터 수집기
- 채널 정보: channel_title, channel_id, subscriber_count, total_view_count, video_count, channel_description, channel_keywords
- 영상 정보: video_title, published_at, view_count, like_count, comment_count, video_description, video_tags, duration, thumbnail_url
"""
import yt_dlp
from datetime import datetime


class YouTubeCollector:
    def __init__(self):
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
    
    def search_channels(self, keyword: str, limit: int = 20) -> list:
        """
        키워드로 영상을 검색하여 채널 목록 추출
        """
        print(f"[검색] 키워드: '{keyword}' (최대 {limit}개 영상 스캔)")
        
        opts = {
            **self.base_opts,
            'extract_flat': True,
        }
        
        query = f"ytsearch{limit}:{keyword}"
        channels = {}
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                result = ydl.extract_info(query, download=False)
                if 'entries' in result:
                    for video in result['entries']:
                        if not video:
                            continue
                        
                        channel_id = video.get('channel_id')
                        if channel_id and channel_id not in channels:
                            channels[channel_id] = {
                                'channel_id': channel_id,
                                'channel_title': video.get('channel'),
                                'channel_url': video.get('channel_url'),
                            }
            except Exception as e:
                print(f"[오류] 검색 실패: {e}")
        
        print(f"[완료] {len(channels)}개 채널 발견")
        return list(channels.values())
    
    def get_channel_info(self, channel_url: str) -> dict:
        """
        채널 상세 정보 수집
        """
        opts = {
            **self.base_opts,
            'extract_flat': True,
            'playlist_items': '0',  # 채널 메타데이터만
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(channel_url, download=False)
                
                return {
                    'channel_title': info.get('channel') or info.get('uploader'),
                    'channel_id': info.get('channel_id') or info.get('uploader_id'),
                    'subscriber_count': info.get('channel_follower_count'),
                    'total_view_count': info.get('view_count'),  # 채널 총 조회수
                    'video_count': info.get('playlist_count'),
                    'channel_description': info.get('description', ''),
                    'channel_keywords': info.get('tags', []),
                }
            except Exception as e:
                print(f"[오류] 채널 정보 수집 실패: {e}")
                return None
    
    def get_recent_videos(self, channel_url: str, limit: int = 5) -> list:
        """
        채널의 최근 영상 목록 수집
        """
        # /videos 탭으로 접근
        videos_url = channel_url.rstrip('/') + '/videos'
        
        opts = {
            **self.base_opts,
            'extract_flat': False,
            'playlistend': limit,
            'ignoreerrors': True,
        }
        
        videos = []
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                result = ydl.extract_info(videos_url, download=False)
                
                if 'entries' in result:
                    for entry in result['entries']:
                        if not entry:
                            continue
                        
                        # 업로드 날짜 포맷팅
                        upload_date = entry.get('upload_date')
                        if upload_date:
                            try:
                                published_at = datetime.strptime(upload_date, '%Y%m%d').strftime('%Y-%m-%d')
                            except:
                                published_at = upload_date
                        else:
                            published_at = None
                        
                        video_data = {
                            'video_title': entry.get('title'),
                            'video_id': entry.get('id'),
                            'published_at': published_at,
                            'view_count': entry.get('view_count'),
                            'like_count': entry.get('like_count'),
                            'comment_count': entry.get('comment_count'),
                            'video_description': entry.get('description', ''),
                            'video_tags': entry.get('tags', []),
                            'duration': entry.get('duration'),  # 초 단위
                            'thumbnail_url': entry.get('thumbnail'),
                        }
                        videos.append(video_data)
                        
            except Exception as e:
                print(f"[오류] 영상 목록 수집 실패: {e}")
        
        return videos
    
    def collect_channel_data(self, channel_url: str, video_limit: int = 5) -> dict:
        """
        채널 정보 + 최근 영상 정보를 통합 수집
        """
        # 1. 채널 정보 수집
        channel_info = self.get_channel_info(channel_url)
        if not channel_info:
            return None
        
        subs = channel_info.get('subscriber_count')
        subs_str = f"{subs:,}" if subs else "N/A"
        print(f"  📺 {channel_info['channel_title']} (구독자: {subs_str})")
        
        # 2. 최근 영상 수집
        recent_videos = self.get_recent_videos(channel_url, limit=video_limit)
        print(f"     └─ 최근 영상 {len(recent_videos)}개 수집")
        
        return {
            'channel_info': channel_info,
            'recent_videos': recent_videos,
        }
