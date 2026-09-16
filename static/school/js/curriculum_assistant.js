(function () {
    'use strict';

    var root = document.getElementById('curriculumAssistant');
    if (!root) return;
    var form = document.getElementById('curriculumQuestionForm');
    var stream = document.getElementById('curriculumMessages');
    var question = document.getElementById('curriculumQuestion');
    var conversationId = null;
    var activeUtterance = null;
    var activeSpeechButton = null;

    function csrfToken() {
        var field = form && form.querySelector('input[name="csrfmiddlewaretoken"]');
        return field ? field.value : '';
    }

    function make(tag, className, text) {
        var element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }

    function scrollToEnd() {
        if (stream) stream.scrollTop = stream.scrollHeight;
    }

    function resetSpeechButton() {
        if (activeSpeechButton) {
            activeSpeechButton.classList.remove('is-speaking');
            activeSpeechButton.setAttribute('aria-pressed', 'false');
            activeSpeechButton.innerHTML = '<i class="bi bi-volume-up-fill"></i><span>استمع للشرح</span>';
        }
        activeSpeechButton = null;
        activeUtterance = null;
    }

    function stopSpeech() {
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        resetSpeechButton();
    }

    function addResponseTools(bubble, content, video) {
        var supportsSpeech = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
        if (!supportsSpeech && !video) return;
        var tools = make('div', 'chat-tools');
        if (supportsSpeech) {
            var listen = make('button', 'chat-listen');
            listen.type = 'button';
            listen.setAttribute('aria-pressed', 'false');
            listen.innerHTML = '<i class="bi bi-volume-up-fill"></i><span>استمع للشرح</span>';
            listen.addEventListener('click', function () {
                if (activeSpeechButton === listen && window.speechSynthesis.speaking) {
                    stopSpeech();
                    return;
                }
                stopSpeech();
                var utterance = new SpeechSynthesisUtterance(
                    String(content || '').replace(/[🌟👣✏️✅]/g, '').trim()
                );
                utterance.lang = 'ar-SA';
                utterance.rate = 0.9;
                var voices = window.speechSynthesis.getVoices();
                var arabicVoice = voices.find(function (voice) {
                    return String(voice.lang || '').toLowerCase().indexOf('ar') === 0;
                });
                if (arabicVoice) utterance.voice = arabicVoice;
                activeUtterance = utterance;
                activeSpeechButton = listen;
                listen.classList.add('is-speaking');
                listen.setAttribute('aria-pressed', 'true');
                listen.innerHTML = '<i class="bi bi-stop-circle-fill"></i><span>إيقاف الصوت</span>';
                utterance.onend = function () {
                    if (activeUtterance === utterance) resetSpeechButton();
                };
                utterance.onerror = function () {
                    if (activeUtterance === utterance) resetSpeechButton();
                };
                window.speechSynthesis.speak(utterance);
            });
            tools.appendChild(listen);
        }
        if (video && video.url) {
            var videoLink = make('a', 'chat-video', video.label || 'ابحث عن فيديو شرح');
            videoLink.href = video.url;
            videoLink.target = '_blank';
            videoLink.rel = 'noopener noreferrer';
            if (video.note) videoLink.title = video.note;
            var icon = make('i', 'bi bi-youtube');
            videoLink.insertBefore(icon, videoLink.firstChild);
            tools.appendChild(videoLink);
        }
        bubble.appendChild(tools);
    }

    function addMessage(role, content, citations, suggestions, video) {
        var row = make('div', 'chat-message chat-message--' + role);
        var avatar = make('div', 'chat-avatar');
        avatar.innerHTML = role === 'assistant' ? '<i class="bi bi-stars"></i>' : '<i class="bi bi-person-fill"></i>';
        var bubble = make('div', 'chat-bubble');
        bubble.appendChild(make('div', 'chat-content', content));
        if (citations && citations.length) {
            var references = make('div', 'chat-citations');
            references.appendChild(make('strong', '', 'اعتمدت على:'));
            citations.forEach(function (citation) {
                var link = make('a', '', citation.label);
                link.href = citation.url;
                link.target = '_blank';
                link.rel = 'noopener';
                references.appendChild(link);
            });
            bubble.appendChild(references);
        }
        if (role === 'assistant' && suggestions && suggestions.length) {
            var followups = make('div', 'chat-followups');
            suggestions.forEach(function (item) {
                var button = make('button', '', item);
                button.type = 'button';
                button.addEventListener('click', function () {
                    question.value = item;
                    question.focus();
                });
                followups.appendChild(button);
            });
            bubble.appendChild(followups);
        }
        if (role === 'assistant') addResponseTools(bubble, content, video);
        row.appendChild(avatar);
        row.appendChild(bubble);
        stream.appendChild(row);
        scrollToEnd();
        return row;
    }

    function setBusy(busy) {
        if (!form) return;
        var button = form.querySelector('button[type="submit"]');
        question.disabled = busy;
        button.disabled = busy;
        button.innerHTML = busy
            ? '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>يفكر…</span>'
            : '<i class="bi bi-send-fill"></i><span>إرسال</span>';
    }

    async function parseResponse(response) {
        var payload;
        try { payload = await response.json(); } catch (ignore) { payload = {}; }
        if (!response.ok || payload.ok === false) {
            var error = new Error(payload.error || 'انقطع اتصال الخادم أثناء إعداد الإجابة. أعد المحاولة بعد تحديث الصفحة.');
            error.payload = payload;
            throw error;
        }
        return payload;
    }

    if (form) {
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            var value = question.value.trim();
            if (value.length < 2) return;
            var sourceId = form.querySelector('[name="source_id"]').value;
            var lessonId = form.querySelector('[name="lesson_id"]').value;
            addMessage('user', value, [], []);
            question.value = '';
            setBusy(true);
            try {
                var response = await fetch(root.dataset.askUrl, {
                    method: 'POST',
                    credentials: 'same-origin',
                    cache: 'no-store',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken(),
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        question: value,
                        source_id: sourceId,
                        lesson_id: lessonId || null,
                        conversation_id: conversationId
                    })
                });
                var payload = await parseResponse(response);
                conversationId = payload.conversation_id || conversationId;
                addMessage('assistant', payload.answer, payload.citations || [], payload.suggestions || [], payload.video || null);
                var remaining = root.querySelector('[data-remaining]');
                if (remaining && payload.remaining !== undefined) remaining.textContent = payload.remaining;
            } catch (error) {
                if (error.payload && error.payload.conversation_id) {
                    conversationId = error.payload.conversation_id;
                }
                addMessage('error', error.message, [], []);
            } finally {
                setBusy(false);
                question.focus();
            }
        });
    }

    root.querySelectorAll('[data-prompt]').forEach(function (button) {
        button.addEventListener('click', function () {
            question.value = button.dataset.prompt;
            question.focus();
        });
    });

    var lessonSelect = document.getElementById('lessonSelect');
    if (lessonSelect) {
        lessonSelect.addEventListener('change', function () {
            var params = new URLSearchParams();
            params.set('source', lessonSelect.dataset.source);
            if (lessonSelect.value) params.set('lesson', lessonSelect.value);
            window.location.href = window.location.pathname + '?' + params.toString();
        });
    }

    async function loadConversation(id) {
        if (!id || !stream) return;
        var url = root.dataset.conversationTemplate.replace('999999', id);
        try {
            var response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
            var payload = await parseResponse(response);
            stream.innerHTML = '';
            payload.conversation.messages.forEach(function (message) {
                addMessage(message.role, message.content, message.citations || [], [], message.video || null);
            });
            conversationId = payload.conversation.id;
        } catch (error) {
            addMessage('error', error.message, [], []);
        }
    }

    loadConversation(root.dataset.initialConversation);
})();
