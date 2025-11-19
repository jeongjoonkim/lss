import streamlit as st
import google.generativeai as genai
import random
import time

# Streamlit 앱 설정
st.set_page_config(page_title="이순신 & 도요토미 대화", layout="centered")
st.title("이순신 & 도요토미 대화 시뮬레이션")
st.write("이순신 장군과 대화해보세요. 가끔 도요토미 히데요시가 끼어들 수 있습니다.")

# API-KEY 설정 (Streamlit secrets 사용 권장)
GOOGLE_API_KEY = "AIzaSyCOGl26FVGWSQMQsC2572MhqPSkCyRsY8E" # 실제 배포 시

# Colab 환경에서 테스트를 위해 notebook의 GOOGLE_API_KEY를 사용
try:
    from google.colab import userdata
    GOOGLE_API_KEY = userdata.get('GOOGLE_API_KEY')
except ImportError:
    # Colab이 아닌 환경에서는 st.secrets 또는 환경 변수 등 사용
    if 'GOOGLE_API_KEY' in st.secrets:
        GOOGLE_API_KEY = st.secrets['GOOGLE_API_KEY']
    else:
        st.error("GOOGLE_API_KEY가 설정되지 않았습니다. st.secrets에 등록하거나 코드에 직접 입력해주세요.")
        st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# 페르소나 정의 (기존 코드와 동일)
lee_sun_shin_persona = """
당신은 조선 시대의 명장 이순신 장군입니다. 임진왜란 때 활약한 해군 제독으로, 국가와 백성을 지키는 데 헌신했습니다. 조선시대의 격식 있는 말투로 대화하며, 다음 특성을 가집니다:

1. 애국심: 조선과 백성에 대한 깊은 사랑과 충성심을 표현합니다.
2. 용기: 어려운 상황에서도 굴하지 않는 용기를 보입니다.
3. 전략가: 뛰어난 전술과 전략적 사고를 바탕으로 대화합니다.
4. 정의감: 올바른 도리를 중요시하고 정의를 추구합니다.
5. 존엄성: 고귀한 품격과 위엄을 유지합니다.

국가의 안위와 백성의 평화를 최우선으로 여기며, 외적의 침략에 대해서는 단호한 태도를 보이되 과도한 적대감은 표현하지 않습니다.
"""

toyotomi_hideyoshi_persona = """
당신은 일본의 전국시대를 통일한 도요토미 히데요시입니다. 임진왜란을 일으킨 장본인이자 뛰어난 전략가로, ~데쓰, ~데쓰까, 빠가야로, 고노야고, 오스와리 등 한국인들에게 익숙한 일본어 단어가 있는 한국어로 대화하며 다음 특성을 가집니다:

1. 야망: 대륙 정복에 대한 강한 열망을 가지고 있습니다.
2. 전략가: 정치와 전쟁에서 뛰어난 전략적 사고를 보여줍니다.
3. 카리스마: 부하들을 이끄는 강한 리더십을 가지고 있습니다.
4. 교활함: 상황에 따라 유연하게 대처하는 능력이 있습니다.
5. 자신감: 자신의 능력과 판단에 대한 강한 확신을 가지고 있습니다.

일본의 이익과 확장을 최우선으로 여기며, 타국과의 관계에서는 실리적인 태도를 보입니다. 과도한 폭력성이나 적대감은 표현하지 않습니다.
대화에 갑자기 끼어들어 자신의 의견을 도발적인 발언을 합니다.
"""

# 안전 설정 (기존 코드와 동일)
safety_settings = [
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_ONLY_HIGH"
    }
]

# 모델 정의 및 챗봇 초기화 (st.session_state로 관리)
if 'chat_bot' not in st.session_state:
    st.session_state.model = genai.GenerativeModel("gemini-2.5-flash-lite", safety_settings=safety_settings)
    st.session_state.chat_bot = st.session_state.model.start_chat(history=[])

# 대화 기록 초기화
if 'messages' not in st.session_state:
    st.session_state.messages = []

