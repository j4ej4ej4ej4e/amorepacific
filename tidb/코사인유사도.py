"""
HairMatch AI - 로컬 임베딩 버전 (sentence-transformers)
TensorFlow 없이 순수 PyTorch만 사용
"""

# 설치 가이드
"""
========================================
설치 순서 (중요!)
========================================

1. TensorFlow 완전 제거:
pip uninstall tensorflow tensorflow-gpu tf-keras keras -y

2. PyTorch CPU 버전 설치:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

3. sentence-transformers 설치:
pip install sentence-transformers

4. 기타 패키지:
pip install pymysql pandas numpy scikit-learn

5. 환경 변수 설정 (PowerShell):
$env:SENTENCE_TRANSFORMERS_BACKEND="pytorch"

또는 코드 최상단에 추가:
import os
os.environ['SENTENCE_TRANSFORMERS_BACKEND'] = 'pytorch'

========================================
"""

import pymysql
import ssl
import numpy as np
import pandas as pd
from typing import List, Dict
from datetime import datetime
import os

# PyTorch 백엔드 강제 설정
os.environ['SENTENCE_TRANSFORMERS_BACKEND'] = 'pytorch'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # TensorFlow 경고 숨김

# sentence-transformers import
try:
    from sentence_transformers import SentenceTransformer
    print("✅ sentence-transformers 로드 성공\n")
except ImportError as e:
    print("❌ sentence-transformers 설치 필요:")
    print("   pip install sentence-transformers")
    exit(1)

# TiDB 접속 정보
DB_CONFIG = {
    'host': 'gateway01.ap-northeast-1.prod.aws.tidbcloud.com',
    'port': 4000,
    'user': '3L6DrudtY9pp6uz.root',
    'password': 'G3kCbZSpzthPGm1Q',
    'database': 'amore',
    'charset': 'utf8mb4'
}


