import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- [1. 페이지 설정 및 제목] ---
st.set_page_config(page_title="서울시 문화공간 분석", layout="wide")
st.title("🏛️ 서울시 문화공간 분포 및 접근성 대시보드")
st.markdown("서울시의 다양한 문화공간 데이터를 SQL로 분석하고 시각화합니다.")

# --- [2. 데이터 로드 및 전처리 함수] ---
@st.cache_data
def load_data():
    file_path = "서울시 문화공간 정보.csv"
    
    # 파일 존재 여부 확인
    if not os.path.exists(file_path):
        st.error(f"❌ '{file_path}' 파일을 찾을 수 없습니다. 파일명을 확인해주세요.")
        return None

    # CSV 읽기 (UTF-8-SIG는 한글 깨짐 방지에 좋습니다)
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
    except:
        df = pd.read_csv(file_path, encoding='cp949') # 실패 시 구버전 엑셀 방식 시도

    # 컬럼명 매핑 (영문 -> 한글)
    rename_map = {
        'num': '번호', 'fac_name': '문화시설명', 'subjcode': '주제분류',
        'gngu': '자치구', 'addr': '주소', 'x_coord': '위도', 'y_coord': '경도',
        'entrfree': '무료구분', 'entr_fee': '관람료', 'openhour': '관람시간',
        'closeday': '휴관일', 'seat_cnt': '객석수', 'homepage': '홈페이지', 'phne': '전화번호'
    }
    df.rename(columns=rename_map, inplace=True)

    # 필수 컬럼 존재 확인 및 안내
    required_cols = ['문화시설명', '자치구', '주제분류', '위도', '경도']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.warning(f"⚠️ 일부 컬럼이 부족합니다: {missing_cols}")
        st.write("현재 파일 컬럼명:", df.columns.tolist())

    # 데이터 정제
    # 1. 위도/경도 숫자형 변환 (오류 데이터는 NaN 처리)
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    
    # 2. 객석수 숫자만 추출
    df['객석수'] = df['객석수'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    
    # 3. 결측치 처리
    df = df.fillna("정보없음").replace("", "정보없음")
    
    return df

# 데이터 불러오기 실행
df_raw = load_data()

if df_raw is not None:
    # --- [3. SQLite 메모리 DB에 저장] ---
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    df_raw.to_sql('culture_space', conn, index=False, if_exists='replace')

    # --- [4. 사이드바 필터] ---
    st.sidebar.header("🔍 데이터 필터링")
    
    # 자치구 선택
    all_districts = ["전체"] + sorted(df_raw['자치구'].unique().tolist())
    selected_district = st.sidebar.selectbox("자치구 선택", all_districts)
    
    # 주제분류 선택
    all_types = ["전체"] + sorted(df_raw['주제분류'].unique().tolist())
    selected_type = st.sidebar.selectbox("문화공간 유형 선택", all_types)

    # SQL 쿼리로 필터링된 데이터 가져오기
    query = "SELECT * FROM culture_space WHERE 1=1"
    if selected_district != "전체":
        query += f" AND 자치구 = '{selected_district}'"
    if selected_type != "전체":
        query += f" AND 주제분류 = '{selected_type}'"
    
    df_filtered = pd.read_sql(query, conn)

    # 상단 요약 지표
    col1, col2, col3 = st.columns(3)
    col1.metric("총 시설 수", f"{len(df_filtered)} 개")
    col2.metric("선택 자치구", selected_district)
    col3.metric("선택 유형", selected_type)

    # --- [5. 시각화 섹션] ---
    st.divider()
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader("1. 자치구별 문화공간 수 (TOP 10)")
        sql_q1 = "SELECT 자치구, COUNT(*) as 시설수 FROM culture_space GROUP BY 자치구 ORDER BY 시설수 DESC LIMIT 10"
        df_q1 = pd.read_sql(sql_q1, conn)
        fig1 = px.bar(df_q1, x='자치구', y='시설수', color='시설수', color_continuous_scale='Blues')
        st.plotly_chart(fig1, use_container_width=True)
        st.info(f"**SQL:** `{sql_q1}`")
        st.write("**인사이트:** 서울 내 문화 시설은 특정 자치구에 집중되어 있는 경향이 있으며, TOP 10 구가 전체 인프라의 상당수를 차지합니다.")

    with row1_col2:
        st.subheader("2. 문화공간 유형별 분포")
        sql_q2 = "SELECT 주제분류, COUNT(*) as 개수 FROM culture_space GROUP BY 주제분류 ORDER BY 개수 DESC"
        df_q2 = pd.read_sql(sql_q2, conn)
        fig2 = px.pie(df_q2, values='개수', names='주제분류', hole=0.4)
        st.plotly_chart(fig2, use_container_width=True)
        st.info(f"**SQL:** `{sql_q2}`")
        st.write("**인사이트:** 도서관, 박물관, 미술관 등 특정 유형의 편중을 확인할 수 있어, 지역별로 부족한 문화 인프라 종류를 파악하기 좋습니다.")

    st.subheader("3. 무료/유료 문화공간 비율")
    sql_q3 = "SELECT 무료구분, COUNT(*) as 개수 FROM culture_space GROUP BY 무료구분"
    df_q3 = pd.read_sql(sql_q3, conn)
    fig3 = px.pie(df_q3, values='개수', names='무료구분', color='무료구분', 
                  color_discrete_map={'무료':'#636EFA', '유료':'#EF553B', '정보없음':'#7f7f7f'})
    st.plotly_chart(fig3)
    st.info(f"**SQL:** `{sql_q3}`")
    st.write("**인사이트:** 무료 시설의 비중이 높을수록 시민들의 문화 접근성이 우수하다고 판단할 수 있습니다.")

    # --- [6. 지도 및 목록] ---
    st.divider()
    st.subheader("📍 지도 상 위치")
    # 위도 경도가 있는 데이터만 추출
    map_data = df_filtered.dropna(subset=['위도', '경도'])
    if not map_data.empty:
        fig_map = px.scatter_mapbox(map_data, lat="위도", lon="경도", 
                                    hover_name="문화시설명", hover_data=["자치구", "주제분류"],
                                    zoom=10, height=500)
        fig_map.update_layout(mapbox_style="open-street-map")
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.warning("위도/경도 정보가 없어 지도를 표시할 수 없습니다.")

    st.subheader("📋 필터링된 문화시설 목록")
    display_cols = ['문화시설명', '자치구', '주제분류', '주소', '무료구분', '관람료', '관람시간', '휴관일', '홈페이지']
    st.dataframe(df_filtered[display_cols], use_container_width=True)

else:
    st.info("💡 '서울시 문화공간 정보.csv' 파일을 이 스크립트와 같은 폴더에 놓아주세요.")