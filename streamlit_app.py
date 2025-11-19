import streamlit as st
import google.generativeai as genai
import random
import time

# --- 1. Streamlit 설정 및 API 키 초기화 ---

# 페이지 설정
st.set_page_config(
    page_title="이순신 vs 도요토미 히데요시 대화",
    layout="wide"
)

st.title("🚢 이순신 vs 🗡️ 도요토미 히데요시 대화")
st.markdown("임진왜란의 두 영웅(장군 및 정복자)과 대화를 나눠보세요. 도요토미 히데요시가 무작위로 난입하여 대화에 끼어들 수 있습니다.")

# API 키 및 모델 초기화 (st.secrets 사용)
try:
    # Streamlit Secrets에서 API 키를 가져옵니다.
    # .streamlit/secrets.toml 파일에 GEMINI_API_KEY = "YOUR_API_KEY" 형태로 저장해야 합니다.
    GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("API 키를 찾을 수 없습니다. `.streamlit/secrets.toml` 파일에 `GEMINI_API_KEY = 'YOUR_API_KEY'` 형태로 키를 설정해주세요.")
    st.stop()

# --- 2. 페르소나 및 설정 ---

# 이순신 장군 페르소나 (시스템 프롬프트)
LEE_SUN_SHIN_PERSONA = """
당신은 조선 시대의 명장 이순신 장군입니다. 임진왜란 때 활약한 해군 제독으로, 국가와 백성을 지키는 데 헌신했습니다. 조선시대의 격식 있는 말투로 대화하며, 다음 특성을 가집니다:
1. 애국심: 조선과 백성에 대한 깊은 사랑과 충성심을 표현합니다.
2. 용기: 어려운 상황에서도 굴하지 않는 용기를 보입니다.
3. 전략가: 뛰어난 전술과 전략적 사고를 바탕으로 대화합니다.
4. 정의감: 올바른 도리를 중요시하고 정의를 추구합니다.
5. 존엄성: 고귀한 품격과 위엄을 유지합니다.
국가의 안위와 백성의 평화를 최우선으로 여기며, 외적의 침략에 대해서는 단호한 태도를 보이되 과도한 적대감은 표현하지 않습니다.
"""

# 도요토미 히데요시 페르소나 (시스템 프롬프트)
TOYOTOMI_HIDEYOSHI_PERSONA = """
당신은 일본의 전국시대를 통일한 도요토미 히데요시입니다. 임진왜란을 일으킨 장본인이자 뛰어난 전략가로, "~데쓰", "~데쓰까", "고노야로" 등 한국인들에게 익숙한 일본어식 표현을 섞어 한국어로 대화하며 다음 특성을 가집니다:
1. 야망: 대륙 정복에 대한 강한 열망을 가지고 있습니다.
2. 전략가: 정치와 전쟁에서 뛰어난 전략적 사고를 보여줍니다.
3. 카리스마: 부하들을 이끄는 강한 리더십을 가지고 있습니다.
4. 교활함: 상황에 따라 유연하게 대처하는 능력이 있습니다.
5. 자신감: 자신의 능력과 판단에 대한 강한 확신을 가지고 있습니다.
일본의 이익과 확장을 최우선으로 여기며, 타국과의 관계에서는 실리적인 태도를 보입니다. 과도한 폭력성이나 적대감은 표현하지 않습니다.
대화에 갑자기 끼어들어 자신의 의견을 도발적인 발언을 합니다. 상대방을 비웃거나 얕잡아보는 말투를 사용합니다.
"""

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"}
]

# --- 3. 모델 초기화 및 캐싱 ---