class LocalSemanticMatcher:
    """로컬 임베딩 모델 기반 매칭"""
    
    def __init__(self):
        print("="*100)
        print("🎯 HairMatch AI - 로컬 임베딩 매칭 시스템")
        print("="*100)
        print("🤖 모델: jhgan/ko-sroberta-multitask (한국어 특화)")
        print("💻 방식: 로컬 실행 (API 불필요)")
        print("="*100 + "\n")
        
        self.db_connection = None
        
        # 임베딩 모델 로드 (첫 실행 시 다운로드 ~500MB)
        print("🔄 임베딩 모델 로드 중...")
        print("  (첫 실행 시 모델 다운로드: ~500MB, 3-5분 소요)\n")
        
        self.model = SentenceTransformer('jhgan/ko-sroberta-multitask')
        
        print("✅ 모델 로드 완료!\n")
        
        # 캐시
        self.influencer_profiles = None
        self.influencer_embeddings = None
        self.content_texts = None
    
    def connect_db(self):
        """TiDB 연결"""
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.db_connection = pymysql.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset=DB_CONFIG['charset'],
                ssl=ssl_context,
                cursorclass=pymysql.cursors.DictCursor
            )
            print("✅ TiDB 연결 성공\n")
            return True
        except Exception as e:
            print(f"❌ TiDB 연결 실패: {e}")
            return False
    
    def close_db(self):
        """DB 연결 종료"""
        if self.db_connection:
            self.db_connection.close()
    
    def build_content_text(self, inf: Dict) -> str:
        """콘텐츠를 텍스트로 변환"""
        
        content_parts = []
        
        # Instagram
        if inf.get('profile_biography'):
            bio = str(inf['profile_biography'])
            if bio != 'None':
                content_parts.append(bio[:300])
        
        # YouTube 채널
        if inf.get('yt_channel_title'):
            content_parts.append(inf['yt_channel_title'])
        
        if inf.get('yt_description'):
            desc = str(inf['yt_description'])
            if desc != 'None':
                content_parts.append(desc[:300])
        
        # 비디오 제목 (최대 20개)
        video_titles = inf.get('video_titles', [])
        if video_titles:
            content_parts.extend(video_titles[:20])
        
        # 비디오 설명 (최대 10개)
        video_descriptions = inf.get('video_descriptions', [])
        if video_descriptions:
            for desc in video_descriptions[:10]:
                if desc and str(desc) != 'None':
                    content_parts.append(str(desc)[:200])
        
        # 태그
        video_tags = inf.get('video_tags', [])
        if video_tags:
            content_parts.extend(video_tags[:30])
        
        return " ".join(content_parts)
    
    def load_influencers_with_videos(self, limit: int = None):
        """인플루언서 + 비디오 정보 로드"""
        
        print("📂 인플루언서 및 콘텐츠 데이터 로드 중...")
        
        cursor = self.db_connection.cursor()
        
        query_influencers = """
        SELECT 
            i.influencer_id,
            i.name,
            i.confidence_score,
            ig.ig_username,
            ig.follower_count,
            ig.engagement_rate,
            ig.profile_biography,
            yc.channel_id,
            yc.title as yt_channel_title,
            yc.description as yt_description,
            yc.subscriber_count
        FROM influencers i
        LEFT JOIN ig_accounts ig ON i.influencer_id = ig.influencer_id
        LEFT JOIN yt_channels yc ON i.influencer_id = yc.influencer_id
        WHERE i.category = 'hair'
        """
        
        if limit:
            query_influencers += f" LIMIT {limit}"
        
        cursor.execute(query_influencers)
        influencers = cursor.fetchall()
        
        print(f"  인플루언서: {len(influencers)}명 로드")
        
        # YouTube 비디오 정보
        print(f"  YouTube 비디오 정보 로드 중...")
        
        for inf in influencers:
            channel_id = inf.get('channel_id')
            
            if not channel_id:
                inf['video_titles'] = []
                inf['video_descriptions'] = []
                inf['video_tags'] = []
                continue
            
            query_videos = """
            SELECT title, description, tags
            FROM yt_videos
            WHERE channel_id = %s
            ORDER BY published_at DESC
            LIMIT 50
            """
            
            cursor.execute(query_videos, (channel_id,))
            videos = cursor.fetchall()
            
            inf['video_titles'] = [v['title'] for v in videos if v.get('title')]
            inf['video_descriptions'] = [v['description'] for v in videos if v.get('description')]
            
            all_tags = []
            for v in videos:
                tags = v.get('tags', '')
                if tags and str(tags) != 'None':
                    if isinstance(tags, str) and tags.startswith('['):
                        import json
                        try:
                            tag_list = json.loads(tags)
                            all_tags.extend(tag_list)
                        except:
                            all_tags.append(tags)
                    else:
                        all_tags.append(str(tags))
            
            inf['video_tags'] = all_tags
        
        cursor.close()
        print(f"✅ 로드 완료\n")
        
        return influencers
    
    def embed_content(self, influencers: List[Dict]):
        """콘텐츠를 임베딩 벡터로 변환"""
        
        print("🔄 콘텐츠 텍스트 생성 중...")
        
        content_texts = []
        for inf in influencers:
            text = self.build_content_text(inf)
            content_texts.append(text)
        
        print(f"✅ {len(content_texts)}개 콘텐츠 텍스트 생성")
        
        text_lengths = [len(t) for t in content_texts]
        print(f"  평균 길이: {np.mean(text_lengths):.0f}자")
        print(f"  최대 길이: {max(text_lengths)}자\n")
        
        print("🤖 로컬 모델로 임베딩 생성 중...")
        print("  (879개 처리 시 약 1-2분 소요)\n")
        
        # 배치로 임베딩 생성 (빠름!)
        embeddings = self.model.encode(
            content_texts,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        print(f"\n✅ 임베딩 완료: shape={embeddings.shape}\n")
        
        # 캐시 저장
        self.influencer_profiles = influencers
        self.influencer_embeddings = embeddings
        self.content_texts = content_texts
        
        return embeddings
    
    def search_by_keywords(self, keywords: List[str], top_k: int = 100) -> List[Dict]:
        """키워드로 의미 매칭"""
        
        print("="*100)
        print(f"🔍 의미 기반 매칭 시작")
        print("="*100)
        print(f"🔑 검색 키워드: {', '.join(keywords)}")
        print(f"🎯 추출 목표: TOP {top_k}명\n")
        
        query_text = " ".join(keywords)
        
        print(f"🤖 검색 쿼리 임베딩 중...")
        query_embedding = self.model.encode([query_text], convert_to_numpy=True)[0]
        
        # 코사인 유사도
        print("🧮 코사인 유사도 계산 중...")
        
        from sklearn.metrics.pairwise import cosine_similarity
        
        similarities = cosine_similarity(
            [query_embedding],
            self.influencer_embeddings
        )[0]
        
        # TOP K
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # 결과 생성
        matches = []
        for idx in top_indices:
            profile = self.influencer_profiles[idx].copy()
            profile['match_score'] = float(similarities[idx])
            profile['rank'] = len(matches) + 1
            
            content = self.content_texts[idx].lower()
            matched_keywords = [kw for kw in keywords if kw.lower() in content]
            profile['matched_keywords'] = matched_keywords
            profile['content_preview'] = self.content_texts[idx][:200]
            
            matches.append(profile)
        
        print(f"✅ 매칭 완료: {len(matches)}명\n")
        
        match_scores = [m['match_score'] for m in matches]
        print(f"📊 매칭 점수 통계:")
        print(f"  최고: {max(match_scores):.4f}")
        print(f"  평균: {np.mean(match_scores):.4f}")
        print(f"  최저: {min(match_scores):.4f}\n")
        
        return matches
    
    def display_results(self, matches: List[Dict], show_top: int = 10):
        """결과 출력"""
        
        print("="*100)
        print(f"📊 매칭 결과 - TOP {show_top}")
        print("="*100 + "\n")
        
        for i, match in enumerate(matches[:show_top], 1):
            print(f"{'='*100}")
            print(f"🏆 Rank #{i} - 의미 유사도: {match['match_score']:.4f}")
            print(f"{'='*100}")
            
            print(f"\n📌 기본 정보")
            print(f"  ID: {match['influencer_id']}")
            print(f"  이름: {match.get('name', 'N/A')}")
            
            if match.get('matched_keywords'):
                print(f"  ✅ 직접 매칭: {', '.join(match['matched_keywords'])}")
            else:
                print(f"  🔄 의미적 매칭")
            
            print(f"\n📄 콘텐츠 미리보기:")
            preview = match.get('content_preview', '')[:150]
            print(f"  {preview}...")
            
            if match.get('ig_username'):
                print(f"\n📱 Instagram")
                print(f"  계정: @{match['ig_username']}")
                print(f"  팔로워: {match.get('follower_count', 0):,}명")
                print(f"  참여율: {match.get('engagement_rate', 0):.2f}%")
            
            if match.get('yt_channel_title'):
                print(f"\n🎬 YouTube")
                print(f"  채널: {match['yt_channel_title']}")
                print(f"  구독자: {match.get('subscriber_count', 0):,}명")
                
                video_titles = match.get('video_titles', [])
                if video_titles:
                    print(f"  최근 비디오:")
                    for vt in video_titles[:3]:
                        print(f"    - {vt}")
            
            print("\n")
        
        print("="*100 + "\n")
    
    def save_results(self, matches: List[Dict], filename: str = 'local_semantic_matched.csv'):
        """결과 저장"""
        
        print(f"💾 결과 저장 중: {filename}")
        
        df = pd.DataFrame(matches)
        
        columns = [
            'rank', 'match_score', 'matched_keywords', 'content_preview',
            'influencer_id', 'name', 
            'ig_username', 'follower_count', 'engagement_rate',
            'yt_channel_title', 'subscriber_count'
        ]
        
        available_columns = [col for col in columns if col in df.columns]
        df_export = df[available_columns]
        
        if 'matched_keywords' in df_export.columns:
            df_export.loc[:, 'matched_keywords'] = df_export['matched_keywords'].apply(
                lambda x: ', '.join(x) if isinstance(x, list) else ''
            )
        
        df_export.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print(f"✅ 저장 완료: {len(df_export)}개 레코드\n")
        
        return filename
    
    def run(self, keywords: List[str], top_k: int = 100, show_top: int = 10,
            save_csv: bool = True, data_limit: int = None):
        """전체 프로세스"""
        
        start_time = datetime.now()
        
        try:
            if not self.connect_db():
                return None
            
            if self.influencer_embeddings is None:
                influencers = self.load_influencers_with_videos(limit=data_limit)
                self.embed_content(influencers)
            else:
                print("✅ 캐시된 임베딩 사용\n")
            
            matches = self.search_by_keywords(keywords, top_k)
            
            self.display_results(matches, show_top)
            
            if save_csv:
                csv_file = self.save_results(matches)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            print("="*100)
            print("✅ 의미 기반 매칭 완료")
            print("="*100)
            print(f"⏱️  소요 시간: {elapsed:.2f}초")
            print(f"📊 전체 인플루언서: {len(self.influencer_profiles)}명")
            print(f"🎯 매칭 결과: {len(matches)}명")
            if save_csv:
                print(f"💾 CSV 파일: {csv_file}")
            print("="*100 + "\n")
            
            return matches
            
        except Exception as e:
            print(f"❌ 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        finally:
            self.close_db()


def main():
    """메인 함수"""
    
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║          HairMatch AI - 로컬 의미 매칭 (sentence-transformers)             ║
║                                                                            ║
║  🤖 특징: 단어가 없어도 의미적으로 유사하면 매칭!                           ║
║  💻 방식: 로컬 실행 (API 불필요, 무료)                                      ║
║  📦 예시: "왁스" → "헤어 스타일링", "제품 리뷰"도 매칭                      ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    system = LocalSemanticMatcher()
    
    examples = [
        ["왁스", "스타일링"],
        ["C컬", "펌"],
        ["컬크림", "웨이브"],
        ["에센스", "손상모발"],
        ["짧은머리", "남성"],
    ]
    
    print("📋 예시:")
    for i, ex in enumerate(examples, 1):
        print(f"  {i}. {', '.join(ex)}")
    
    print("\n" + "="*100)
    user_input = input("💬 키워드 입력 (쉼표로 구분, Enter=예시1): ").strip()
    
    if not user_input:
        keywords = examples[0]
        print(f"선택: {', '.join(keywords)}")
    else:
        keywords = [k.strip() for k in user_input.split(',') if k.strip()]
    
    top_k = input("🔢 추출할 인플루언서 수 (기본=100): ").strip()
    top_k = int(top_k) if top_k.isdigit() else 100
    
    show_top = input("📺 화면 출력 개수 (기본=10): ").strip()
    show_top = int(show_top) if show_top.isdigit() else 10
    
    print("\n")
    
    matches = system.run(
        keywords=keywords,
        top_k=top_k,
        show_top=show_top,
        save_csv=True,
        data_limit=None  # 테스트: 100
    )
    
    if matches:
        print("🎉 매칭 성공!")
        print("📁 'local_semantic_matched.csv' 파일을 2단계 팀원에게 전달하세요.")


if __name__ == "__main__":
    main()