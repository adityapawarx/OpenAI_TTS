import requests
import streamlit as st
import openai
import tempfile
import base64
from audio_recorder_streamlit import audio_recorder
import asyncio
import edge_tts
import re
from PIL import Image

# Constants
COST_PER_1K_TOKENS = 0.002  # GPT-3.5-turbo cost rate
WEATHER_API_KEY = st.secrets["WEATHER_API_KEY"]  # Include your Weather API Key in Streamlit secrets

# Set OpenAI API Key
openai.api_key = st.secrets["OPEN_API_KEY"]

# Function to encode an image as base64
def set_background_image(image_path):
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode()
    page_bg_img = f"""
    <style>
    .stApp {{
        background-image: url("data:image/png;base64,{base64_image}");
        background-size: cover;
    }}
    </style>
    """
    st.markdown(page_bg_img, unsafe_allow_html=True)

# Placeholder function to fetch images
def fetch_relevant_image(query):
    # Placeholder code; replace with actual image fetching logic/API call
    return Image.open("valorant.png")  # Use a valid image path or fetching logic

# Initialize session state variables
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = [{"role": "system", "content": "You are a helpful assistant."}]
if "interrupt_flag" not in st.session_state:
    st.session_state.interrupt_flag = False

def main():
    # Title and layout setup
    st.title("Voice Assistant")
    
    # Call the function to set the background image
    set_background_image('cortana.png')  # Replace with your image path

    # Setup layout with columns: 2/5 for images, 3/5 for the assistant
    col1, col2 = st.columns([2, 3])
    
    with col1:  # Left column for images
        st.subheader("Relevant Image")
        image = fetch_relevant_image("first president of america")  # Placeholder query
        if image:
            st.image(image, use_column_width=True)

    response_container = col2.container()  # Right column for the voice assistant

    def autoplay_audio(audio_file_path):
        if st.session_state.interrupt_flag:
            return
        audio_placeholder = response_container.empty()
        with open(audio_file_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
            audio_html = f"""
            <audio autoplay>
                <source src="data:audio/mp3;base64,{base64.b64encode(audio_bytes).decode()}" type="audio/mp3">
            </audio>
            """
            audio_placeholder.markdown(audio_html, unsafe_allow_html=True)

    async def handle_conversation():
        audio_bytes = audio_recorder(key="audio_recorder_main")
        if audio_bytes:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
                temp_audio_file.write(audio_bytes)
                temp_audio_file_path = temp_audio_file.name

            with open(temp_audio_file_path, "rb") as audio_file:
                transcript = openai.Audio.transcribe("whisper-1", audio_file)

            user_input = transcript["text"]

            if "weather" in user_input.lower() or "storm" in user_input.lower():
                city_name = extract_city_name(user_input)

                if city_name:
                    weather_info = get_weather_data(city_name)
                    if weather_info:
                        response = interpret_weather_data(user_input, weather_info)
                        assistant_reply = response
                    else:
                        assistant_reply = "Sorry, I couldn't fetch the weather for that location."
                else:
                    assistant_reply = "Could you please specify the city name for the weather details?"
            else:
                assistant_reply, prompt_tokens, completion_tokens = get_ai_response(user_input)

            await process_and_play_ai_response(assistant_reply)

    def get_ai_response(user_input):
        st.session_state.conversation_history.append({"role": "user", "content": user_input})
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.conversation_history
        )
        assistant_reply = response["choices"][0]["message"]["content"]
        st.session_state.conversation_history.append({"role": "assistant", "content": assistant_reply})

        return assistant_reply, response["usage"]["prompt_tokens"], response["usage"]["completion_tokens"]

    async def process_and_play_ai_response(assistant_reply):
        communicate = edge_tts.Communicate(assistant_reply, "en-US-AriaNeural", rate="+50%")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            await communicate.save(temp_audio_file.name)
            temp_tts_audio_file_path = temp_audio_file.name

        st.write(f"**Assistant (in English):** {assistant_reply}")
        autoplay_audio(temp_tts_audio_file_path)

    def extract_city_name(user_input):
        match = re.search(r'weather in (\w+)', user_input)
        if match:
            return match.group(1)
        return None

    def get_weather_data(location):
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={WEATHER_API_KEY}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            temp = data['main']['temp'] - 273.15
            feels_like = data['main']['feels_like'] - 273.15
            weather_desc = data['weather'][0]['description']
            weather_conditions = data['weather'][0]['main']
            humidity = data['main']['humidity']
            wind_speed = data['wind']['speed']

            return {
                "location": location,
                "temperature": round(temp, 2),
                "feels_like": round(feels_like, 2),
                "description": weather_desc.capitalize(),
                "conditions": weather_conditions.lower(),
                "humidity": humidity,
                "wind_speed": wind_speed
            }
        else:
            return None

    def interpret_weather_data(user_input, weather_info):
        if "storm" in user_input.lower() and "storm" in weather_info["conditions"]:
            return f"Yes, there is a storm today in {weather_info['location']} with {weather_info['description']}."
        elif "temperature" in user_input.lower():
            return f"The current temperature in {weather_info['location']} is {weather_info['temperature']}°C."
        elif "wind" in user_input.lower():
            return f"The wind speed in {weather_info['location']} is {weather_info['wind_speed']} m/s."
        elif "humidity" in user_input.lower():
            return f"The humidity in {weather_info['location']} is {weather_info['humidity']}%."
        else:
            return f"Current weather in {weather_info['location']}: {weather_info['description']}, {weather_info['temperature']}°C."

    asyncio.run(handle_conversation())

if __name__ == "__main__":
    main()