def generate_response(persona, character_name, user_input_for_model):
    """
    주어진 페르소나와 입력으로 응답을 생성합니다.
    이 함수는 Streamlit 앱 내에서 API 호출을 관리합니다.
    """
    try:
        prompt = f"""
{persona}

대화 맥락:
{st.session_state.messages[-5:] if len(st.session_state.messages) > 5 else st.session_state.messages}
사용자: {user_input_for_model}

{character_name}으로서 응답해주세요:
"""
        response = st.session_state.chat_bot.send_message(prompt, stream=False)
        if response.text:
            return response.text
        return ""
    except Exception as e:
        st.error(f"{character_name} 응답 생성 중 오류 발생: {e}")
        return ""

def generate_response_with_retry(persona, character_name, user_input_for_model, max_retries=3):
    for attempt in range(max_retries):
        try:
            response_text = generate_response(persona, character_name, user_input_for_model)
            if response_text:
                return response_text
        except Exception as e:
            if "429" in str(e):  # API 할당량 초과 에러
                wait_time = (attempt + 1) * 5
                # 수정: f-string 내의 변수 이름 'wait_name'을 'wait_time'으로 변경
                st.warning(f"{wait_time}초 후 재시도합니다... ({attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                st.error(f"{character_name} 응답 재시도 중 오류: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
    return ""

# 이전 대화 기록 표시
for role, message in st.session_state.messages:
    with st.chat_message(role):
        st.write(message)

# 사용자 입력 처리
user_input = st.chat_input("장군님께 여쭙고 싶은 말이 있으십니까?")

if user_input:
    # 사용자 메시지 기록 및 표시
    st.session_state.messages.append(("user", user_input))
    with st.chat_message("user"):
        st.write(user_input)

    # 이순신 장군 응답 생성 및 표시
    with st.chat_message("이순신"):
        with st.spinner("이순신 장군께서 생각 중이십니다..."):
            lee_response = generate_response_with_retry(lee_sun_shin_persona, "이순신", user_input)
            if lee_response:
                st.write(lee_response)
                st.session_state.messages.append(("이순신", lee_response))
            else:
                st.error("이순신 장군의 응답을 생성하는 데 실패했습니다.")

    # 도요토미 히데요시 난입 확률
    if random.random() < 0.49:
        with st.chat_message("히데요시"):
            st.write("도요토미 히데요시가 끼어듭니다:")
            with st.spinner("히데요시가 발언을 준비 중입니다..."):
                hideyoshi_input = f"이순신의 말: {lee_response}\n사용자의 말: {user_input}"
                hideyoshi_response = generate_response_with_retry(
                    toyotomi_hideyoshi_persona,
                    "히데요시",
                    hideyoshi_input
                )
                if hideyoshi_response:
                    st.write(hideyoshi_response)
                    st.session_state.messages.append(("히데요시", hideyoshi_response))
                else:
                    st.error("히데요시의 응답을 생성하는 데 실패했습니다.")

        # 히데요시 난입 후 이순신 장군 대응
        if hideyoshi_response:
            with st.chat_message("이순신"):
                st.write("이순신 장군께서 대응하십니다:")
                with st.spinner("이순신 장군께서 반박 중이십니다..."):
                    lee_counter_response = generate_response_with_retry(
                        lee_sun_shin_persona,
                        "이순신",
                        f"히데요시가 말하길: {hideyoshi_response}"
                    )
                    if lee_counter_response:
                        st.write(lee_counter_response)
                        st.session_state.messages.append(("이순신", lee_counter_response))
                    else:
                        st.error("이순신 장군의 대응 응답을 생성하는 데 실패했습니다.")

    # 대화 종료 기능 (Streamlit에서는 앱을 닫거나 새로고침)
    # '대화 종료' 입력 시 특별한 처리 필요 시 여기에 추가
    if user_input.lower() == "대화 종료":
        st.info("대화가 종료되었습니다. 앱을 닫거나 새로고침 하십시오.")
        st.stop()
