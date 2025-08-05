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
        
        // Speaker detection
        this.currentSpeaker = 1;
        this.speakers = new Map();
        this.lastSpeechTime = Date.now();
        this.speakerColors = [
            '#1a73e8', // Google Blue
            '#34a853', // Google Green  
            '#ea4335', // Google Red
            '#fbbc04', // Google Yellow
            '#673ab7', // Purple
            '#ff6f00', // Orange
            '#00796b', // Teal
            '#5d4037'  // Brown
        ];
        this.speakerChangeThreshold = 3000; // 3 seconds pause for definite speaker change
        this.sameSpeakerThreshold = 1500; // Less than 1.5 seconds = likely same speaker
        this.transcriptSegments = [];
        this.speakerHistory = []; // Track speaker patterns for correlation
        this.lastActiveSpeaker = null; // Remember last active speaker
        this.speakerPatterns = new Map(); // Store speech patterns for each speaker
        
        this.initializeElements();
        this.initializeSpeechRecognition();
        this.attachEventListeners();
        this.setupChatListeners();
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
        this.copyNotesBtn = document.getElementById('copyNotesBtn');
        this.exportNotesBtn = document.getElementById('exportNotesBtn');
        
        // Sidebar elements
        this.meetingsList = document.getElementById('meetingsList');
        this.refreshMeetingsBtn = document.getElementById('refreshMeetingsBtn');
        this.toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
        
        // Transcript stats  
        this.speakerCount = document.getElementById('speakerCount');
        this.speakerCountText = document.getElementById('speakerCountText');
        this.wordCount = document.getElementById('wordCount');
        this.wordCountText = document.getElementById('wordCountText');
        
        // Chat elements
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.sendChatBtn = document.getElementById('sendChatBtn');
        this.clearChatBtn = document.getElementById('clearChatBtn');
        this.contextIndicator = document.getElementById('contextIndicator');
        

        
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
        
        // New action buttons
        if (this.copyNotesBtn) {
            this.copyNotesBtn.addEventListener('click', () => this.copyNotesToClipboard());
        }
        if (this.exportNotesBtn) {
            this.exportNotesBtn.addEventListener('click', () => this.exportNotesAsPDF());
        }
        

        
        // Mobile sidebar toggle
        if (this.toggleSidebarBtn) {
            this.toggleSidebarBtn.addEventListener('click', () => this.toggleSidebar());
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
            this.updateStatus('Processing Complete', 'Ready to generate meeting notes');
        } else {
            this.updateStatus('No Speech Detected', 'Please try recording again');
        }
    }
    
    handleSpeechResult(event) {
        let interimTranscript = '';
        let finalTranscript = '';
        
        // Smart speaker detection based on pause duration
        const currentTime = Date.now();
        const timeSinceLastSpeech = currentTime - this.lastSpeechTime;
        
        if (this.transcript.trim()) {
            if (timeSinceLastSpeech < this.sameSpeakerThreshold) {
                // Very short pause - definitely same speaker, no change needed
            } else if (timeSinceLastSpeech < this.speakerChangeThreshold) {
                // Medium pause - might be same speaker thinking
                // Keep same speaker if they were recently active
                if (this.lastActiveSpeaker !== null && this.lastActiveSpeaker === this.currentSpeaker) {
                    // Keep current speaker
                } else if (this.lastActiveSpeaker !== null) {
                    // Return to last active speaker (they're continuing)
                    this.currentSpeaker = this.lastActiveSpeaker;
                }
            } else {
                // Long pause - likely speaker change
                // Check if we should cycle to next speaker or return to a previous one
                const nextSpeaker = this.determineNextSpeaker();
                if (this.currentSpeaker !== nextSpeaker) {
                    this.lastActiveSpeaker = this.currentSpeaker; // Remember who was speaking
                    this.currentSpeaker = nextSpeaker;
                }
            }
        }
        
        this.lastSpeechTime = currentTime;
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            
            if (event.results[i].isFinal) {
                // Store transcript segment with speaker info
                this.transcriptSegments.push({
                    text: transcript,
                    speaker: this.currentSpeaker,
                    timestamp: new Date().toLocaleTimeString()
                });
                
                // Update speaker history for pattern detection
                if (!this.speakerHistory.includes(this.currentSpeaker)) {
                    this.speakerHistory.push(this.currentSpeaker);
                }
                
                // Store speech pattern for this speaker
                this.updateSpeakerPattern(this.currentSpeaker, transcript);
                
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
        
        // Update stats
        this.updateTranscriptStats();
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
            
            // Show transcript stats
            if (this.speakerCount) this.speakerCount.style.display = 'inline-flex';
            if (this.wordCount) this.wordCount.style.display = 'inline-flex';
        } else {
            this.recordBtn.style.display = 'inline-flex';
            this.stopBtn.style.display = 'none';
            this.recordingIndicator.classList.remove('recording');
        }
    }
    
    updateTranscriptStats() {
        if (!this.speakerCountText || !this.wordCountText) return;
        
        // Update speaker count
        const speakerSet = new Set(this.transcriptSegments.map(s => s.speaker));
        const speakerCount = speakerSet.size || 0;
        this.speakerCountText.textContent = `${speakerCount} speaker${speakerCount !== 1 ? 's' : ''}`;
        
        // Update word count
        const wordCount = this.transcript.trim().split(/\s+/).filter(word => word.length > 0).length;
        this.wordCountText.textContent = `${wordCount} word${wordCount !== 1 ? 's' : ''}`;
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
                <p class="text-muted small">Speech will appear here in real-time with speaker detection</p>
            </div>
        `;
        this.transcriptSegments = [];
        this.currentSpeaker = 1;
        this.lastActiveSpeaker = null;
        this.speakerHistory = [];
        this.speakerPatterns.clear();
        feather.replace();
    }
    
    determineNextSpeaker() {
        // If we have speaker history, try to detect patterns
        if (this.speakerHistory.length > 0) {
            // Check if this is a back-and-forth conversation pattern
            const recentSpeakers = this.speakerHistory.slice(-4);
            if (recentSpeakers.length >= 2) {
                // Look for alternating pattern
                const lastTwo = recentSpeakers.slice(-2);
                if (lastTwo[0] !== lastTwo[1]) {
                    // Alternating pattern detected, return to previous speaker
                    return lastTwo[0];
                }
            }
        }
        
        // Track speaker in history
        if (this.currentSpeaker && !this.speakerHistory.includes(this.currentSpeaker)) {
            this.speakerHistory.push(this.currentSpeaker);
        }
        
        // If we have 2 or fewer speakers so far, alternate between them
        if (this.speakerHistory.length === 2) {
            return this.speakerHistory.find(s => s !== this.currentSpeaker);
        }
        
        // Otherwise assign new speaker number
        return (this.currentSpeaker % 8) + 1;
    }
    
    updateSpeakerPattern(speakerId, text) {
        // Store speech patterns for future correlation
        if (!this.speakerPatterns.has(speakerId)) {
            this.speakerPatterns.set(speakerId, {
                textLength: [],
                pauseDurations: [],
                lastSpeechTime: Date.now()
            });
        }
        
        const pattern = this.speakerPatterns.get(speakerId);
        pattern.textLength.push(text.length);
        pattern.lastSpeechTime = Date.now();
        
        // Keep only recent patterns
        if (pattern.textLength.length > 10) {
            pattern.textLength.shift();
        }
    }
    
    updateSpeakerPattern(speakerId, text) {
        // Store speech patterns for each speaker (word count, average segment length)
        if (!this.speakerPatterns.has(speakerId)) {
            this.speakerPatterns.set(speakerId, {
                totalWords: 0,
                segments: 0,
                avgSegmentLength: 0
            });
        }
        
        const pattern = this.speakerPatterns.get(speakerId);
        const wordCount = text.split(/\s+/).filter(w => w.length > 0).length;
        pattern.totalWords += wordCount;
        pattern.segments += 1;
        pattern.avgSegmentLength = pattern.totalWords / pattern.segments;
    }
    
    updateTranscriptDisplay() {
        let html = '';
        
        // Display transcript segments with speaker labels and colors
        if (this.transcriptSegments.length > 0) {
            let currentSpeakerBlock = null;
            let blockHtml = '';
            
            this.transcriptSegments.forEach((segment, index) => {
                if (currentSpeakerBlock !== segment.speaker) {
                    // Close previous speaker block
                    if (blockHtml) {
                        html += blockHtml + '</div></div>';
                    }
                    
                    // Start new speaker block
                    currentSpeakerBlock = segment.speaker;
                    const color = this.speakerColors[(segment.speaker - 1) % this.speakerColors.length];
                    blockHtml = `
                        <div class="speaker-block" data-speaker="${segment.speaker}">
                            <div class="speaker-label" style="background-color: ${color}">
                                <span>Speaker ${segment.speaker}</span>
                                <small>${segment.timestamp}</small>
                            </div>
                            <div class="speaker-content">`;
                }
                
                blockHtml += `<span class="transcript-segment">${segment.text} </span>`;
            });
            
            // Close last speaker block
            if (blockHtml) {
                html += blockHtml + '</div></div>';
            }
        }
        
        // Add interim transcript with current speaker
        if (this.interimTranscript.trim()) {
            const color = this.speakerColors[(this.currentSpeaker - 1) % this.speakerColors.length];
            html += `
                <div class="speaker-block interim" data-speaker="${this.currentSpeaker}">
                    <div class="speaker-label" style="background-color: ${color}">
                        <span>Speaker ${this.currentSpeaker}</span>
                        <small>Speaking...</small>
                    </div>
                    <div class="speaker-content">
                        <span class="transcript-segment interim">${this.interimTranscript}</span>
                    </div>
                </div>`;
        }
        
        if (html) {
            this.transcriptElement.innerHTML = html;
            // Scroll to bottom
            this.transcriptElement.scrollTop = this.transcriptElement.scrollHeight;
            
            // Submit context to Gemini automatically
            if (this.chatInput && !this.chatInput.disabled) {
                this.updateGeminiContext();
            }
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
        this.meetingNotes.innerHTML = this.formatNotesForDisplay(notes);
        this.notesSection.style.display = 'block';
        
        // Extract and display action items summary
        this.displayActionItemsSummary(notes);
        
        // Enable action buttons
        this.downloadNotesBtn.disabled = false;
        if (this.copyNotesBtn) this.copyNotesBtn.disabled = false;
        if (this.exportNotesBtn) this.exportNotesBtn.disabled = false;
        
        // Scroll to notes section
        this.notesSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    formatNotesForDisplay(notes) {
        // Convert markdown-style notes to HTML with proper formatting
        let formatted = notes
            // Handle headers with emojis
            .replace(/## 🔥 (.*)/g, '<h2 class="priority-header">🔥 $1</h2>')
            .replace(/## 📋 (.*)/g, '<h2 class="action-header">📋 $1</h2>')
            .replace(/## 💬 (.*)/g, '<h2 class="discussion-header">💬 $1</h2>')
            .replace(/## ✅ (.*)/g, '<h2 class="decision-header">✅ $1</h2>')
            .replace(/## ⏭️ (.*)/g, '<h2 class="next-steps-header">⏭️ $1</h2>')
            .replace(/## 👥 (.*)/g, '<h2 class="participants-header">👥 $1</h2>')
            .replace(/## (.*)/g, '<h2>$1</h2>')
            
            // Handle numbered lists
            .split('\n').map(line => {
                if (/^\d+\.\s/.test(line)) {
                    return `<div class="numbered-item">${line}</div>`;
                } else if (/^•\s/.test(line)) {
                    return `<div class="bullet-item">${line.replace('• ', '')}</div>`;
                } else if (line.trim() === '') {
                    return '<div class="spacing"></div>';
                } else if (!line.startsWith('<h2')) {
                    return `<div class="content-line">${line}</div>`;
                }
                return line;
            }).join('')
            
            // Clean up spacing
            .replace(/<div class="spacing"><\/div><div class="spacing"><\/div>/g, '<div class="spacing"></div>');
            
        return formatted;
    }
    
    displayActionItemsSummary(notes) {
        const actionItemsSummary = document.getElementById('actionItemsSummary');
        const actionItemsList = document.getElementById('actionItemsList');
        
        if (!actionItemsSummary || !actionItemsList) return;
        
        // Extract priority actions and all action items from notes
        const priorityMatches = notes.match(/## 🔥 Priority Action Items\n([\s\S]*?)(?=\n##|$)/);
        const allActionsMatches = notes.match(/## 📋 Complete Action Items\n([\s\S]*?)(?=\n##|$)/);
        
        if (priorityMatches || allActionsMatches) {
            let html = '';
            
            // Add priority items
            if (priorityMatches) {
                const priorityItems = priorityMatches[1].trim().split('\n').filter(line => line.trim());
                priorityItems.forEach((item, index) => {
                    const cleanItem = item.replace(/^\d+\.\s*/, '');
                    html += `
                        <div class="action-item priority">
                            <span class="action-item-number">${index + 1}.</span>
                            ${cleanItem}
                        </div>
                    `;
                });
            }
            
            // Add regular items (if any)
            if (allActionsMatches && !priorityMatches) {
                const allItems = allActionsMatches[1].trim().split('\n').filter(line => line.trim());
                allItems.slice(0, 5).forEach((item, index) => { // Show top 5
                    const cleanItem = item.replace(/^\d+\.\s*/, '');
                    html += `
                        <div class="action-item">
                            <span class="action-item-number">${index + 1}.</span>
                            ${cleanItem}
                        </div>
                    `;
                });
            }
            
            if (html) {
                actionItemsList.innerHTML = html;
                actionItemsSummary.style.display = 'block';
            }
        }
    }
    
    async copyNotesToClipboard() {
        if (!this.currentNotes) {
            this.showError('No notes available to copy.');
            return;
        }
        
        try {
            await navigator.clipboard.writeText(this.currentNotes);
            
            // Show success feedback
            const originalIcon = this.copyNotesBtn.innerHTML;
            this.copyNotesBtn.innerHTML = '<i data-feather="check" class="icon-sm"></i>';
            this.copyNotesBtn.classList.add('btn-success');
            this.copyNotesBtn.classList.remove('btn-outline-secondary');
            
            setTimeout(() => {
                this.copyNotesBtn.innerHTML = originalIcon;
                this.copyNotesBtn.classList.remove('btn-success');
                this.copyNotesBtn.classList.add('btn-outline-secondary');
                feather.replace();
            }, 2000);
            
            feather.replace();
        } catch (error) {
            this.showError('Failed to copy notes to clipboard.');
            console.error('Copy error:', error);
        }
    }
    
    exportNotesAsPDF() {
        if (!this.currentNotes) {
            this.showError('No notes available to export.');
            return;
        }
        
        // Create a printable version
        const printWindow = window.open('', '_blank');
        const now = new Date();
        const timestamp = now.toLocaleString();
        
        printWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Meeting Notes - ${timestamp}</title>
                <style>
                    body {
                        font-family: 'Google Sans', Arial, sans-serif;
                        line-height: 1.6;
                        max-width: 800px;
                        margin: 40px auto;
                        padding: 20px;
                        color: #333;
                    }
                    h1 {
                        color: #1a73e8;
                        border-bottom: 3px solid #1a73e8;
                        padding-bottom: 10px;
                    }
                    h2 {
                        color: #34a853;
                        margin-top: 30px;
                        margin-bottom: 15px;
                        font-size: 18px;
                    }
                    ul, ol {
                        margin-bottom: 20px;
                    }
                    li {
                        margin-bottom: 8px;
                    }
                    .priority-section {
                        background: #fef7f7;
                        border-left: 4px solid #ea4335;
                        padding: 15px;
                        margin: 20px 0;
                    }
                    .header-info {
                        color: #666;
                        font-size: 14px;
                        margin-bottom: 30px;
                        border-bottom: 1px solid #eee;
                        padding-bottom: 15px;
                    }
                    @media print {
                        body { margin: 0; }
                        .no-print { display: none; }
                    }
                </style>
            </head>
            <body>
                <div class="header-info">
                    <strong>Meeting Notes</strong><br>
                    Generated: ${timestamp}<br>
                    Source: Meeting Transcription App
                </div>
                <div class="notes-content">
                    ${this.formatNotesForDisplay(this.currentNotes)}
                </div>
                <div class="no-print" style="margin-top: 40px; text-align: center;">
                    <button onclick="window.print()" style="background: #1a73e8; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">Print / Save as PDF</button>
                    <button onclick="window.close()" style="background: #666; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-left: 10px;">Close</button>
                </div>
            </body>
            </html>
        `);
        
        printWindow.document.close();
        
        // Auto-focus the print window
        setTimeout(() => {
            printWindow.focus();
        }, 500);
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
    
    setupChatListeners() {
        if (!this.chatInput || !this.sendChatBtn) return;
        
        // Enable chat when recording starts
        this.chatInput.disabled = false;
        this.sendChatBtn.disabled = false;
        
        // Send button click
        this.sendChatBtn.addEventListener('click', () => this.sendMessage());
        
        // Enter key in input
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Clear chat button
        if (this.clearChatBtn) {
            this.clearChatBtn.addEventListener('click', () => this.clearChat());
        }
        
        // Preset prompt buttons
        const presetButtons = document.querySelectorAll('.preset-btn');
        presetButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const prompt = e.currentTarget.dataset.prompt;
                if (prompt) {
                    this.sendPresetPrompt(prompt);
                }
            });
        });
    }
    
    async sendPresetPrompt(prompt) {
        // Check if we have a transcript
        if (!this.transcript || this.transcript.trim().length === 0) {
            this.showError('Please record some speech first before using preset prompts.');
            return;
        }
        
        // Add user message to chat
        this.addChatMessage(prompt, true);
        
        // Disable inputs while sending
        this.chatInput.disabled = true;
        this.sendChatBtn.disabled = true;
        
        try {
            // Get current transcript as context
            const context = this.getTranscriptText();
            
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: prompt,
                    context: context
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Chat request failed');
            }
            
            // Add AI response to chat
            this.addChatMessage(data.response, false);
            
        } catch (error) {
            console.error('Chat error:', error);
            this.addChatMessage('Sorry, I encountered an error. Please try again.', false);
        } finally {
            // Re-enable inputs
            this.chatInput.disabled = false;
            this.sendChatBtn.disabled = false;
        }
    }
    
    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        this.addChatMessage(message, true);
        
        // Clear input
        this.chatInput.value = '';
        
        // Disable inputs while sending
        this.chatInput.disabled = true;
        this.sendChatBtn.disabled = true;
        
        try {
            // Get current transcript as context
            const context = this.getTranscriptText();
            
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    context: context
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Chat request failed');
            }
            
            // Add AI response to chat
            this.addChatMessage(data.response, false);
            
        } catch (error) {
            console.error('Chat error:', error);
            this.addChatMessage('Sorry, I encountered an error. Please try again.', false);
        } finally {
            // Re-enable inputs
            this.chatInput.disabled = false;
            this.sendChatBtn.disabled = false;
            this.chatInput.focus();
        }
    }
    
    addChatMessage(message, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${isUser ? 'user-message' : 'ai-message'}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = `<i data-feather="${isUser ? 'user' : 'cpu'}" class="avatar-icon"></i>`;
        
        const content = document.createElement('div');
        content.className = 'message-content';
        
        // Split message into paragraphs
        const paragraphs = message.split('\n').filter(p => p.trim());
        paragraphs.forEach(para => {
            const p = document.createElement('p');
            p.textContent = para;
            content.appendChild(p);
        });
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        
        this.chatMessages.appendChild(messageDiv);
        feather.replace();
        
        // Scroll to bottom
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    clearChat() {
        // Keep only the initial AI message
        const firstMessage = this.chatMessages.querySelector('.chat-message');
        this.chatMessages.innerHTML = '';
        if (firstMessage) {
            this.chatMessages.appendChild(firstMessage);
        }
    }
    
    updateGeminiContext() {
        // Show context indicator briefly
        if (this.contextIndicator) {
            this.contextIndicator.style.display = 'block';
            setTimeout(() => {
                this.contextIndicator.style.display = 'none';
            }, 2000);
        }
    }
    
    getTranscriptText() {
        // Build full transcript text from segments
        let fullText = '';
        
        this.transcriptSegments.forEach(segment => {
            fullText += `Speaker ${segment.speaker}: ${segment.text}\n`;
        });
        
        // Add interim transcript if present
        if (this.interimTranscript.trim()) {
            fullText += `Speaker ${this.currentSpeaker}: ${this.interimTranscript}\n`;
        }
        
        return fullText.trim();
    }
    
    showError(message) {
        this.errorMessage.textContent = message;
        this.errorModal.show();
    }

}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new MeetingTranscription();
});
