
import os
import json
import google.generativeai as genai
import time

def test_connection():
    # Load config
    try:
        with open('wallet_config.json', 'r') as f:
            config = json.load(f)
            api_key = config.get('gemini_api_key')
            if not api_key:
                print("No API Key found")
                return
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    print(f"Configuring API with key ending in ...{api_key[-4:]}")
    genai.configure(api_key=api_key)
    
    model_name = "gemini-3-pro-preview"
    print(f"Creating model: {model_name}")
    
    try:
        model = genai.GenerativeModel(model_name)
        
        print("Sending request (this might take a while due to thinking)...")
        start_time = time.time()
        response = model.generate_content("Hello, this is a test. Are you online?")
        end_time = time.time()
        
        print(f"Response received in {end_time - start_time:.2f}s")
        print(f"Text: {response.text}")
        
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == "__main__":
    test_connection()
