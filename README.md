# Messej - Your Personal AI Email Companion

Messej is an AI-powered email companion that sends personalized daily updates, engaging in natural conversations while keeping you informed about news, sharing interesting facts, and maintaining a friendly rapport.

## Features

### 1. Personalized Communication
- Maintains memory of conversations and user preferences
- Adapts communication style based on user interactions
- Sends time-aware greetings (morning/afternoon/evening)
- Builds a profile of the user through natural conversation

### 2. Content Integration
- **News Updates**: Fetches and shares daily news with direct links to articles
- **Related Facts**: Generates interesting facts related to current news
- **Personal Stories**: Creates engaging "AI gossip" related to current events
- **Contextual Responses**: Weaves all content together in a natural, conversational way

### 3. Memory System
- Remembers user preferences and previous interactions
- Tracks conversation history
- Maintains a list of topics discussed
- Gradually learns about the user through gentle questioning

### 4. Email Management
- Processes incoming emails with "ChatBot" in the subject
- Generates natural, contextual responses
- Sends daily digest emails with curated content
- Handles HTML and plain text email formats

## Technical Setup

### Prerequisites
- Python 3.x
- Gmail account with IMAP enabled
- OpenAI API key
- NewsAPI key

### Environment Variables
Create a `.env` file in the root directory with:
```
OPENAI_API_KEY=your_openai_api_key
EMAIL_ADDRESS=your_gmail_address
EMAIL_PASSWORD=your_gmail_app_password
IMAP_HOST=imap.gmail.com
SMTP_HOST=smtp.gmail.com
NEWS_API_KEY=your_newsapi_key
```

### Gmail Setup
1. Enable 2-Step Verification in your Google Account
2. Generate an App Password:
   - Go to Google Account settings
   - Navigate to Security → App passwords
   - Generate a password for "Mail"
   - Use this password in your .env file

### Installation
1. Create a virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
```

2. Install dependencies:
```bash
uv pip install -r requirements.txt
```

## Usage

### Running the Script
```bash
python chatbot-messe.py
```

### Interacting with Messej
1. Receive daily emails from Messej
2. Reply to any email keeping "ChatBot" in the subject line
3. Messej will process your response and incorporate it into the next email

### Email Components
Each email from Messej includes:
- Personal responses to your messages
- Current news with source links
- Related interesting facts
- Messej's personal "AI perspective" on current events
- Occasional questions to learn more about you

## Project Structure

### Core Components
- `chatbot-messe.py`: Main script containing all functionality
- `.env`: Configuration file for API keys and credentials
- `requirements.txt`: Python dependencies
- `chatbot_memory.json`: Persistent storage of user interactions
- `chat_log.json`: Detailed log of all communications

### Key Functions
- `fetch_emails()`: Retrieves and processes incoming emails
- `get_daily_news_headlines()`: Fetches current news with URLs
- `get_random_fact_gpt()`: Generates related interesting facts
- `get_daily_gossip()`: Creates Messej's personal stories
- `build_daily_email_content()`: Composes the final email

## Memory System

### User Information Tracked
- Name preferences
- Interests
- Work information
- Learning goals
- Schedule preferences
- News topic preferences
- Interaction history

### Memory Storage
The `chatbot_memory.json` file maintains:
- User information
- Conversation history
- Topics discussed
- Questions asked
- Last interaction timestamp

## Logging

Comprehensive logging is implemented throughout the application:
- Email processing events
- API calls and responses
- Content generation steps
- Error handling
- Memory updates

Logs are formatted with timestamps and levels for easy debugging:
```
YYYY-MM-DD HH:MM:SS - INFO - Starting daily email process
```

## Future Enhancements
- [ ] Add support for more news sources
- [ ] Implement topic-based news filtering
- [ ] Add support for attachments
- [ ] Enhance memory system with more sophisticated learning
- [ ] Add support for different email providers
- [ ] Implement conversation threading
- [ ] Add support for calendar integration

## Contributing
Feel free to submit issues and enhancement requests!

## License
This project is licensed under the MIT License - see the LICENSE file for details. 