import os
import google.generativeai as genai

GEMINI_API_KEY = "AIzaSyA4Q8r2xeMPStNnvVYoy8lOuBBgn2qjQas"
genai.configure(api_key=GEMINI_API_KEY)

try:
    print("Listing available models...")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")
