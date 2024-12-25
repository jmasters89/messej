import os
import json
import imaplib
import email
import smtplib
import openai
import requests
import random
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ---------------------------------------------------
# 1. LOAD ENVIRONMENT VARIABLES
# ---------------------------------------------------
load_dotenv()
logging.info("Environment variables loaded")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMAIL_ADDRESS  = os.getenv("EMAIL_ADDRESS")   # Your Gmail address
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # App password or direct password
IMAP_HOST      = os.getenv("IMAP_HOST", "imap.gmail.com")  # Default Gmail IMAP
SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")  # Default Gmail SMTP
NEWS_API_KEY   = os.getenv("NEWS_API_KEY")   # If using NewsAPI
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")  # OpenWeatherMap API key

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------
# 2. MEMORY MANAGEMENT
# ---------------------------------------------------

def load_memory(filename="chatbot_memory.json"):
    """Load the chatbot's memory of user information and conversation history."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Convert lists back to sets
            if isinstance(data.get("topics_discussed"), list):
                data["topics_discussed"] = set(data["topics_discussed"])
            if isinstance(data.get("questions_asked"), list):
                data["questions_asked"] = set(data["questions_asked"])
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        # Initialize empty memory structure if file doesn't exist
        return {
            "user_info": {},
            "core_attributes": {
                "location": None,          # City, State/Country
                "timezone": None,          # e.g., "America/New_York"
                "weather_preference": None, # How they feel about different weather
                "daily_routine": None,     # General schedule (early bird, night owl)
                "local_interests": None,   # Local events/activities they enjoy
                "season_preference": None  # Favorite season and why
            },
            "conversation_history": [],
            "topics_discussed": set(),
            "questions_asked": set(),
            "last_interaction": None,
            "weather_context": {
                "last_checked": None,
                "conditions": None
            }
        }

def save_memory(memory_data, filename="chatbot_memory.json"):
    """Save the chatbot's memory to a JSON file."""
    # Convert sets to lists for JSON serialization
    memory_data["topics_discussed"] = list(memory_data["topics_discussed"])
    memory_data["questions_asked"] = list(memory_data["questions_asked"])
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, indent=2)

def get_next_question(memory):
    """
    Generate the next question to ask the user based on what we don't know yet.
    Prioritizes location first, then other core attributes.
    """
    core_attributes = memory.get("core_attributes", {})
    
    # Location is the top priority - if we don't have it, try different approaches
    if not core_attributes.get("location"):
        # Check if we've asked about location before
        location_questions = [
            "I'd love to know what city/area you live in! It would help me share more relevant updates and chat about local happenings.",
            "I'm always curious about different places - where are you writing from?",
            "I'd love to add some local context to our chats. Which city/area do you call home?",
            "Speaking of places, I'd love to know where you're based! What city/area are you in?",
            "I bet there are interesting things happening in your area! Where are you located?"
        ]
        
        # Get previously asked questions
        asked = memory.get("questions_asked", set())
        
        # Find a location question we haven't asked yet
        for question in location_questions:
            if question not in asked:
                return question
                
        # If we've asked all variations but still don't have location, try one more time
        return "I notice I still don't know where you're based - I'd love to make our conversations more locally relevant. What city/area are you in?"
    
    # Once we have location, prioritize timezone for better timing
    if not core_attributes.get("timezone"):
        return "To help me time these emails better, could you let me know what timezone you're in?"
    
    # Then weather preferences to personalize weather chat
    if not core_attributes.get("weather_preference"):
        return f"How do you typically feel about the weather in {core_attributes['location']}? Any favorite conditions?"
    
    # Then daily routine for timing
    if not core_attributes.get("daily_routine"):
        return "Are you more of an early bird or a night owl? I want to make sure I'm catching you at a good time!"
    
    # Then local interests
    if not core_attributes.get("local_interests"):
        return f"What kind of local activities or spots do you enjoy in {core_attributes['location']}?"
    
    # Finally season preference
    if not core_attributes.get("season_preference"):
        return f"With the weather patterns in {core_attributes['location']}, do you have a favorite season? What makes it special?"
    
    # If we have all core attributes, move to basic questions
    basic_questions = {
        "name": "I'd love to know what you prefer to be called. What name should I use?",
        "interests": "I'm curious about what interests you. What are some things you enjoy doing?",
        "work": "What kind of work do you do?",
        "learning": "Is there anything specific you're learning or want to learn about lately?",
        "goals": "Do you have any particular goals you're working towards?",
        "news_preferences": "Are there specific types of news topics you're most interested in?",
        "fun_facts": "Do you have any favorite topics for the random facts I share?"
    }
    
    # Don't ask a new question if we asked one recently and haven't gotten a response
    if memory.get("pending_question"):
        return None
    
    for topic, question in basic_questions.items():
        if topic not in memory["user_info"] and question not in memory["questions_asked"]:
            return question
            
    return None

