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

st.set_page_config(page_title="HairMatch AI", page_icon="💇", layout="wide")

# 사이드바 설정
with st.sidebar:
    st.title("Filters")
    platform = st.multiselect("플랫폼", ["YouTube", "Instagram"], default=["YouTube", "Instagram"])
    min_subs = st.slider("최소 구독자/팔로워", 0, 1000000, 10000, step=10000)
    
    st.info("💡 자연어로 검색하면 AI가 SQL을 생성합니다.")

# 메인 UI
st.title("💇 HairMatch AI v2.0")
st.markdown("인플루언서 큐레이션")

# 검색창
query = st.text_input("원하는 인플루언서 조건을 입력하세요", placeholder="예: 남성 헤어 컬크림 리뷰하는 구독자 5만명 이상 유튜버 찾아줘")

if query:
    with st.spinner("AI가 분석 중입니다..."):
        # 1. SQL 생성
        sql = generate_sql(query)
        
        if sql:
            # SQL 정제
            sql = sql.replace('```sql', '').replace('```', '').strip()
            
            with st.expander("🔍 생성된 SQL Query 보기"):
                st.code(sql, language="sql")
            
            # 2. 쿼리 실행
            # 2. 쿼리 실행
            try:
                results = execute_query(sql)
                df = pd.DataFrame(results) if results else pd.DataFrame()

                # [필터링] 신뢰도 점수 50점 초과만 표시
                if 'confidence_score' in df.columns:
                    df['confidence_score'] = pd.to_numeric(df['confidence_score'], errors='coerce').fillna(0)
                    df = df[df['confidence_score'] > 50]
                
                # [보충] 결과가 10개 미만이면 부족한 만큼 랭킹순으로 채움 (confidence_score > 50)
                if len(df) < 10:
                    needed = 10 - len(df)
                    st.warning(f"검색 결과가 {len(df)}건이라, '검증된 인플루언서'를 추가하여 보여드립니다.")
                    
                    # 이미 있는 influencer_id 제외하고 가져오기
                    existing_ids = df['influencer_id'].tolist() if 'influencer_id' in df.columns else []
                    
                    # 넉넉하게 상위 20명 조회
                    fallback_sql = "SELECT * FROM influencers WHERE confidence_score > 50 ORDER BY confidence_score DESC LIMIT 20"
                    fallback_results = execute_query(fallback_sql)
                    
                    if fallback_results:
                        fallback_df = pd.DataFrame(fallback_results)
                        if 'influencer_id' in fallback_df.columns:
                            # 이미 목록에 있는 ID 제외
                            fallback_df = fallback_df[~fallback_df['influencer_id'].isin(existing_ids)]
                        
                        # 부족한 만큼 추가
                        df = pd.concat([df, fallback_df.head(needed)], ignore_index=True)

                if not df.empty:
                    # 중복 제거 (influencer_id 기준)
                    if 'influencer_id' in df.columns:
                        df = df.drop_duplicates(subset=['influencer_id'])
                    elif 'name' in df.columns: # fallback
                         df = df.drop_duplicates(subset=['name'])

                    # confidence_score 기준 정렬
                    if 'confidence_score' in df.columns:
                        df = df.sort_values(by='confidence_score', ascending=False)
                    
                    st.success(f"총 {len(df)}명의 인플루언서를 찾았습니다!")
                    
                    # 결과 표시
                    for idx, row in df.iterrows():
                        with st.container():
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                st.image("https://ui-avatars.com/api/?name=" + str(row.get('name', 'User')), width=80)
                            with col2:
                                name_text = f"{row.get('name', 'Unknown')}"
                                if row.get('confidence_score'):
                                    name_text += f" (점수: {row['confidence_score']})"
                                st.subheader(name_text)

                                
                                # 데이터 표시 최적화
                                info_str = []
                                if row.get('title'): info_str.append(f"📺 **{row['title']}**")
                                if row.get('subscriber_count'): info_str.append(f"구독자: {row['subscriber_count']:,}명")
                                if row.get('channel_title'): info_str.append(f"채널: {row['channel_title']}")
                                
                                st.markdown(" | ".join(info_str))
                                
                                # 추가 세부 정보
                                with st.expander("상세 정보"):
                                    st.json(row.to_dict())
                            st.divider()
                else:
                    st.warning("검색 결과가 없습니다.")
                    
            except Exception as e:
                st.error(f"쿼리 실행 중 오류가 발생했습니다: {e}")
        else:
            st.error("SQL 생성에 실패했습니다. API 키를 확인해주세요.")

# 하단 푸터
st.markdown("---")
st.markdown("© 2024 HairMatch AI | Powered by TiDB & Gemini")
