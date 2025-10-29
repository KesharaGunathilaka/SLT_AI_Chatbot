import google.generativeai as genai

# Configure Gemini
genai.configure(api_key="AIzaSyDgniAjT8lW0IZQNupdjwA7aas14jTpM5I")


def query_ollama(prompt, model="gemini-2.0-flash"):
    try:
        model = genai.GenerativeModel(model)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Gemini API error: {str(e)}"