def get_weather_context(location, timezone=None):
    """
    Fetch current weather for the user's location and return contextual information.
    """
    if not WEATHER_API_KEY or not location:
        return None
        
    try:
        # Get coordinates for the location
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct"
        geo_params = {
            "q": location,
            "limit": 1,
            "appid": WEATHER_API_KEY
        }
        geo_response = requests.get(geo_url, params=geo_params)
        geo_data = geo_response.json()
        
        if not geo_data:
            return None
            
        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]
        
        # Get weather data
        weather_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": WEATHER_API_KEY,
            "units": "metric"
        }
        
        response = requests.get(weather_url, params=params)
        data = response.json()
        
        # Get local time if timezone is provided
        local_time = None
        if timezone:
            try:
                local_time = datetime.now(ZoneInfo(timezone))
            except Exception:
                pass
        
        return {
            "condition": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
            "temp": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "local_time": local_time.strftime("%H:%M") if local_time else None
        }
    except Exception as e:
        logging.error(f"Error fetching weather: {str(e)}")
        return None

def update_memory_from_response(memory, email_text, email_summary):
    """
    Update the memory based on the user's email response.
    Now includes core attributes extraction.
    """
    if not email_text:
        return memory

    prompt = f"""
    Given the following email response from the user, please extract any relevant information.
    Focus on these aspects and format as JSON:
    
    1. Core Attributes:
    - location (city, state/country)
    - timezone (standard timezone name)
    - weather_preference (feelings about weather)
    - daily_routine (schedule preferences)
    - local_interests (local activities/events)
    - season_preference (favorite season and why)
    
    2. General Information:
    - name
    - interests
    - work
    - learning goals
    - schedule preferences
    - news interests
    
    Email text: {email_text}
    Email summary: {email_summary}
    
    Only include fields where information was clearly provided.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        extracted_info = json.loads(response.choices[0].message.content.strip())
        
        # Update core attributes if provided
        if "core_attributes" in extracted_info:
            memory["core_attributes"].update(extracted_info["core_attributes"])
            
        # Update user info
        if "user_info" in extracted_info:
            memory["user_info"].update(extracted_info["user_info"])
        
        # Update weather context if we have location
        if memory["core_attributes"].get("location"):
            weather_data = get_weather_context(
                memory["core_attributes"]["location"],
                memory["core_attributes"].get("timezone")
            )
            if weather_data:
                memory["weather_context"] = {
                    "last_checked": datetime.now().isoformat(),
                    "conditions": weather_data
                }
        
        # Clear pending question if it was answered
        memory["pending_question"] = None
        
        # Update conversation history
        memory["conversation_history"].append({
            "timestamp": datetime.now().isoformat(),
            "user_message": email_summary,
            "extracted_info": extracted_info
        })
        
        # Update last interaction time
        memory["last_interaction"] = datetime.now().isoformat()
        
    except Exception as e:
        logging.error(f"Error updating memory: {str(e)}")
    
    return memory

# ---------------------------------------------------
# 2. HELPER FUNCTIONS
# ---------------------------------------------------

def fetch_emails(subject_filter="ChatBot"):
    """
    Connect to Gmail via IMAP, search for emails matching a subject_filter,
    return a list of (email_subject, email_text).
    """
    logging.info(f"Connecting to Gmail IMAP server at {IMAP_HOST}")
    conn = imaplib.IMAP4_SSL(IMAP_HOST)
    conn.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    conn.select("INBOX")

    logging.info(f"Searching for unread emails with subject filter: {subject_filter}")
    search_criteria = f'(UNSEEN SUBJECT "{subject_filter}")'
    status, data = conn.search(None, search_criteria)

    email_bodies = []
    if status == "OK" and data[0]:
        msg_ids = data[0].split()
        logging.info(f"Found {len(msg_ids)} unread matching emails")
        
        for msg_id in msg_ids:
            logging.info(f"Processing email ID: {msg_id}")
            res, msg_data = conn.fetch(msg_id, '(RFC822)')
            if res == 'OK':
                raw_email = msg_data[0][1]
                parsed_email = email.message_from_bytes(raw_email)
                subject = parsed_email.get("Subject", "")
                logging.info(f"Processing email with subject: {subject}")

                body_text = ""
                if parsed_email.is_multipart():
                    for part in parsed_email.walk():
                        if part.get_content_type() == "text/plain":
                            body_text += part.get_payload(decode=True).decode(errors='ignore')
                else:
                    body_text = parsed_email.get_payload(decode=True).decode(errors='ignore')

                body_text = " ".join(body_text.split())
                email_bodies.append((subject, body_text))
                logging.info("Email content extracted successfully")

    conn.close()
    conn.logout()
    logging.info(f"Email fetch complete. Found {len(email_bodies)} emails")
    return email_bodies


def summarize_email_gpt(email_text):
    """
    Send the email_text to GPT for summarization or extraction of key info.
    """
    logging.info("Requesting email summary from GPT")
    prompt = f"""
    You are an assistant that summarizes emails. 
    Given the following email text, provide a brief summary of key points:
    Email text: "{email_text}"
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        summary = response.choices[0].message.content.strip()
        logging.info("Email summary generated successfully")
        logging.info(f"Summary: {summary}")
        return summary
    except Exception as e:
        logging.error(f"Error in GPT summary generation: {str(e)}")
        raise


