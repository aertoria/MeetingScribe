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

// Deepgram Diarization Handler
class DeepgramDiarization {
    constructor(meetingApp) {
        this.meetingApp = meetingApp;
        this.ws = null;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.audioStream = null;
        this.processorNode = null;
        this.isConnected = false;
        this.transcriptSegments = [];
        this.speakers = new Map();
        this.speakerColors = [
            '#1a73e8', '#34a853', '#ea4335', '#fbbc04',
            '#673ab7', '#ff6f00', '#00796b', '#5d4037'
        ];
        
        // Speaker identification tracking
        this.speakerIdentities = new Map();
        this.speakerBuffer = new Map(); // Buffer recent text for each speaker
        this.identificationQueue = [];
        this.isIdentifying = false;
        this.lastIdentificationTime = new Map();
        this.identificationInterval = 10000; // Re-identify every 10 seconds
        
        // Speaker transition tracking
        this.currentActiveSpeaker = null;
        this.lastTranscriptTime = Date.now();
    }
    
    async start() {
        try {
            // Get microphone access
            this.audioStream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                } 
            });
            
            // Set up audio context for processing
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });
            
            const source = this.audioContext.createMediaStreamSource(this.audioStream);
            this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);
            
            // Connect WebSocket
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/transcribe`;
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('Connected to Deepgram diarization service');
                this.isConnected = true;
                this.meetingApp.updateStatus('Connecting to AI', 'Initializing speaker detection...', 'status-recording');
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.meetingApp.showError('WebSocket connection error. Please refresh the page and try again.');
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket connection closed');
                this.isConnected = false;
                this.stop();
            };
            
            // Process audio and send to WebSocket
            this.processorNode.onaudioprocess = (e) => {
                if (!this.isConnected || this.ws.readyState !== WebSocket.OPEN) return;
                
                const inputData = e.inputBuffer.getChannelData(0);
                const outputData = new Int16Array(inputData.length);
                
                // Convert float32 to int16
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    outputData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                
                // Send audio data as binary
                this.ws.send(outputData.buffer);
            };
            
            // Connect audio nodes
            source.connect(this.processorNode);
            this.processorNode.connect(this.audioContext.destination);
            
            return true;
        } catch (error) {
            console.error('Error starting Deepgram diarization:', error);
            
            // Provide specific error messages based on error type
            let errorMessage = 'Failed to start diarization: ';
            if (error.name === 'NotAllowedError') {
                errorMessage = 'Microphone access denied. Please allow microphone access and try again.';
            } else if (error.name === 'NotFoundError') {
                errorMessage = 'No microphone found. Please check your microphone and try again.';
            } else if (error.name === 'NotSupportedError') {
                errorMessage = 'Your browser does not support audio recording. Please use Chrome, Firefox, or Safari.';
            } else {
                errorMessage += error.message;
            }
            
            this.meetingApp.showError(errorMessage);
            return false;
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'ready':
                console.log('Diarization service ready');
                this.meetingApp.updateStatus('Recording Active', 'AI speaker detection ready', 'status-recording');
                break;
                
            case 'transcript':
                this.handleTranscript(data.data);
                break;
                
            case 'speaker_change':
                this.handleSpeakerChange(data.data);
                break;
                
            case 'error':
                console.error('Diarization error:', data.message);
                this.meetingApp.showError('Diarization error: ' + data.message);
                this.isConnected = false;
                // Stop recording if there's an error
                if (this.meetingApp.isRecording) {
                    this.meetingApp.stopRecording();
                }
                break;
                
            case 'summary':
                console.log('Session summary:', data.data);
                break;
        }
    }
    
    handleTranscript(transcriptData) {
        const { speaker, speaker_id, text, time, confidence } = transcriptData;
        
        // Track speaker transitions with improved logic
        const previousSpeaker = this.currentActiveSpeaker;
        this.currentActiveSpeaker = speaker_id;
        
        // Track speaker with confidence tracking
        if (!this.speakers.has(speaker_id)) {
            const color = this.speakerColors[speaker_id % this.speakerColors.length];
            this.speakers.set(speaker_id, { 
                name: speaker, 
                color: color,
                utteranceCount: 0,
                lastActiveTime: Date.now(),
                totalConfidence: confidence || 0.8,
                avgConfidence: confidence || 0.8,
                segments: []
            });
            
            // Initialize speaker identity
            this.speakerIdentities.set(speaker_id, 'Identifying...');
            this.showSpeakerPanel();
        }
        
        // Update speaker activity with confidence tracking
        const speakerInfo = this.speakers.get(speaker_id);
        speakerInfo.utteranceCount++;
        speakerInfo.lastActiveTime = Date.now();
        
        // Update confidence tracking
        if (confidence) {
            speakerInfo.totalConfidence += confidence;
            speakerInfo.avgConfidence = speakerInfo.totalConfidence / speakerInfo.utteranceCount;
        }
        
        // Store segment info for consistency analysis
        speakerInfo.segments.push({
            text: text,
            confidence: confidence || 0.8,
            timestamp: Date.now(),
            wordCount: text.split(' ').length
        });
        
        // Keep only last 10 segments per speaker for analysis
        if (speakerInfo.segments.length > 10) {
            speakerInfo.segments.shift();
        }
        
        // Buffer speaker text for identification
        if (!this.speakerBuffer.has(speaker_id)) {
            this.speakerBuffer.set(speaker_id, []);
        }
        this.speakerBuffer.get(speaker_id).push(text);
        
        // Keep only last 5 utterances per speaker
        const buffer = this.speakerBuffer.get(speaker_id);
        if (buffer.length > 5) {
            buffer.shift();
        }
        
        // Check if we should identify this speaker (more frequent for low confidence)
        const lastIdentTime = this.lastIdentificationTime.get(speaker_id) || 0;
        const now = Date.now();
        
        // Identify more frequently for new speakers or low confidence
        const baseInterval = speakerInfo.utteranceCount < 3 ? 4000 : this.identificationInterval;
        const confidenceMultiplier = speakerInfo.avgConfidence < 0.7 ? 0.6 : 1.0;
        const identInterval = baseInterval * confidenceMultiplier;
        
        if (now - lastIdentTime > identInterval && buffer.length >= 2) {
            this.queueSpeakerIdentification(speaker_id);
        }
        
        // Advanced segment merging with confidence consideration
        const lastSegment = this.transcriptSegments[this.transcriptSegments.length - 1];
        const wordCount = text.split(' ').length;
        const timeSinceLastSegment = now - this.lastTranscriptTime;
        
        // Improved merging logic
        const shouldMerge = lastSegment && 
                           lastSegment.speaker_id === speaker_id && 
                           (wordCount < 4 || timeSinceLastSegment < 1500) &&
                           timeSinceLastSegment < 3000 &&
                           (confidence || 0.8) > 0.6;  // Don't merge low confidence segments
        
        if (shouldMerge) {
            // Merge with previous segment
            lastSegment.text += ' ' + text;
            lastSegment.merged = true;
            lastSegment.confidence = Math.max(lastSegment.confidence || 0.8, confidence || 0.8);
        } else {
            // Store as new segment with enhanced metadata
            this.transcriptSegments.push({
                speaker: speaker,
                speaker_id: speaker_id,
                text: text,
                time: time,
                confidence: confidence || 0.8,
                wordCount: wordCount,
                transition: previousSpeaker !== null && previousSpeaker !== speaker_id,
                transitionConfidence: this.calculateTransitionConfidence(previousSpeaker, speaker_id)
            });
        }
        
        this.lastTranscriptTime = now;
        
        // Update display with confidence information
        this.updateTranscriptDisplay();
        this.updateSpeakerProfiles(speaker_id, true); // Mark as active
        
        // Update full transcript text for the meeting app
        this.meetingApp.transcript = this.getFullTranscript();
        
        // Update stats
        this.updateStats();
    }
    
    calculateTransitionConfidence(prevSpeaker, currentSpeaker) {
        if (prevSpeaker === null || prevSpeaker === currentSpeaker) {
            return 1.0; // No transition or same speaker
        }
        
        // Calculate confidence based on speaker history and patterns
        const prevSpeakerInfo = this.speakers.get(prevSpeaker);
        const currentSpeakerInfo = this.speakers.get(currentSpeaker);
        
        if (!prevSpeakerInfo || !currentSpeakerInfo) {
            return 0.5; // Unknown speakers
        }
        
        // Higher confidence for speakers with good track record
        const avgConfidence = (prevSpeakerInfo.avgConfidence + currentSpeakerInfo.avgConfidence) / 2;
        
        // Consider timing patterns - frequent switchers get lower confidence
        const recentSwitches = this.transcriptSegments.slice(-5).filter(s => s.transition).length;
        const switchPenalty = Math.max(0, (recentSwitches - 1) * 0.1);
        
        return Math.max(0.3, avgConfidence - switchPenalty);
    }
    
    showSpeakerPanel() {
        const panel = document.getElementById('speakerPanel');
        const divider = document.getElementById('speakerDivider');
        if (panel) panel.style.display = 'block';
        if (divider) divider.style.display = 'block';
    }
    
    queueSpeakerIdentification(speakerId) {
        // Add to queue if not already there
        if (!this.identificationQueue.includes(speakerId)) {
            this.identificationQueue.push(speakerId);
        }
        
        // Process queue if not already processing
        if (!this.isIdentifying) {
            this.processIdentificationQueue();
        }
    }
    
    async processIdentificationQueue() {
        if (this.identificationQueue.length === 0) {
            this.isIdentifying = false;
            return;
        }
        
        this.isIdentifying = true;
        const speakerId = this.identificationQueue.shift();
        
        try {
            await this.identifySpeaker(speakerId);
        } catch (error) {
            console.error('Error identifying speaker:', error);
        }
        
        // Continue processing queue
        setTimeout(() => this.processIdentificationQueue(), 500);
    }
    
    async identifySpeaker(speakerId) {
        const buffer = this.speakerBuffer.get(speakerId);
        if (!buffer || buffer.length === 0) return;
        
        // Combine recent utterances
        const recentText = buffer.slice(-3).join(' ');
        
        try {
            const response = await fetch('/identify_speaker', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    speaker_id: speakerId,
                    text: recentText
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.speakerIdentities.set(speakerId, data.identity);
                this.lastIdentificationTime.set(speakerId, Date.now());
                this.updateSpeakerProfiles(speakerId);
            }
        } catch (error) {
            console.error('Failed to identify speaker:', error);
        }
    }
    
    updateSpeakerProfiles(activeSpeakerId = null, isSpeaking = false) {
        const profilesContainer = document.getElementById('speakerProfiles');
        if (!profilesContainer) return;
        
        let html = '';
        
        this.speakers.forEach((speaker, speakerId) => {
            const identity = this.speakerIdentities.get(speakerId) || 'Identifying...';
            const isActive = speakerId === activeSpeakerId;
            const color = speaker.color;
            
            // Get confidence information
            const avgConfidence = speaker.avgConfidence || 0.8;
            const confidencePercent = Math.round(avgConfidence * 100);
            const confidenceColor = avgConfidence > 0.8 ? '#4caf50' : 
                                   avgConfidence > 0.6 ? '#ff9800' : '#f44336';
            
            html += `
                <div class="speaker-profile ${isActive && isSpeaking ? 'active' : ''}" 
                     style="border-left-color: ${color};">
                    <div class="speaker-avatar" style="background: ${color};">
                        ${speakerId + 1}
                    </div>
                    <div class="speaker-info">
                        <div class="speaker-label">${speaker.name}</div>
                        <div class="speaker-identity ${identity === 'Identifying...' ? 'unknown' : ''}">
                            ${identity}
                        </div>
                        <div class="speaker-confidence" style="font-size: 0.75em; color: ${confidenceColor}; margin-top: 2px;">
                            <span title="Detection confidence">🎯 ${confidencePercent}%</span>
                            <span style="margin-left: 8px; color: #666;" title="Total segments">${speaker.utteranceCount || 0}</span>
                        </div>
                        <div class="speaker-status ${isActive && isSpeaking ? 'speaking' : ''}">
                            <span class="status-dot"></span>
                            <span>${isActive && isSpeaking ? 'Speaking' : 'Listening'}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        
        profilesContainer.innerHTML = html;
        
        // Update feather icons if needed
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
        
        // Clear speaking status after a delay
        if (isSpeaking) {
            setTimeout(() => {
                this.updateSpeakerProfiles();
            }, 2000);
        }
    }
    
    handleSpeakerChange(data) {
        console.log(`New speaker detected: ${data.speaker_name}`);
        // Could show a notification or update UI
    }
    
    updateTranscriptDisplay() {
        const transcriptElement = this.meetingApp.transcriptElement;
        let html = '';
        
        this.transcriptSegments.forEach((segment, index) => {
            const speaker = this.speakers.get(segment.speaker_id);
            const color = speaker ? speaker.color : '#666';
            
            // Add visual separator for speaker transitions
            const transitionClass = segment.transition ? 'speaker-transition' : '';
            const mergedClass = segment.merged ? 'merged-segment' : '';
            
            // Confidence indicators
            const confidence = segment.confidence || 0.8;
            const confidenceClass = confidence > 0.8 ? 'high-confidence' : 
                                  confidence > 0.6 ? 'med-confidence' : 'low-confidence';
            
            // Transition confidence indicator
            const transitionConf = segment.transitionConfidence || 1.0;
            const transitionWarning = segment.transition && transitionConf < 0.7;
            
            html += `
                <div class="transcript-segment ${transitionClass} ${mergedClass} ${confidenceClass}" 
                     style="margin-bottom: ${segment.transition ? '12px' : '6px'}; 
                            padding-top: ${segment.transition ? '8px' : '4px'};
                            ${confidence < 0.7 ? 'border-left: 2px solid #ff9800;' : ''}">
                    <div class="segment-header">
                        <span style="color: ${color}; font-weight: bold;">${segment.speaker}</span>
                        <span style="color: #999; font-size: 0.85em; margin-left: 10px;">${segment.time}</span>
                        ${segment.transition ? 
                          `<span style="color: ${transitionWarning ? '#ff5722' : '#ea4335'}; font-size: 0.75em; margin-left: 8px;">
                            • ${transitionWarning ? 'uncertain switch' : 'switched'}
                           </span>` : ''}
                        ${confidence < 0.7 ? 
                          `<span style="color: #ff9800; font-size: 0.7em; margin-left: 8px;" title="Low confidence: ${Math.round(confidence * 100)}%">
                            ⚠ ${Math.round(confidence * 100)}%
                           </span>` : ''}
                    </div>
                    <div class="segment-text" style="margin-top: 4px; line-height: 1.5;">${segment.text}</div>
                </div>
            `;
        });
        
        transcriptElement.innerHTML = html || '<p class="text-muted">Waiting for speech...</p>';
        
        // Smooth scroll to bottom
        if (transcriptElement.scrollHeight - transcriptElement.scrollTop < transcriptElement.clientHeight + 100) {
            transcriptElement.scrollTop = transcriptElement.scrollHeight;
        }
    }
    
    updateStats() {
        // Update speaker count
        if (this.meetingApp.speakerCountText) {
            this.meetingApp.speakerCountText.textContent = this.speakers.size;
        }
        
        // Update word count
        if (this.meetingApp.wordCountText) {
            const wordCount = this.transcriptSegments.reduce((count, segment) => {
                return count + segment.text.split(/\s+/).length;
            }, 0);
            this.meetingApp.wordCountText.textContent = wordCount;
        }
    }
    
    getFullTranscript() {
        return this.transcriptSegments
            .map(segment => `${segment.speaker}: ${segment.text}`)
            .join('\n');
    }
    
    async stop() {
        // Send stop command if connected
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ command: 'stop' }));
            this.ws.close();
        }
        
        // Stop audio processing
        if (this.processorNode) {
            this.processorNode.disconnect();
            this.processorNode = null;
        }
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
            this.audioStream = null;
        }
        
        this.isConnected = false;
        
        // Hide speaker panel if no speakers detected
        if (this.speakers.size === 0) {
            const panel = document.getElementById('speakerPanel');
            const divider = document.getElementById('speakerDivider');
            if (panel) panel.style.display = 'none';
            if (divider) divider.style.display = 'none';
        }
    }
    
    async getSummary() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ command: 'get_summary' }));
        }
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    const app = new MeetingTranscription();
    
    // Add toggle for diarization mode
    const useDiarization = true; // Set to true to use Deepgram diarization
    
    if (useDiarization) {
        // Override recording methods to use Deepgram diarization
        const diarization = new DeepgramDiarization(app);
        
        app.startRecording = async function() {
            try {
                this.isRecording = true;
                this.transcript = '';
                this.updateRecordingUI(true);
                this.clearTranscript();
                
                const success = await diarization.start();
                if (!success) {
                    this.stopRecording();
                }
            } catch (error) {
                this.showError('Failed to start recording: ' + error.message);
                this.stopRecording();
            }
        };
        
        app.stopRecording = async function() {
            this.isRecording = false;
            this.updateRecordingUI(false);
            
            await diarization.stop();
            
            if (this.transcript.trim()) {
                this.generateNotesBtn.disabled = false;
                this.updateStatus('Processing Complete', 'Ready to generate meeting notes');
            } else {
                this.updateStatus('No Speech Detected', 'Please try recording again');
            }
        };
    }
});
