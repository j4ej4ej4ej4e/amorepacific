import streamlit as st
import os
import sys
import pandas as pd
from dotenv import load_dotenv

# 현재 디렉토리 및 상위 디렉토리의 모듈을 참조하기 위한 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
load_dotenv(os.path.join(current_dir, '.env'))

# search_influencer 모듈 가져오기
try:
    from search_influencer import generate_sql
    from db_connection import execute_query
except ImportError:
    st.error("search_influencer.py 또는 db_connection.py 파일을 찾을 수 없습니다.")
    st.stop()

st.set_page_config(page_title="Filtering for Real", page_icon="💇", layout="wide")

# ==============================================================================
# CSS & STYLE INJECTION
# ==============================================================================
st.markdown("""
<style>
    /* Google Fonts Import */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    /* Dark Background */
    .stApp {
        background-color: #0E1117;
    }

    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Card Component Style */
    .stContainer {
        border-radius: 12px;
        padding: 1rem;
        background-color: #ffffff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #f0f0f0;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .main .stContainer:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }
    
    /* Dark Mode Adjustment for Cards */
    @media (prefers-color-scheme: dark) {
        .stContainer {
            background-color: #262730;
            border-color: #3f3f3f;
        }
    }

    /* Gradient Header */
    .highlight-header {
        background: linear-gradient(90deg, #FF4B4B 0%, #6E3EF4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    
    .sub-header {
        color: #888;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    /* Metric Badges */
    .metric-badge {
        background-color: #f0f2f6;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #31333F;
        display: inline-block;
        margin-right: 0.5rem;
    }
    @media (prefers-color-scheme: dark) {
        .metric-badge {
            background-color: #3b3d45;
            color: #dcdcdc;
        }
    }

    /* Influencer Score Badge */
    .score-badge-high {
        background-color: #d1fae5;
        color: #065f46;
        padding: 0.25rem 0.75rem;
        border-radius: 99px;
        font-weight: bold;
        font-size: 0.9rem;
    }
    .score-badge-mid {
        background-color: #fffbeb;
        color: #92400e;
        padding: 0.25rem 0.75rem;
        border-radius: 99px;
        font-weight: bold;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# SIDEBAR UI
# ==============================================================================
with st.sidebar:
    st.markdown("### 🛠 Filters")
    st.caption("검색 결과 필터링 옵션")
    
    with st.container():
        platform = st.multiselect(
            "📍 플랫폼", 
            ["YouTube", "Instagram"], 
            default=["YouTube", "Instagram"]
        )
        min_subs = st.slider(
            "👥 최소 구독자/팔로워", 
            0, 10000000, 1000, 
            step=1000,
            format="%d명"
        )
    
    st.markdown("---")
    st.markdown("### 💡 Tips")
    st.info("""
    **검색 예시:**
    - "남성 왁스 리뷰하는 구독자 10만 이상 유튜버"
    - "비건 화장품 좋아하는 인스타 인플루언서"
    """)

# ==============================================================================
# MAIN UI
# ==============================================================================
st.markdown('<div class="highlight-header">💇 Filtering for Real </div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Influencer Discover & Curation Platform</div>', unsafe_allow_html=True)

# 검색창 영역
with st.container():
    query = st.text_input(
        "🔎 어떤 인플루언서를 찾으시나요?", 
        placeholder="예: 탈모 샴푸 리뷰를 잘하는 전문성 있는 유튜버 추천해줘"
    )

if query:
    st.markdown("---")
    with st.spinner("🧠 AI가 분석 중입니다..."):
        # 1. SQL 생성
        try:
            sql = generate_sql(query)
            
            if sql:
                # SQL 정제
                sql = sql.replace('```sql', '').replace('```', '').strip()
                
                # 2. 쿼리 실행
                try:
                    results = execute_query(sql)
                    df = pd.DataFrame(results) if results else pd.DataFrame()

                    # [필터링]
                    if 'confidence_score' in df.columns:
                        df['confidence_score'] = pd.to_numeric(df['confidence_score'], errors='coerce').fillna(0)
                        df = df[df['confidence_score'] > 50]
                    
                    # [보충 로직] - 별도 변수로 저장 (나중에 검색 결과 아래에 표시)
                    fallback_df = pd.DataFrame()
                    if len(df) < 10:
                        needed = 10 - len(df)

                        existing_ids = df['influencer_id'].tolist() if 'influencer_id' in df.columns else []
                        fallback_sql = """
                            SELECT i.influencer_id, i.name, i.confidence_score,
                                   c.channel_id, c.title AS channel_title, c.subscriber_count, c.thumbnail_url,
                                   ig.ig_username
                            FROM influencers i
                            LEFT JOIN yt_channels c ON i.influencer_id = c.influencer_id
                            LEFT JOIN ig_accounts ig ON i.influencer_id = ig.influencer_id
                            WHERE i.confidence_score > 50
                            ORDER BY i.confidence_score DESC
                            LIMIT 20
                        """
                        fallback_results = execute_query(fallback_sql)
                        
                        if fallback_results:
                            fallback_df = pd.DataFrame(fallback_results)
                            if 'influencer_id' in fallback_df.columns:
                                fallback_df = fallback_df[~fallback_df['influencer_id'].isin(existing_ids)]
                                fallback_df = fallback_df.drop_duplicates(subset=['influencer_id'])
                            fallback_df = fallback_df.head(needed)

                    if not df.empty:
                        # 중복 제거 및 정렬
                        if 'influencer_id' in df.columns:
                            df = df.drop_duplicates(subset=['influencer_id'])
                        elif 'name' in df.columns:
                            df = df.drop_duplicates(subset=['name'])

                        # 신뢰도 점수 50점 초과만 표시
                        if 'confidence_score' in df.columns:
                            df['confidence_score'] = pd.to_numeric(df['confidence_score'], errors='coerce').fillna(0)
                            df = df[df['confidence_score'] > 50]
                            df = df.sort_values(by='confidence_score', ascending=False)
                        
                        st.success(f"🎉 **{len(df)}명**의 최적 인플루언서를 발견했습니다!")

                        # ----------------------------------------------------------
                        # CARD LIST VIEW
                        # ----------------------------------------------------------
                        for idx, row in df.iterrows():
                            # 프로필 이미지 URL 결정 (썸네일 우선, 없으면 기본 아바타)
                            name = row.get('name', 'Unknown')
                            thumbnail_url = row.get('thumbnail_url')
                            if thumbnail_url and pd.notna(thumbnail_url) and str(thumbnail_url).lower() != 'nan':
                                avatar_url = thumbnail_url
                            else:
                                avatar_url = f"https://ui-avatars.com/api/?name={name}&background=random&size=128"

                            # 메인 카드 컨테이너
                            with st.container():
                                # 카드 내부 레이아웃
                                col_img, col_info, col_stat = st.columns([1.2, 5, 2])
                                
                                with col_img:
                                    st.image(avatar_url, width=90)
                                
                                with col_info:
                                    st.markdown(f"### {name}")
                                    
                                    # 태그/메타데이터
                                    tags = []
                                    channel_title = row.get('channel_title')
                                    if channel_title and pd.notna(channel_title) and str(channel_title).lower() != 'nan': 
                                        tags.append(f"📺 {channel_title}")
                                    sub_count = row.get('subscriber_count')
                                    if sub_count and pd.notna(sub_count): 
                                        tags.append(f"👥 구독자 {int(sub_count):,}명")
                                    
                                    if tags:
                                        st.markdown(" &nbsp;•&nbsp; ".join([f"**{t}**" for t in tags]))
                                    
                                    title = row.get('title')
                                    if title and pd.notna(title) and str(title).lower() != 'nan':
                                        st.caption(f"📝 {title}")
                                
                                with col_stat:
                                    # 유튜브 채널 링크 버튼
                                    channel_id = row.get('channel_id')
                                    if channel_id and pd.notna(channel_id) and str(channel_id).lower() != 'nan':
                                        yt_url = f"https://www.youtube.com/channel/{channel_id}"
                                        st.link_button("▶️ YouTube", yt_url)
                                    
                                    # 인스타그램 링크 버튼
                                    ig_username = row.get('ig_username')
                                    if ig_username and pd.notna(ig_username) and str(ig_username).lower() != 'nan':
                                        ig_url = f"https://www.instagram.com/{ig_username}"
                                        st.link_button("📷 Instagram", ig_url)
                                
                                st.markdown("---")
                        
                        # ----------------------------------------------------------
                        # 보충된 인플루언서 (검색 결과 아래에 표시)
                        # ----------------------------------------------------------
                        if not fallback_df.empty:
                            for idx, row in fallback_df.iterrows():
                                name = row.get('name', 'Unknown')
                                thumbnail_url = row.get('thumbnail_url')
                                if thumbnail_url and pd.notna(thumbnail_url) and str(thumbnail_url).lower() != 'nan':
                                    avatar_url = thumbnail_url
                                else:
                                    avatar_url = f"https://ui-avatars.com/api/?name={name}&background=random&size=128"

                                with st.container():
                                    col_img, col_info, col_stat = st.columns([1.2, 5, 2])
                                    
                                    with col_img:
                                        st.image(avatar_url, width=90)
                                    
                                    with col_info:
                                        st.markdown(f"### {name}")
                                        tags = []
                                        channel_title = row.get('channel_title')
                                        if channel_title and pd.notna(channel_title) and str(channel_title).lower() != 'nan': 
                                            tags.append(f"📺 {channel_title}")
                                        sub_count = row.get('subscriber_count')
                                        if sub_count and pd.notna(sub_count): 
                                            tags.append(f"👥 구독자 {int(sub_count):,}명")
                                        if tags:
                                            st.markdown(" &nbsp;•&nbsp; ".join([f"**{t}**" for t in tags]))
                                    
                                    with col_stat:
                                        channel_id = row.get('channel_id')
                                        if channel_id and pd.notna(channel_id) and str(channel_id).lower() != 'nan':
                                            yt_url = f"https://www.youtube.com/channel/{channel_id}"
                                            st.link_button("▶️ YouTube", yt_url)
                                        ig_username = row.get('ig_username')
                                        if ig_username and pd.notna(ig_username) and str(ig_username).lower() != 'nan':
                                            ig_url = f"https://www.instagram.com/{ig_username}"
                                            st.link_button("📷 Instagram", ig_url)
                                    
                                    st.markdown("---")
                        
                        # [SQL 보기 옵션 - 맨 하단에 배치]
                        with st.expander("🛠 Generated SQL Query (Debug)", expanded=False):
                            st.code(sql, language="sql") 

                    else:
                        st.error("검색 결과가 없습니다. 조건을 변경하여 다시 시도해주세요.")
                        
                except Exception as e:
                    st.error(f"시스템 오류가 발생했습니다: {e}")
            else:
                st.error("SQL 생성에 실패했습니다. 유요한 질의인지 확인해주세요.")
                
        except Exception as e_gen:
             st.error(f"SQL 생성 중 오류 발생: {e_gen}")

# ==============================================================================
# FOOTER
# ==============================================================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.8rem;">
    © 2025 Filtering for Real | Powered by <b>TiDB Serverless</b> & <b>Google Gemini</b>
</div>
""", unsafe_allow_html=True)