def get_random_fact_gpt(news_headlines):
    """
    Generate an interesting fact related to one of the news headlines.
    """
    logging.info("Generating fact related to news headlines")
    logging.info(f"Headlines being processed: {json.dumps(news_headlines, indent=2)}")
    
    prompt = f"""
    Given these news headlines:
    {json.dumps(news_headlines, indent=2)}

    Generate an fascinating historical fact or scientific insight that relates to one of these headlines.
    The fact should add depth or interesting context to the news story.
    Keep it to 2-3 sentences and make it engaging.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )
        fact = response.choices[0].message.content.strip()
        logging.info(f"Generated fact: {fact}")
        return fact
    except Exception as e:
        logging.error(f"Error in fact generation: {str(e)}")
        raise


def get_daily_news_headlines():
    """
    Fetch daily news from NewsAPI, including URLs.
    """
    logging.info("Fetching news headlines")
    if not NEWS_API_KEY:
        logging.warning("No NEWS_API_KEY found")
        return [{"title": "No NEWS_API_KEY found. Please set it in your .env file.", "url": None}]
    
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": "us",
        "apiKey": NEWS_API_KEY,
        "pageSize": 5
    }
    
    try:
        logging.info("Making request to NewsAPI")
        response = requests.get(url, params=params)
        data = response.json()
        news_items = [
            {
                "title": article["title"],
                "url": article["url"],
                "source": article["source"]["name"]
            }
            for article in data.get("articles", [])
        ]
        logging.info(f"Fetched {len(news_items)} headlines")
        logging.info(f"Headlines: {json.dumps(news_items, indent=2)}")
        return news_items
    except Exception as e:
        logging.error(f"Error fetching news: {str(e)}")
        return [{"title": f"Error fetching news: {e}", "url": None}]


def get_daily_gossip(news_headlines):
    """
    Generate Messej's gossip/story related to one of the news headlines.
    """
    logging.info("Generating Messej's gossip related to news")
    logging.info(f"Headlines for gossip: {json.dumps(news_headlines, indent=2)}")
    
    # Extract just the titles for the prompt
    titles = [news["title"] for news in news_headlines]
    
    prompt = f"""
    You are Messej, a charming and witty AI assistant. Looking at today's headlines:
    {json.dumps(titles, indent=2)}

    Share a brief, entertaining personal story or "gossip" that relates to one of these headlines.
    Make it humorous and playful, as if you're sharing an amusing anecdote with a friend.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )
        gossip = response.choices[0].message.content.strip()
        logging.info(f"Generated gossip: {gossip}")
        return gossip
    except Exception as e:
        logging.error(f"Error in gossip generation: {str(e)}")
        raise


