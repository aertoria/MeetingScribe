# Overview

This is a meeting transcription web application that converts speech to text in real-time and generates professional meeting notes using AI. The application allows users to record meetings through their browser's speech recognition capabilities, view live transcripts, and automatically generate structured meeting notes including summaries, action items, decisions, and key points using OpenAI's GPT-4o model.

# User Preferences

Preferred communication style: Simple, everyday language.
Design theme preference: Google Workspace theme with clean, modern interface and Google's signature colors.

# System Architecture

## Backend Architecture
- **Framework**: Flask web application with SQLAlchemy ORM
- **Database**: SQLite for development with PostgreSQL support via environment configuration
- **AI Integration**: OpenAI GPT-4o API for generating structured meeting notes from transcripts
- **Data Models**: Simple Meeting model storing transcript text, generated notes, and timestamps

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Flask
- **UI Framework**: Bootstrap 5 for responsive design with Google Workspace theme
- **Speech Recognition**: Browser Web Speech API (webkitSpeechRecognition/SpeechRecognition)
- **JavaScript**: Vanilla ES6+ with class-based architecture for real-time transcription handling
- **Styling**: Google Workspace theme with Material Design principles, Google Sans fonts, and Google's signature color palette
- **Design System**: Google's color scheme (blue #1a73e8, green #34a853, red #ea4335, gray scale), rounded corners, subtle shadows, and clean typography

## API Structure
- **POST /generate_notes**: Accepts transcript text and returns AI-generated structured meeting notes
- **GET /**: Serves the main transcription interface with sidebar
- **GET /meetings**: Returns list of all saved meetings with previews
- **GET /meetings/<id>**: Returns specific meeting data including transcript and notes

## Data Flow
1. Browser captures audio via Web Speech API
2. Real-time transcript displayed to user in main content area
3. Complete transcript sent to backend for AI processing
4. OpenAI returns structured JSON with meeting summary, action items, decisions, and key points
5. Generated notes stored in database and displayed to user
6. Meeting history displayed in left sidebar for easy access and management
7. Users can click on any previous meeting to view transcript and notes

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