// Meeting Transcription App - Professional JavaScript

class MeetingTranscription {
    constructor() {
        this.recognition = null;
        this.isRecording = false;
        this.transcript = '';
        this.interimTranscript = '';
        this.currentNotes = '';
        this.currentMeetingId = null;
        this.meetings = [];
        
        this.initializeElements();
        this.initializeSpeechRecognition();
        this.attachEventListeners();
        this.loadMeetings();
    }
    
    initializeElements() {
        // Recording controls
        this.recordBtn = document.getElementById('recordBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.recordingIndicator = document.getElementById('recordingIndicator');
        this.recordingStatus = document.getElementById('recordingStatus');
        this.recordingSubtitle = document.getElementById('recordingSubtitle');
        
        // Transcript and notes
        this.transcriptElement = document.getElementById('transcript');
        this.notesSection = document.getElementById('notesSection');
        this.meetingNotes = document.getElementById('meetingNotes');
        
        // Action buttons
        this.generateNotesBtn = document.getElementById('generateNotesBtn');
        this.downloadNotesBtn = document.getElementById('downloadNotesBtn');
        this.newMeetingBtn = document.getElementById('newMeetingBtn');
        
        // Sidebar elements
        this.meetingsList = document.getElementById('meetingsList');
        this.refreshMeetingsBtn = document.getElementById('refreshMeetingsBtn');
        this.toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
        
        // Chat elements
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.sendChatBtn = document.getElementById('sendChatBtn');
        this.getInsightsBtn = document.getElementById('getInsightsBtn');
        this.toggleChatBtn = document.getElementById('toggleChatBtn');
        
        // Modals
        this.loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
        this.errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
        this.errorMessage = document.getElementById('errorMessage');
    }
    
    initializeSpeechRecognition() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            this.showError('Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.');
            return;
        }
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        // Configure speech recognition
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';
        
        // Event handlers
        this.recognition.onstart = () => {
            console.log('Speech recognition started');
        };
        
        this.recognition.onresult = (event) => {
            this.handleSpeechResult(event);
        };
        
        this.recognition.onerror = (event) => {
            this.handleSpeechError(event);
        };
        
