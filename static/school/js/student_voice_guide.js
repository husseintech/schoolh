(function () {
  'use strict';

  function localDayKey() {
    var now = new Date();
    return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
  }

  function readStorage(key) {
    try { return window.localStorage.getItem(key); } catch (error) { return null; }
  }

  function writeStorage(key, value) {
    try { window.localStorage.setItem(key, value); } catch (error) { /* يعمل المساعد دون التخزين المحلي. */ }
  }

  function parseJsonNode(id, fallback) {
    var node = document.getElementById(id);
    if (!node) return fallback;
    try { return JSON.parse(node.textContent || ''); } catch (error) { return fallback; }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var guide = document.getElementById('studentVoiceGuide');
    var config = parseJsonNode('studentAssistantConfig', {});
    var tasks = parseJsonNode('studentGuideTasks', []);
    if (!guide || !config.enabled) return;
    if (!Array.isArray(tasks)) tasks = [];

    var studentKey = guide.dataset.studentKey || 'student';
    var dismissedKey = 'schoolh_student_guide_dismissed_' + studentKey;
    var mutedKey = 'schoolh_student_guide_muted_' + studentKey;
    var launcher = document.getElementById('studentGuideLauncher');
    var mascot = document.getElementById('studentGuideMascot');
    var card = guide.querySelector('.student-guide__card');
    var welcome = document.getElementById('studentAssistantWelcome');
    var workspace = document.getElementById('studentAssistantWorkspace');
    var welcomeStart = document.getElementById('studentAssistantWelcomeStart');
    var shortName = document.getElementById('studentAssistantShortName');
    var schoolName = document.getElementById('studentAssistantSchoolName');
    var welcomeMessage = document.getElementById('studentAssistantWelcomeMessage');
    var title = document.getElementById('studentGuideTitle');
    var message = document.getElementById('studentGuideMessage');
    var status = document.getElementById('studentGuideStatus');
    var action = document.getElementById('studentGuideAction');
    var actionText = action.querySelector('span');
    var listen = document.getElementById('studentGuideListen');
    var listenText = listen.querySelector('span');
    var mute = document.getElementById('studentGuideMute');
    var close = document.getElementById('studentGuideClose');
    var dismissToday = document.getElementById('studentGuideDismissToday');
    var pager = document.getElementById('studentGuidePager');
    var previous = document.getElementById('studentGuidePrevious');
    var next = document.getElementById('studentGuideNext');
    var counter = document.getElementById('studentGuideCounter');
    var taskBadge = document.getElementById('studentGuideTaskBadge');
    var tabs = Array.prototype.slice.call(guide.querySelectorAll('[data-guide-tab]'));
    var panels = Array.prototype.slice.call(guide.querySelectorAll('[data-guide-panel]'));
    var messages = document.getElementById('studentAssistantMessages');
    var suggestions = document.getElementById('studentAssistantSuggestions');
    var usage = document.getElementById('studentAssistantUsage');
    var form = document.getElementById('studentAssistantForm');
    var input = document.getElementById('studentAssistantInput');
    var send = document.getElementById('studentAssistantSend');
    var mic = document.getElementById('studentAssistantMic');
    var state = document.getElementById('studentAssistantState');
    var currentIndex = 0;
    var hasListened = false;
    var lastSpokenText = '';
    var speechSupported = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
    var isMuted = readStorage(mutedKey) === '1';
    var isSending = false;

    shortName.textContent = config.short_name || 'عزيزي الطالب';
    schoolName.textContent = config.school_name || 'مدرستك';
    welcomeMessage.textContent = config.welcome_message || '';
    usage.textContent = config.educational_ai_enabled === false
      ? 'المساعدة التعليمية الذكية متوقفة حاليًا'
      : 'متاح حتى ' + (config.daily_ai_limit || 10) + ' أسئلة تعليمية ذكية يوميًا';
    taskBadge.textContent = tasks.length;
    taskBadge.hidden = !tasks.length;

    function cancelSpeech() {
      if (speechSupported) window.speechSynthesis.cancel();
    }

    function chooseArabicVoice() {
      if (!speechSupported) return null;
      var voices = window.speechSynthesis.getVoices();
      return voices.find(function (voice) { return /^ar[-_](PS|SA)/i.test(voice.lang); }) ||
        voices.find(function (voice) { return /^ar/i.test(voice.lang); }) || null;
    }

    function speak(text) {
      if (!speechSupported || isMuted || !text) return;
      cancelSpeech();
      lastSpokenText = text;
      var utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'ar-SA';
      utterance.rate = 0.9;
      utterance.pitch = 1.06;
      var voice = chooseArabicVoice();
      if (voice) utterance.voice = voice;
      utterance.onstart = function () {
        listen.classList.add('active');
        listenText.textContent = 'يتم التشغيل';
      };
      utterance.onend = utterance.onerror = function () {
        listen.classList.remove('active');
        hasListened = true;
        updateMuteButton();
      };
      window.speechSynthesis.speak(utterance);
    }

    function updateMuteButton() {
      var icon = mute.querySelector('i');
      icon.className = isMuted ? 'bi bi-volume-mute-fill' : 'bi bi-volume-up-fill';
      mute.setAttribute('aria-label', isMuted ? 'تشغيل الصوت' : 'كتم الصوت');
      mute.title = isMuted ? 'تشغيل الصوت' : 'كتم الصوت';
      listen.disabled = isMuted || !speechSupported;
      if (!speechSupported) {
        listen.title = 'الصوت غير مدعوم في هذا المتصفح';
        listenText.textContent = 'الصوت غير مدعوم';
      } else {
        listen.title = '';
        listenText.textContent = hasListened ? 'إعادة الصوت' : 'استمع';
      }
    }

    function renderTask(index) {
      if (!tasks.length) {
        status.className = 'student-guide__status tone-success';
        status.textContent = 'كل شيء مكتمل';
        title.textContent = 'أحسنت!';
        message.textContent = 'لا توجد مهام جديدة تحتاج متابعتك الآن. يمكنك الانتقال إلى تبويب اسألني.';
        action.hidden = true;
        pager.hidden = true;
        listen.hidden = true;
        return;
      }
      currentIndex = (index + tasks.length) % tasks.length;
      var task = tasks[currentIndex];
      cancelSpeech();
      status.className = 'student-guide__status tone-' + (task.tone || 'info');
      status.textContent = task.key === 'student_file' ? 'للمتابعة' : 'مهمة مطلوبة';
      title.textContent = task.title || '';
      message.textContent = task.message || '';
      action.hidden = !task.url;
      action.href = task.url || '#';
      actionText.textContent = task.action_label || 'فتح';
      counter.textContent = (currentIndex + 1) + ' من ' + tasks.length;
      pager.hidden = tasks.length < 2;
      listen.hidden = false;
      hasListened = false;
      lastSpokenText = (task.title || '') + '. ' + (task.message || '');
      updateMuteButton();
    }

    function switchTab(name) {
      welcome.hidden = true;
      workspace.hidden = false;
      tabs.forEach(function (tab) {
        var active = tab.dataset.guideTab === name;
        tab.classList.toggle('is-active', active);
        tab.setAttribute('aria-selected', String(active));
      });
      panels.forEach(function (panel) { panel.classList.toggle('is-active', panel.dataset.guidePanel === name); });
      card.classList.toggle('is-chatting', name === 'chat');
      if (name === 'chat') window.setTimeout(function () { input.focus(); }, 80);
    }

    function showWelcome() {
      workspace.hidden = true;
      welcome.hidden = false;
      card.classList.add('is-welcoming');
      lastSpokenText = 'مرحبًا ' + (config.short_name || 'عزيزي الطالب') + '. نرحب بك في ' + (config.school_name || 'مدرستك') + '. ' + (config.welcome_message || '');
      window.setTimeout(function () { speak(lastSpokenText); }, 450);
    }

    function openGuide(withWelcome) {
      launcher.hidden = true;
      guide.setAttribute('aria-hidden', 'false');
      if (withWelcome) showWelcome();
      else {
        card.classList.remove('is-welcoming');
        switchTab('tasks');
      }
      requestAnimationFrame(function () { guide.classList.add('is-visible'); });
    }

    function closeGuide(showLauncher) {
      cancelSpeech();
      guide.classList.remove('is-visible');
      guide.setAttribute('aria-hidden', 'true');
      window.setTimeout(function () { launcher.hidden = !showLauncher; }, 320);
    }

    function addMessage(text, kind, response) {
      var bubble = document.createElement('div');
      bubble.className = 'student-assistant__bubble ' + (kind === 'student' ? 'is-student' : 'is-bot');
      var inner = document.createElement('div');
      var paragraph = document.createElement('p');
      paragraph.textContent = text;
      inner.appendChild(paragraph);
      if (response && response.action_url && /^\/(?!\/)/.test(response.action_url)) {
        var link = document.createElement('a');
        link.href = response.action_url;
        link.className = 'student-assistant__action';
        link.textContent = response.action_label || 'فتح الرابط';
        inner.appendChild(link);
      }
      var small = document.createElement('small');
      small.textContent = kind === 'student' ? 'أنت' : 'مساعد المدرسة';
      inner.appendChild(small);
      if (kind !== 'student') {
        var avatar = document.createElement('span');
        avatar.className = 'student-assistant__avatar';
        avatar.innerHTML = '<i class="bi bi-stars"></i>';
        bubble.appendChild(avatar);
      }
      bubble.appendChild(inner);
      messages.appendChild(bubble);
      messages.scrollTop = messages.scrollHeight;
    }

    function renderSuggestions(items) {
      suggestions.replaceChildren();
      (Array.isArray(items) ? items : []).slice(0, 5).forEach(function (item) {
        var question = typeof item === 'string' ? item : item.question;
        var label = typeof item === 'string' ? item : item.label;
        if (!question) return;
        var button = document.createElement('button');
        button.type = 'button';
        if (typeof item === 'object' && item.icon) {
          var icon = document.createElement('i');
          icon.className = 'bi ' + item.icon;
          button.appendChild(icon);
        }
        button.appendChild(document.createTextNode(label || question));
        button.addEventListener('click', function () { submitQuestion(question); });
        suggestions.appendChild(button);
      });
    }

    function setSending(value) {
      isSending = value;
      input.disabled = value;
      send.disabled = value;
      mic.disabled = value;
      state.innerHTML = value ? '<span class="student-assistant__typing"><i></i><i></i><i></i></span> أفكر في إجابة مناسبة…' : '';
    }

    function submitQuestion(rawQuestion) {
      var question = String(rawQuestion || input.value || '').trim();
      if (isSending || question.length < 2) return;
      switchTab('chat');
      addMessage(question, 'student');
      input.value = '';
      input.style.height = '';
      renderSuggestions([]);
      setSending(true);
      var csrfInput = form.querySelector('[name=csrfmiddlewaretoken]');
      fetch(config.ask_url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfInput ? csrfInput.value : '' },
        body: JSON.stringify({ question: question })
      }).then(function (response) {
        return response.json().catch(function () { return { error: 'تعذر قراءة رد المساعد.' }; }).then(function (data) {
          if (!response.ok && !data.answer) throw new Error(data.error || 'تعذر إرسال السؤال.');
          return data;
        });
      }).then(function (data) {
        addMessage(data.answer || 'لم أجد إجابة مناسبة.', 'bot', data);
        renderSuggestions(data.suggestions || []);
        if (typeof data.ai_remaining === 'number') usage.textContent = 'تبقى لك ' + data.ai_remaining + ' من الأسئلة التعليمية الذكية اليوم';
        speak(data.answer || '');
      }).catch(function (error) {
        addMessage(error.message || 'حدث خطأ مؤقت. حاول مرة أخرى.', 'bot');
      }).finally(function () {
        setSending(false);
        input.focus();
      });
    }

    renderTask(0);
    renderSuggestions(config.quick_prompts || []);
    updateMuteButton();

    if (config.welcome_pending) window.setTimeout(function () { openGuide(true); }, 380);
    else if (config.auto_open && readStorage(dismissedKey) !== localDayKey()) window.setTimeout(function () { openGuide(false); }, 650);
    else launcher.hidden = false;

    tabs.forEach(function (tab) { tab.addEventListener('click', function () { switchTab(tab.dataset.guideTab); }); });
    welcomeStart.addEventListener('click', function () {
      cancelSpeech();
      card.classList.remove('is-welcoming');
      switchTab('tasks');
    });
    listen.addEventListener('click', function () { speak(lastSpokenText); });
    mascot.addEventListener('click', function () { speak(lastSpokenText); });
    previous.addEventListener('click', function () { renderTask(currentIndex - 1); });
    next.addEventListener('click', function () { renderTask(currentIndex + 1); });
    close.addEventListener('click', function () { closeGuide(true); });
    launcher.addEventListener('click', function () { openGuide(false); });
    mute.addEventListener('click', function () {
      isMuted = !isMuted;
      writeStorage(mutedKey, isMuted ? '1' : '0');
      if (isMuted) cancelSpeech();
      updateMuteButton();
    });
    dismissToday.addEventListener('click', function () {
      writeStorage(dismissedKey, localDayKey());
      closeGuide(false);
    });
    form.addEventListener('submit', function (event) { event.preventDefault(); submitQuestion(); });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submitQuestion(); }
    });
    input.addEventListener('input', function () {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 100) + 'px';
    });

    var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      mic.disabled = true;
      mic.title = 'الإملاء الصوتي غير مدعوم في هذا المتصفح';
    } else {
      var recognition = new Recognition();
      recognition.lang = 'ar-PS';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      mic.addEventListener('click', function () {
        try { recognition.start(); state.textContent = 'تحدث الآن… أنا أستمع إليك'; mic.classList.add('is-listening'); } catch (error) { /* جلسة الاستماع قائمة. */ }
      });
      recognition.onresult = function (event) {
        input.value = event.results[0][0].transcript;
        state.textContent = 'تمت كتابة سؤالك، راجعه ثم أرسله.';
      };
      recognition.onerror = function () { state.textContent = 'لم أتمكن من سماعك بوضوح. يمكنك كتابة السؤال.'; };
      recognition.onend = function () { mic.classList.remove('is-listening'); };
    }

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && guide.classList.contains('is-visible')) closeGuide(true);
    });
    window.addEventListener('pagehide', cancelSpeech);
    document.addEventListener('visibilitychange', function () { if (document.hidden) cancelSpeech(); });
  });
})();