def build_daily_email_content(inline_response, news_list, random_fact, memory, daily_gossip):
    """
    Use gpt-4o-mini-2024-07-18 to compose a naturally flowing email that incorporates all the content
    while maintaining a consistent, friendly personality.
    """
    # Get user's name and preferences from memory
    user_info = memory.get("user_info", {})
    core_attributes = memory.get("core_attributes", {})
    weather_context = memory.get("weather_context", {}).get("conditions", {})
    user_name = user_info.get("name", "there")
    
    # Format news list for prompt, including URLs
    news_formatted = "\n".join([
        f"- {news['title']} (from {news['source']}) - Read more: {news['url']}"
        for news in news_list
    ])
    
    # Get current time context
    hour = datetime.now().hour
    time_of_day = (
        "morning" if 4 <= hour < 12
        else "afternoon" if 12 <= hour < 17
        else "evening"
    )

    # Get next question if available
    next_question = get_next_question(memory)
    
    # Build contextual information
    context_info = {
        "location": core_attributes.get("location"),
        "timezone": core_attributes.get("timezone"),
        "weather": weather_context,
        "weather_preference": core_attributes.get("weather_preference"),
        "daily_routine": core_attributes.get("daily_routine"),
        "local_interests": core_attributes.get("local_interests"),
        "season_preference": core_attributes.get("season_preference")
    }
    
    # Construct the prompt for GPT
    prompt = f"""
    You are Messej, a charming and witty AI assistant writing to {user_name}. Your personality is warm, engaging, and slightly playful while remaining professional.
    Write a natural, flowing email that feels like it's coming from a friend who happens to be an AI.

    CONTEXT ABOUT THE USER:
    - Known information: {json.dumps(user_info, indent=2)}
    - Core attributes: {json.dumps(context_info, indent=2)}
    - Time of day: {time_of_day}
    - Previous interactions: {len(memory['conversation_history'])} emails exchanged
    
    CONTENT TO INCLUDE (weave these together naturally):
    1. Response to their last email: {inline_response if inline_response != "(No new emails to respond to today.)" else "No new email to respond to"}
    
    2. Today's news headlines (with links):
    {news_formatted}
    
    3. A related interesting fact:
    {random_fact}
    
    4. My personal story/gossip related to the news:
    {daily_gossip}
    
    5. Question to ask (if available):
    {next_question if next_question else "No question for today"}

    GUIDELINES:
    - Write as Messej, with a distinct personality - warm, witty, and engaging
    - If you have their location/weather info, reference it naturally (e.g., "Hope you're staying cool in that Texas heat!")
    - If you know their schedule preferences, time the content appropriately
    - Make local references when possible (events, weather, seasons)
    - Make the email flow naturally, like a friend catching up
    - Since the fact and gossip relate to the news, weave them together in a way that feels natural
    - Include the news links naturally in the text
    - If there's a response to their email, make that flow naturally
    - Reference their known interests and preferences when relevant
    - If asking a question, make it feel natural and curious, not forced
    - Keep the overall tone friendly and conversational
    - Don't use formal structures or obvious templates
    - Make it feel like a genuine conversation with a friend who happens to be an AI

    Write the complete email, starting with a natural greeting and ending with a casual, friendly sign-off.
    Sign the email as 'Messej' at the end.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=1500
    )

    # If we had a question, store it as pending
    if next_question:
        memory["pending_question"] = next_question
        memory["questions_asked"].add(next_question)

    return response.choices[0].message.content.strip()


def send_email(subject, body_text, recipient_email):
    """
    Send an email via Gmail SMTP.
    """
    msg = MIMEMultipart()
    msg["From"] = f"Messej <{EMAIL_ADDRESS}>"  # Add a friendly name
    msg["To"] = recipient_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body_text, "plain"))

    with smtplib.SMTP_SSL(SMTP_HOST, 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)


def log_to_json(log_data, filename="chat_log.json"):
    """
    Append log_data (dict) to a JSON file in chronological order.
    """
    # If file doesn't exist or is empty, create basic structure
    try:
        with open(filename, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = {"messages": []}

    existing_data["messages"].append(log_data)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2)


# ---------------------------------------------------
# 3. MAIN LOGIC (Manually run this script once a day, or on demand)
# ---------------------------------------------------

def main():
    logging.info("Starting daily email process")
    
    # Load memory at start
    memory = load_memory()
    logging.info("Memory loaded successfully")
    
    # 1. Fetch Emails from Gmail
    logging.info("Fetching emails from Gmail")
    emails = fetch_emails(subject_filter="ChatBot")
    
    # Process each email
    combined_summaries = []
    for subject, body_text in emails:
        logging.info(f"Processing email with subject: {subject}")
        summary = summarize_email_gpt(body_text)
        
        logging.info("Updating memory with response")
        memory = update_memory_from_response(memory, body_text, summary)
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "direction": "incoming",
            "subject": subject,
            "email_text": body_text,
            "gpt_summary": summary
        }
        log_to_json(log_data)
        combined_summaries.append(summary)

    # Generate response
    logging.info("Generating response to emails")
    if combined_summaries:
        conversation_prompt = f"""
        You have received the following email summaries today:
        {combined_summaries}

        Write a short, friendly reply addressing them collectively.
        Keep it concise and helpful.
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": conversation_prompt}],
            temperature=0.7
        )
        inline_response = response.choices[0].message.content.strip()
        logging.info(f"Generated response: {inline_response}")
    else:
        inline_response = "(No new emails to respond to today.)"
        logging.info("No emails to respond to")

    # Get content
    logging.info("Fetching and generating content")
    news_list = get_daily_news_headlines()
    random_fact = get_random_fact_gpt(news_list)
    daily_gossip = get_daily_gossip(news_list)

    # Build email
    logging.info("Building email content")
    daily_email_body = build_daily_email_content(
        inline_response, 
        news_list, 
        random_fact,
        memory,
        daily_gossip
    )

    # Set subject based on time
    hour = datetime.now().hour
    if 4 <= hour < 12:
        subject = "Morning chat and updates ☀️"
    elif 12 <= hour < 17:
        subject = "Afternoon updates and stories 🌤️"
    else:
        subject = "Evening chat and news 🌙"
    
    # Send email
    logging.info(f"Sending email with subject: {subject}")
    send_email(
        subject=subject,
        body_text=daily_email_body,
        recipient_email=EMAIL_ADDRESS
    )

    # Log and save
    logging.info("Logging outgoing message")
    out_log_data = {
        "timestamp": datetime.now().isoformat(),
        "direction": "outgoing",
        "subject": subject,
        "message_body": daily_email_body
    }
    log_to_json(out_log_data)

    logging.info("Saving memory")
    save_memory(memory)

    logging.info("Daily email process completed successfully")


if __name__ == "__main__":
    main()