from flask import Flask, request, jsonify
import requests
import os
import google.generativeai as genai
from werkzeug.utils import secure_filename
import PyPDF2
import io

app = Flask(__name__)

# Configuration - These will be set in Render.com environment variables
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'my_secure_verify_token_12345')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Store your knowledge base (PDF content)
KNOWLEDGE_BASE = ""

def extract_text_from_pdf(pdf_content):
    """Extract text from PDF bytes"""
    try:
        pdf_file = io.BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return ""

def load_knowledge_base():
    """Load PDF from environment variable or file"""
    global KNOWLEDGE_BASE
    
    # You can upload PDF content as base64 in environment variable
    # Or mount a volume in Render with your PDF
    pdf_path = os.getenv('PDF_PATH', 'knowledge_base.pdf')
    
    if os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            KNOWLEDGE_BASE = extract_text_from_pdf(f.read())
        print("Knowledge base loaded successfully!")
    else:
        print("No PDF found. Bot will work without knowledge base.")
        KNOWLEDGE_BASE = ""

def generate_ai_response(user_message):
    """Generate response using Gemini with knowledge base context"""
    try:
        # Create prompt with knowledge base context
        if KNOWLEDGE_BASE:
            prompt = f"""You are a helpful assistant. Use the following knowledge base to answer questions accurately.

KNOWLEDGE BASE:
{KNOWLEDGE_BASE}

USER QUESTION: {user_message}

Please provide a helpful, accurate response based on the knowledge base. If the question is not covered in the knowledge base, politely let them know and offer general assistance. Keep responses concise and friendly."""
        else:
            prompt = f"""You are a helpful assistant. Please respond to this message in a friendly and helpful way:

USER MESSAGE: {user_message}"""
        
        # Generate response
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        print(f"Error generating AI response: {e}")
        return "I apologize, but I'm having trouble processing your request right now. Please try again in a moment."

def send_message(recipient_id, message_text):
    """Send message back to Instagram user"""
    url = f"https://graph.facebook.com/v18.0/me/messages"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    params = {
        "access_token": PAGE_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, params=params)
        if response.status_code == 200:
            print(f"Message sent successfully to {recipient_id}")
        else:
            print(f"Error sending message: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception sending message: {e}")

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Webhook verification endpoint for Meta"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return challenge, 200
    else:
        return 'Verification failed', 403

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle incoming Instagram messages"""
    try:
        data = request.get_json()
        print(f"Received webhook data: {data}")
        
        # Process Instagram messages
        if data.get('object') == 'instagram':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event['sender']['id']
                    
                    # Check if it's a message event
                    if 'message' in messaging_event:
                        message_text = messaging_event['message'].get('text', '')
                        
                        if message_text:
                            print(f"Received message from {sender_id}: {message_text}")
                            
                            # Generate AI response
                            ai_response = generate_ai_response(message_text)
                            
                            # Send response back
                            send_message(sender_id, ai_response)
        
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        print(f"Error handling webhook: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "knowledge_base_loaded": bool(KNOWLEDGE_BASE),
        "gemini_configured": bool(GEMINI_API_KEY),
        "page_token_configured": bool(PAGE_ACCESS_TOKEN)
    }), 200

@app.route('/privacy', methods=['GET'])
def privacy_policy():
    """Privacy policy page"""
    with open('privacy.html', 'r') as f:
        return f.read()

@app.route('/', methods=['GET'])
def home():
    """Home endpoint"""
    return """
    <h1>Instagram AI Bot is Running! 🤖</h1>
    <p>Your bot is active and ready to respond to Instagram messages.</p>
    <p>Check <a href="/health">/health</a> for system status.</p>
    <p><a href="/privacy">Privacy Policy</a></p>
    """

if __name__ == '__main__':
    # Load knowledge base on startup
    load_knowledge_base()
    
    # Run the server
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
