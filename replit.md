# Overview

This is a meeting transcription web application that converts speech to text in real-time and generates professional meeting notes using AI. The application allows users to record meetings through their browser's speech recognition capabilities, view live transcripts, and automatically generate structured meeting notes including summaries, action items, decisions, and key points using OpenAI's GPT-4o model.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask web application with SQLAlchemy ORM
- **Database**: SQLite for development with PostgreSQL support via environment configuration
- **AI Integration**: OpenAI GPT-4o API for generating structured meeting notes from transcripts
- **Data Models**: Simple Meeting model storing transcript text, generated notes, and timestamps

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Flask
- **UI Framework**: Bootstrap 5 for responsive design
- **Speech Recognition**: Browser Web Speech API (webkitSpeechRecognition/SpeechRecognition)
- **JavaScript**: Vanilla ES6+ with class-based architecture for real-time transcription handling
- **Styling**: Custom CSS with CSS variables for consistent theming

## API Structure
- **POST /generate_notes**: Accepts transcript text and returns AI-generated structured meeting notes
- **GET /**: Serves the main transcription interface

## Data Flow
1. Browser captures audio via Web Speech API
2. Real-time transcript displayed to user
3. Complete transcript sent to backend for AI processing
4. OpenAI returns structured JSON with meeting summary, action items, decisions, and key points
5. Generated notes stored in database and displayed to user

## Design Patterns
- **MVC Pattern**: Clear separation between models (SQLAlchemy), views (templates), and controllers (Flask routes)
- **Service Layer**: Dedicated OpenAI service module for AI integration
- **Environment Configuration**: Database URLs and API keys managed via environment variables

# External Dependencies

## Third-Party Services
- **OpenAI API**: GPT-4o model for natural language processing and meeting note generation
- **Web Speech API**: Browser-native speech recognition for real-time transcription

## Frontend Libraries
- **Bootstrap 5**: UI component framework and responsive grid system
- **Feather Icons**: Icon library for user interface elements

## Python Packages
- **Flask**: Web framework and application server
- **SQLAlchemy**: Database ORM and connection management
- **OpenAI**: Official Python client for OpenAI API integration
- **Werkzeug**: WSGI utilities and proxy handling

## Database
- **SQLite**: Default development database
- **PostgreSQL**: Production database support via DATABASE_URL environment variable

## Browser APIs
- **Web Speech API**: Real-time speech-to-text conversion
- **Web Audio API**: Audio input handling and processing