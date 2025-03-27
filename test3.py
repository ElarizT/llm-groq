import streamlit as st
from groq import Groq
import os
import tempfile
import pandas as pd
from io import StringIO
# Add PyPDF2 for PDF text extraction
import PyPDF2
import io
# Replace Tavily with DuckDuckGo search
from duckduckgo_search import DDGS
import json
from datetime import datetime
# Text-to-speech library (no PyAudio dependency)
from gtts import gTTS
import base64

# Set up Streamlit app
st.set_page_config(page_title="Elariz's Chatbot", layout="wide")
st.title("🤖 Elariz's Chatbot")

# Initialize API clients
groq_api_key = API_KEY

client = Groq(api_key=groq_api_key)

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "file_content" not in st.session_state:
    st.session_state.file_content = None
if "file_name" not in st.session_state:
    st.session_state.file_name = None
if "use_web_search" not in st.session_state:
    st.session_state.use_web_search = False
if "voice_mode" not in st.session_state:
    st.session_state.voice_mode = False

# Function to convert text to speech and play it
def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='en')
        # Save the audio file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except Exception as e:
        st.error(f"Text-to-speech error: {str(e)}")
        return None

# Function to autoplay audio in Streamlit
def autoplay_audio(file_path):
    if file_path is None or not os.path.exists(file_path):
        st.warning("Audio file not available")
        return
        
    try:
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        
        audio_base64 = base64.b64encode(audio_bytes).decode()
        audio_html = f"""
            <audio autoplay controls>
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
        
        # Clean up file after use
        try:
            os.unlink(file_path)
        except:
            pass
    except Exception as e:
        st.error(f"Error playing audio: {str(e)}")

# Function to search the web using DuckDuckGo
def search_web(query, max_results=3):
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        
        # Format the search results nicely
        formatted_results = f"Web search results for: '{query}'\n\n"
        
        if not results:
            return f"No results found for query: '{query}'"
        
        formatted_results += "Sources:\n"
        for i, result in enumerate(results, 1):
            formatted_results += f"{i}. {result.get('title', 'No title')}\n"
            formatted_results += f"   URL: {result.get('href', 'No URL')}\n"
            formatted_results += f"   Content: {result.get('body', 'No content')}\n\n"
                
        return formatted_results
    
    except Exception as e:
        return f"Error performing web search: {str(e)}"

# Create sidebar for file uploads and settings
with st.sidebar:
    st.header("Settings")
    
    # Web search toggle
    st.session_state.use_web_search = st.toggle("Enable Web Search", st.session_state.use_web_search)
    
    # Voice output mode toggle (Text-to-Speech for AI responses)
    st.session_state.voice_mode = st.toggle("Enable Voice Output", st.session_state.voice_mode)
    if st.session_state.voice_mode:
        st.info("🔊 AI responses will be spoken aloud")
    
    st.header("Upload File")
    uploaded_file = st.file_uploader("Choose a file", type=["txt", "csv", "pdf", "py", "js", "html", "css", "json", "md"])
    
    # Rest of the sidebar code remains unchanged
    if uploaded_file is not None:
        # Get file details
        file_details = {"Filename": uploaded_file.name, "FileType": uploaded_file.type, "FileSize": f"{uploaded_file.size / 1024:.2f} KB"}
        st.write("File Details:")
        st.json(file_details)
        
        try:
            # Read and store file content based on type
            if uploaded_file.name.endswith('.csv'):
                # For CSV files, use pandas to read and convert to string
                df = pd.read_csv(uploaded_file)
                string_data = df.to_string()
                st.session_state.file_content = string_data
            elif uploaded_file.name.endswith('.pdf'):
                # Extract text from PDF using PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
                text = ""
                for page_num in range(len(pdf_reader.pages)):
                    text += pdf_reader.pages[page_num].extract_text() + "\n\n"
                
                if text.strip():
                    st.session_state.file_content = text
                else:
                    st.warning("No extractable text found in the PDF. It might be scanned or image-based.")
                    st.session_state.file_content = "PDF file uploaded, but no extractable text was found."
            else:
                # For text-based files - try different encodings if utf-8 fails
                try:
                    content = uploaded_file.getvalue().decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        content = uploaded_file.getvalue().decode("latin-1")
                    except:
                        content = str(uploaded_file.getvalue())
                
                st.session_state.file_content = content
            
            st.session_state.file_name = uploaded_file.name
            st.success(f"File '{uploaded_file.name}' successfully processed!")
            
            # Show a preview of the file content
            with st.expander("File Preview"):
                if len(st.session_state.file_content) > 1000:
                    st.text(st.session_state.file_content[:1000] + "...")
                else:
                    st.text(st.session_state.file_content)
        
        except Exception as e:
            st.error(f"Error processing file: {e}")
    
    # Option to clear uploaded file
    if st.session_state.file_content is not None:
        if st.button("Clear Uploaded File"):
            st.session_state.file_content = None
            st.session_state.file_name = None
            st.success("File cleared!")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Text input for user messages (no voice input since it won't work in cloud)
user_input = st.chat_input("Ask me anything...")

if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Prepare messages for the API call
    messages_for_api = st.session_state.messages.copy()
    
    # Search the web if enabled
    web_search_results = None
    if st.session_state.use_web_search:
        with st.spinner("Searching the web..."):
            web_search_results = search_web(user_input)
            if web_search_results:
                # Display search results to user
                with st.expander("Web Search Results"):
                    st.markdown(web_search_results)
    
    # System message preparation
    system_instructions = []
    
    # If there's an uploaded file, include its content in the system message
    if st.session_state.file_content:
        file_info = f"The user has uploaded a file named '{st.session_state.file_name}'. Here's the content of the file:\n\n{st.session_state.file_content}\n\nPlease refer to this content when answering questions about the file."
        system_instructions.append(file_info)
    
    # If web search results are available, include them
    if web_search_results:
        current_date = datetime.now().strftime("%Y-%m-%d")
        search_info = f"Current date: {current_date}. The following information was retrieved from the web in response to the user's query:\n\n{web_search_results}\n\nPlease use this information to provide an up-to-date and accurate response."
        system_instructions.append(search_info)
    
    # Add system message if we have any instructions
    if system_instructions:
        system_message = {
            "role": "system",
            "content": "\n\n".join(system_instructions)
        }
        messages_for_api.insert(0, system_message)
    
    # Show a spinner while waiting for the API response
    with st.spinner("Thinking..."):
        # API call to Groq
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages_for_api,
                temperature=1,
                max_completion_tokens=1024,
                top_p=1,
                stream=True,
                stop=None,
            )
            
            # Process and display the streaming response
            bot_reply = ""
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    bot_reply += content
                    message_placeholder.markdown(bot_reply + "▌")
                message_placeholder.markdown(bot_reply)
            
            # Store bot response
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            
            # If voice mode is enabled, convert response to speech
            if st.session_state.voice_mode:
                with st.spinner("Generating speech..."):
                    # Limit the text to avoid very long audio
                    speech_text = bot_reply[:500] + "..." if len(bot_reply) > 500 else bot_reply
                    audio_file = text_to_speech(speech_text)
                    if audio_file:
                        autoplay_audio(audio_file)
            
        except Exception as e:
            st.error(f"Error communicating with Groq API: {e}")
            st.session_state.messages.append({"role": "assistant", "content": f"I'm sorry, I encountered an error: {str(e)}"})