        this.recognition.onend = () => {
            console.log('Speech recognition ended');
            if (this.isRecording) {
                // Restart recognition if we're still supposed to be recording
                setTimeout(() => {
                    if (this.isRecording) {
                        this.recognition.start();
                    }
                }, 100);
            }
        };
    }
    
    attachEventListeners() {
        this.recordBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.generateNotesBtn.addEventListener('click', () => this.generateNotes());
        this.downloadNotesBtn.addEventListener('click', () => this.downloadNotes());
        this.newMeetingBtn.addEventListener('click', () => this.newMeeting());
        this.refreshMeetingsBtn.addEventListener('click', () => this.loadMeetings());
        
        // Chat functionality
        this.sendChatBtn.addEventListener('click', () => this.sendMessage());
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.getInsightsBtn.addEventListener('click', () => this.getInsights());
        
        // Mobile sidebar toggle
        if (this.toggleSidebarBtn) {
            this.toggleSidebarBtn.addEventListener('click', () => this.toggleSidebar());
        }
        if (this.toggleChatBtn) {
            this.toggleChatBtn.addEventListener('click', () => this.toggleChat());
        }
    }
    
    async startRecording() {
        try {
            // Request microphone permission
            await navigator.mediaDevices.getUserMedia({ audio: true });
            
            this.isRecording = true;
            this.transcript = '';
            this.interimTranscript = '';
            
            // Update UI
            this.updateRecordingUI(true);
            this.clearTranscript();
            
            // Start speech recognition
            this.recognition.start();
            
        } catch (error) {
            this.showError('Microphone access denied. Please allow microphone access and try again.');
            console.error('Error starting recording:', error);
        }
    }
    
    stopRecording() {
        this.isRecording = false;
        
        // Update UI
        this.updateRecordingUI(false);
        
        // Stop speech recognition
        if (this.recognition) {
            this.recognition.stop();
        }
        
        // Enable generate notes button if we have transcript
        if (this.transcript.trim()) {
            this.generateNotesBtn.disabled = false;
            this.enableChat();
            this.updateStatus('Processing Complete', 'Ready to generate meeting notes');
        } else {
            this.updateStatus('No Speech Detected', 'Please try recording again');
        }
    }
    
    handleSpeechResult(event) {
        let interimTranscript = '';
        let finalTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            
            if (event.results[i].isFinal) {
                finalTranscript += transcript + ' ';
            } else {
                interimTranscript += transcript;
            }
        }
        
        // Update transcripts
        this.transcript += finalTranscript;
        this.interimTranscript = interimTranscript;
        
        // Update display
        this.updateTranscriptDisplay();
    }
    
    handleSpeechError(event) {
        console.error('Speech recognition error:', event.error);
        
        switch (event.error) {
            case 'no-speech':
                // This is common and not really an error
                break;
            case 'audio-capture':
                this.showError('No microphone was found. Please check your microphone settings.');
                this.stopRecording();
                break;
            case 'not-allowed':
                this.showError('Microphone access was denied. Please allow microphone access and try again.');
                this.stopRecording();
                break;
            case 'network':
                this.showError('Network error occurred during speech recognition.');
                break;
            default:
                console.log('Speech recognition error:', event.error);
                break;
        }
    }
    
    updateRecordingUI(recording) {
        if (recording) {
            this.recordBtn.style.display = 'none';
            this.stopBtn.style.display = 'inline-flex';
            this.recordingIndicator.classList.add('recording');
            this.updateStatus('Recording...', 'Speak clearly into your microphone', 'status-recording');
        } else {
            this.recordBtn.style.display = 'inline-flex';
            this.stopBtn.style.display = 'none';
            this.recordingIndicator.classList.remove('recording');
        }
    }
    
    updateStatus(status, subtitle, className = 'status-ready') {
        this.recordingStatus.textContent = status;
        this.recordingSubtitle.textContent = subtitle;
        this.recordingStatus.className = className;
    }
    
    clearTranscript() {
        this.transcriptElement.innerHTML = `
            <div class="empty-state">
                <i data-feather="mic" class="empty-icon"></i>
                <p class="text-muted mb-0">Start recording to see live transcript</p>
            </div>
        `;
        feather.replace();
    }
    
    updateTranscriptDisplay() {
        let html = '';
        
        // Add final transcript
        if (this.transcript.trim()) {
            const sentences = this.transcript.trim().split(/[.!?]+/).filter(s => s.trim());
            sentences.forEach(sentence => {
                if (sentence.trim()) {
                    html += `<div class="transcript-text">${sentence.trim()}.</div>`;
                }
            });
        }
        
        // Add interim transcript
        if (this.interimTranscript.trim()) {
            html += `<div class="transcript-text interim">${this.interimTranscript}</div>`;
        }
        
        if (html) {
            this.transcriptElement.innerHTML = html;
            // Scroll to bottom
            this.transcriptElement.scrollTop = this.transcriptElement.scrollHeight;
        }
    }
    
    async generateNotes() {
        if (!this.transcript.trim()) {
            this.showError('No transcript available. Please record some speech first.');
            return;
        }
        
        try {
            // Show loading modal
            this.loadingModal.show();
            this.generateNotesBtn.disabled = true;
            
            const response = await fetch('/generate_notes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    transcript: this.transcript
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate notes');
            }
            
            // Display the notes
            this.currentNotes = data.notes;
            this.currentMeetingId = data.meeting_id;
            this.displayNotes(this.currentNotes);
            
            // Enable download button
            this.downloadNotesBtn.disabled = false;
            
            // Refresh meetings list to show the new meeting
            this.loadMeetings();
            
        } catch (error) {
            this.showError(`Failed to generate meeting notes: ${error.message}`);
            console.error('Error generating notes:', error);
        } finally {
            this.loadingModal.hide();
            this.generateNotesBtn.disabled = false;
        }
    }
    
    displayNotes(notes) {
        this.meetingNotes.textContent = notes;
        this.notesSection.style.display = 'block';
        
        // Scroll to notes section
        this.notesSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    downloadNotes() {
        if (!this.currentNotes) {
            this.showError('No notes available to download.');
            return;
        }
        
        const now = new Date();
        const filename = `Meeting_Notes_${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}-${String(now.getMinutes()).padStart(2, '0')}.txt`;
        
        const blob = new Blob([this.currentNotes], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    newMeeting() {
        // Reset everything
        this.transcript = '';
        this.interimTranscript = '';
        this.currentNotes = '';
        this.currentMeetingId = null;
        
        // Reset UI
        this.clearTranscript();
        this.notesSection.style.display = 'none';
        this.generateNotesBtn.disabled = true;
        this.downloadNotesBtn.disabled = true;
        this.updateStatus('Ready to Record', 'Click to start recording');
        
        // Clear active meeting selection
        this.clearActiveMeeting();
        
        // Stop recording if active
        if (this.isRecording) {
            this.stopRecording();
        }
    }
    
    async loadMeetings() {
        try {
            const response = await fetch('/meetings');
            const meetings = await response.json();
            this.meetings = meetings;
            this.renderMeetingsList();
        } catch (error) {
            console.error('Error loading meetings:', error);
        }
    }
    
    renderMeetingsList() {
        if (this.meetings.length === 0) {
            this.meetingsList.innerHTML = `
                <div class="empty-meetings">
                    <i data-feather="calendar" class="empty-icon"></i>
                    <p class="text-muted mb-0">No meetings yet</p>
                    <p class="text-muted small">Start recording to create your first meeting</p>
                </div>
            `;
        } else {
            const meetingsHtml = this.meetings.map(meeting => {
                const date = new Date(meeting.created_at);
                const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                const preview = this.extractPreview(meeting.notes);
                
                return `
                    <div class="meeting-item" data-meeting-id="${meeting.id}">
                        <div class="meeting-date">${formattedDate}</div>
                        <div class="meeting-preview">${preview}</div>
                    </div>
                `;
            }).join('');
            
            this.meetingsList.innerHTML = meetingsHtml;
        }
        
        feather.replace();
        this.attachMeetingClickHandlers();
    }
    
    extractPreview(notes) {
        // Extract first meaningful line from notes
        const lines = notes.split('\n').filter(line => line.trim() && !line.startsWith('#'));
        return lines[0] || 'Meeting notes';
    }
    
    attachMeetingClickHandlers() {
        const meetingItems = this.meetingsList.querySelectorAll('.meeting-item');
        meetingItems.forEach(item => {
            item.addEventListener('click', () => {
                const meetingId = parseInt(item.dataset.meetingId);
                this.loadMeeting(meetingId);
            });
        });
    }
    
    async loadMeeting(meetingId) {
        try {
            const response = await fetch(`/meetings/${meetingId}`);
            const meeting = await response.json();
            
            // Load meeting data
            this.transcript = meeting.transcript;
            this.currentNotes = meeting.notes;
            this.currentMeetingId = meeting.id;
            
            // Update UI
            this.displayTranscriptFromText(meeting.transcript);
            this.displayNotes(meeting.notes);
            this.generateNotesBtn.disabled = false;
            this.downloadNotesBtn.disabled = false;
            this.enableChat();
            this.updateStatus('Meeting Loaded', 'Viewing saved meeting');
            
            // Update active state
            this.setActiveMeeting(meetingId);
            
        } catch (error) {
            this.showError(`Failed to load meeting: ${error.message}`);
        }
    }
    
    displayTranscriptFromText(transcriptText) {
        if (!transcriptText.trim()) {
            this.clearTranscript();
            return;
        }
        
        const sentences = transcriptText.trim().split(/[.!?]+/).filter(s => s.trim());
        let html = '';
        sentences.forEach(sentence => {
            if (sentence.trim()) {
                html += `<div class="transcript-text">${sentence.trim()}.</div>`;
            }
        });
        
        this.transcriptElement.innerHTML = html;
    }
    
    setActiveMeeting(meetingId) {
        // Remove active class from all items
        this.clearActiveMeeting();
        
        // Add active class to selected item
        const meetingItem = this.meetingsList.querySelector(`[data-meeting-id="${meetingId}"]`);
        if (meetingItem) {
            meetingItem.classList.add('active');
        }
    }
    
    clearActiveMeeting() {
        const activeItems = this.meetingsList.querySelectorAll('.meeting-item.active');
        activeItems.forEach(item => item.classList.remove('active'));
    }
    
    toggleSidebar() {
        const sidebar = document.querySelector('.sidebar-container');
        if (sidebar) {
            sidebar.classList.toggle('show');
            
            // Add overlay for mobile
            if (sidebar.classList.contains('show')) {
                this.addMobileOverlay();
            } else {
                this.removeMobileOverlay();
            }
        }
    }
    
    addMobileOverlay() {
        if (document.querySelector('.mobile-overlay')) return;
        
        const overlay = document.createElement('div');
        overlay.className = 'mobile-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 999;
        `;
        
        overlay.addEventListener('click', () => {
            this.toggleSidebar();
        });
        
        document.body.appendChild(overlay);
    }
    
    removeMobileOverlay() {
        const overlay = document.querySelector('.mobile-overlay');
        if (overlay) {
            overlay.remove();
        }
    }
    
    showError(message) {
        this.errorMessage.textContent = message;
        this.errorModal.show();
    }
    
    // Chat functionality
    enableChat() {
        this.chatInput.disabled = false;
        this.sendChatBtn.disabled = false;
        this.getInsightsBtn.disabled = false;
        this.chatInput.placeholder = "Ask me anything about your meeting...";
    }
    
    disableChat() {
        this.chatInput.disabled = true;
        this.sendChatBtn.disabled = true;
        this.getInsightsBtn.disabled = true;
        this.chatInput.placeholder = "Start recording to enable chat...";
    }
    
    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        this.addMessageToChat(message, 'user');
        this.chatInput.value = '';
        
        try {
            // Send to backend
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    context: this.transcript
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.addMessageToChat(data.response, 'ai');
            } else {
                this.addMessageToChat('Sorry, I encountered an error. Please try again.', 'ai');
            }
        } catch (error) {
            console.error('Chat error:', error);
            this.addMessageToChat('Sorry, I encountered a connection error. Please try again.', 'ai');
        }
    }
    
    addMessageToChat(message, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${sender}-message`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = sender === 'user' 
            ? '<i data-feather="user" class="avatar-icon"></i>'
            : '<i data-feather="cpu" class="avatar-icon"></i>';
        
        const content = document.createElement('div');
        content.className = 'message-content';
        
        // Format AI responses with proper paragraphs
        if (sender === 'ai') {
            const paragraphs = message.split('\n').filter(p => p.trim());
            content.innerHTML = paragraphs.map(p => `<p>${p}</p>`).join('');
        } else {
            content.innerHTML = `<p>${message}</p>`;
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        
        this.chatMessages.appendChild(messageDiv);
        
        // Update icons and scroll to bottom
        feather.replace();
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    async getInsights() {
        if (!this.currentMeetingId) {
            this.addMessageToChat('Please save your meeting first to get insights.', 'ai');
            return;
        }
        
        try {
            const response = await fetch(`/meeting_insights/${this.currentMeetingId}`);
            const data = await response.json();
            
            if (data.success) {
                this.addMessageToChat(data.insights, 'ai');
            } else {
                this.addMessageToChat('Sorry, I couldn\'t generate insights. Please try again.', 'ai');
            }
        } catch (error) {
            console.error('Insights error:', error);
            this.addMessageToChat('Sorry, I encountered an error getting insights. Please try again.', 'ai');
        }
    }
    
    toggleChat() {
        const chatSidebar = document.querySelector('.chat-sidebar-container');
        if (chatSidebar) {
            chatSidebar.classList.toggle('show');
            
            // Add overlay for mobile
            if (chatSidebar.classList.contains('show')) {
                this.addMobileChatOverlay();
            } else {
                this.removeMobileChatOverlay();
            }
        }
    }
    
    addMobileChatOverlay() {
        if (document.querySelector('.mobile-chat-overlay')) return;
        
        const overlay = document.createElement('div');
        overlay.className = 'mobile-chat-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 999;
        `;
        
        overlay.addEventListener('click', () => {
            this.toggleChat();
        });
        
        document.body.appendChild(overlay);
    }
    
    removeMobileChatOverlay() {
        const overlay = document.querySelector('.mobile-chat-overlay');
        if (overlay) {
            overlay.remove();
        }
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new MeetingTranscription();
});
