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
    var videoModal = document.getElementById('curriculumVideoModal');
    var videoFrame = document.getElementById('curriculumVideoFrame');
    var videoList = document.getElementById('curriculumVideoList');
    var videoTitle = document.getElementById('curriculumVideoModalTitle');
    var videoNowPlaying = document.getElementById('curriculumVideoNowPlaying');
    var lastVideoTrigger = null;

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

    function safeVideoItems(library) {
        return library && Array.isArray(library.items) ? library.items.filter(function (item) {
            return item && /^[A-Za-z0-9_-]{11}$/.test(String(item.youtube_id || ''));
        }) : [];
    }

    function playVideo(item, selectedButton) {
        if (!videoFrame || !item) return;
        videoFrame.src = 'https://www.youtube-nocookie.com/embed/' + item.youtube_id + '?rel=0';
        videoFrame.title = item.title || 'فيديو شرح الدرس';
        if (videoNowPlaying) videoNowPlaying.textContent = item.title || 'فيديو شرح الدرس';
        if (videoList) {
            videoList.querySelectorAll('button').forEach(function (button) {
                button.classList.toggle('is-active', button === selectedButton);
                button.setAttribute('aria-pressed', button === selectedButton ? 'true' : 'false');
            });
        }
    }

    function closeVideoLibrary() {
        if (!videoModal || videoModal.hidden) return;
        videoModal.hidden = true;
        document.body.classList.remove('curriculum-video-open');
        if (videoFrame) videoFrame.removeAttribute('src');
        if (lastVideoTrigger) lastVideoTrigger.focus();
        lastVideoTrigger = null;
    }

    function openVideoLibrary(library, trigger) {
        var items = safeVideoItems(library);
        if (!videoModal || !videoList || !items.length) return;
        lastVideoTrigger = trigger || document.activeElement;
        videoTitle.textContent = (library.lesson || 'الدرس') + ' — ' + items.length + ' فيديو';
        videoList.textContent = '';
        var firstButton = null;
        items.forEach(function (item, index) {
            var button = make('button', 'curriculum-video-item');
            button.type = 'button';
            button.setAttribute('aria-pressed', 'false');
            var image = make('img');
            image.src = 'https://i.ytimg.com/vi/' + item.youtube_id + '/mqdefault.jpg';
            image.alt = '';
            image.loading = 'lazy';
            button.appendChild(image);
            var details = make('span');
            details.appendChild(make('strong', '', item.title || 'فيديو شرح الدرس'));
            details.appendChild(make('small', '', 'تشغيل داخل المنصة'));
            button.appendChild(details);
            button.addEventListener('click', function () { playVideo(item, button); });
            videoList.appendChild(button);
            if (index === 0) firstButton = button;
        });
        videoModal.hidden = false;
        document.body.classList.add('curriculum-video-open');
        playVideo(items[0], firstButton);
        var dialog = videoModal.querySelector('.curriculum-video-dialog');
        if (dialog) dialog.focus();
    }

    function addResponseTools(bubble, content, video) {
        var supportsSpeech = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
        var videoItems = safeVideoItems(video);
        if (!supportsSpeech && !videoItems.length) return;
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
        if (videoItems.length) {
            var videoButton = make('button', 'chat-video');
            videoButton.type = 'button';
            videoButton.innerHTML = '<i class="bi bi-youtube"></i><span>' +
                'فيديوهات الدرس (' + videoItems.length + ')</span>';
            videoButton.addEventListener('click', function () { openVideoLibrary(video, videoButton); });
            tools.appendChild(videoButton);
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

    var initialVideoLibrary = null;
    var videoData = document.getElementById('curriculumVideoData');
    if (videoData) {
        try { initialVideoLibrary = JSON.parse(videoData.textContent); } catch (ignore) { initialVideoLibrary = null; }
    }
    root.querySelectorAll('[data-open-video-library]').forEach(function (button) {
        button.addEventListener('click', function () { openVideoLibrary(initialVideoLibrary, button); });
    });
    if (videoModal) {
        videoModal.querySelectorAll('[data-video-close]').forEach(function (button) {
            button.addEventListener('click', closeVideoLibrary);
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && !videoModal.hidden) closeVideoLibrary();
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