@st.cache_resource
def initialize_models(api_key):
    """모델을 초기화하고 재사용하여 Streamlit 성능을 향상시킵니다."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash", # 더 강력하고 안정적인 모델 사용
            safety_settings=SAFETY_SETTINGS
        )
        return model
    except Exception as e:
        st.error(f"모델 초기화 오류: {e}")
        st.stop()

# 모델 로드
MODEL = initialize_models(GOOGLE_API_KEY)

# --- 4. Streamlit 상태 관리 (session_state) ---

# 채팅 기록 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "name": "이순신", "content": "나는 조선의 수군 통제사 이순신이오. 그대와 국사에 대해 대화를 나눌 준비가 되었소."}
    ]

# 채팅 세션 초기화 (캐릭터별 기록 관리)
if "chat_lee" not in st.session_state:
    st.session_state.chat_lee = MODEL.start_chat(history=[])
if "chat_hideyoshi" not in st.session_state:
    st.session_state.chat_hideyoshi = MODEL.start_chat(history=[])

# --- 5. 응답 생성 함수 ---

def generate_response_with_retry(chat_session, persona, character_name, context_prompt, max_retries=3):
    """
    주어진 페르소나와 컨텍스트를 바탕으로 응답을 생성하고 API 오류 시 재시도합니다.
    """
    
    # 프롬프트 구성
    full_prompt = f"""
    {persona}
    
    이것은 현재 대화 맥락과 사용자 입력의 전체 정보입니다:
    {context_prompt}
    
    {character_name}으로서 가장 적절한 방식으로 이 상황에 응답해주세요.
    """

    for attempt in range(max_retries):
        try:
            # send_message 대신 generate_content를 사용하여 페르소나를 더 잘 제어합니다.
            response = MODEL.generate_content(
                contents=[
                    {"role": "user", "parts": [{"text": full_prompt}]}
                ],
                config=genai.types.GenerateContentConfig(
                    system_instruction=persona
                )
            )

            # 응답 텍스트를 정리하고 반환
            if response.text:
                return response.text.strip()
            return None

        except genai.errors.ResourceExhaustedError:
            wait_time = (attempt + 1) * 5
            st.warning(f"API 할당량 초과 에러 (429). {wait_time}초 후 재시도합니다... ({attempt + 1}/{max_retries})")
            time.sleep(wait_time)
        except Exception as e:
            st.error(f"'{character_name}' 응답 생성 오류 (시도 {attempt + 1}): {str(e)}")
            time.sleep(2) # 일반 오류 시 짧게 대기
            
    return None

# --- 6. 채팅 UI 및 로직 ---

# 기존 채팅 기록 표시
for message in st.session_state.chat_history:
    with st.chat_message(message["name"], avatar="user" if message["role"] == "user" else "assistant"):
        st.markdown(message["content"])

# 사용자 입력 처리
if user_prompt := st.chat_input("이순신 장군에게 말을 걸어보십시오."):
    
    # 1. 사용자 입력 저장
    st.session_state.chat_history.append({"role": "user", "name": "나", "content": user_prompt})
    
    # 새로운 사용자 입력 표시
    with st.chat_message("나", avatar="user"):
        st.markdown(user_prompt)

    # 2. 이순신 장군 응답 생성 및 표시
    with st.spinner("🚢 이순신 장군이 고심하고 있습니다..."):
        lee_context_prompt = f"사용자의 대화: {user_prompt}"
        lee_response = generate_response_with_retry(
            st.session_state.chat_lee, LEE_SUN_SHIN_PERSONA, "이순신", lee_context_prompt
        )

    if lee_response:
        with st.chat_message("이순신", avatar="assistant"):
            st.markdown(lee_response)
        st.session_state.chat_history.append({"role": "assistant", "name": "이순신", "content": lee_response})

        # 3. 도요토미 히데요시 난입 판정 (40% 확률)
        if random.random() < 0.4:
            st.subheader("⚔️ 도요토미 히데요시가 난입합니다!")
            
            # 4. 히데요시 응답 생성 및 표시
            with st.spinner("🗡️ 도요토미 히데요시가 도발적인 발언을 준비합니다..."):
                hideyoshi_context_prompt = f"현재 대화: (사용자: {user_prompt}) (이순신: {lee_response})\n\n이순신의 발언에 대해 도발적이고 교활하게 대화에 끼어들어 응답하십시오."
                hideyoshi_response = generate_response_with_retry(
                    st.session_state.chat_hideyoshi, TOYOTOMI_HIDEYOSHI_PERSONA, "히데요시", hideyoshi_context_prompt
                )

            if hideyoshi_response:
                with st.chat_message("히데요시", avatar="assistant"):
                    st.markdown(hideyoshi_response)
                st.session_state.chat_history.append({"role": "assistant", "name": "히데요시", "content": hideyoshi_response})
                
                # 5. 이순신 장군 대응 응답 생성 및 표시
                st.subheader("🛡️ 이순신 장군이 이에 대응합니다.")
                with st.spinner("🚢 이순신 장군이 단호하게 응답합니다..."):
                    lee_counter_context_prompt = f"도요토미 히데요시의 도발: {hideyoshi_response}\n\n히데요시의 발언에 대해 조선의 명장으로서 단호하고 위엄 있게 대응하십시오."
                    lee_counter_response = generate_response_with_retry(
                        st.session_state.chat_lee, LEE_SUN_SHIN_PERSONA, "이순신", lee_counter_context_prompt
                    )

                if lee_counter_response:
                    with st.chat_message("이순신", avatar="assistant"):
                        st.markdown(lee_counter_response)
                    st.session_state.chat_history.append({"role": "assistant", "name": "이순신", "content": lee_counter_response})
    
    # 전체 페이지 다시 실행하여 새로운 메시지 표시
    st.rerun()

# 리셋 버튼
if st.button("대화 리셋", help="새로운 대화를 시작합니다."):
    st.session_state.chat_history = [
        {"role": "assistant", "name": "이순신", "content": "나는 조선의 수군 통제사 이순신이오. 그대와 국사에 대해 대화를 나눌 준비가 되었소."}
    ]
    # 채팅 세션도 새로 시작
    st.session_state.chat_lee = MODEL.start_chat(history=[])
    st.session_state.chat_hideyoshi = MODEL.start_chat(history=[])
    st.rerun()
