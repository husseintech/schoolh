(function () {
  'use strict';

  function localDayKey() {
    var now = new Date();
    var month = String(now.getMonth() + 1).padStart(2, '0');
    var day = String(now.getDate()).padStart(2, '0');
    return now.getFullYear() + '-' + month + '-' + day;
  }

  function readStorage(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function writeStorage(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      // The guide still works when private browsing blocks local storage.
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var guide = document.getElementById('studentVoiceGuide');
    var dataNode = document.getElementById('studentGuideTasks');
    if (!guide || !dataNode) return;

    var tasks;
    try {
      tasks = JSON.parse(dataNode.textContent || '[]');
    } catch (error) {
      return;
    }
    if (!Array.isArray(tasks) || !tasks.length) return;

    var studentKey = guide.dataset.studentKey || 'student';
    var dismissedKey = 'schoolh_student_guide_dismissed_' + studentKey;
    var mutedKey = 'schoolh_student_guide_muted_' + studentKey;
    var launcher = document.getElementById('studentGuideLauncher');
    var mascot = document.getElementById('studentGuideMascot');
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
    var currentIndex = 0;
    var hasListened = false;
    var speechSupported = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
    var isMuted = readStorage(mutedKey) === '1';

    function cancelSpeech() {
      if (speechSupported) window.speechSynthesis.cancel();
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
      currentIndex = (index + tasks.length) % tasks.length;
      var task = tasks[currentIndex];
      cancelSpeech();
      status.className = 'student-guide__status tone-' + (task.tone || 'info');
      status.textContent = task.key === 'student_file' ? 'للمتابعة' : 'مهمة مطلوبة';
      title.textContent = task.title;
      message.textContent = task.message;
      action.href = task.url;
      actionText.textContent = task.action_label;
      counter.textContent = (currentIndex + 1) + ' من ' + tasks.length;
      pager.hidden = tasks.length < 2;
      taskBadge.textContent = tasks.length;
      hasListened = false;
      updateMuteButton();
    }

    function chooseArabicVoice() {
      if (!speechSupported) return null;
      var voices = window.speechSynthesis.getVoices();
      return voices.find(function (voice) { return /^ar[-_](PS|SA)/i.test(voice.lang); }) ||
        voices.find(function (voice) { return /^ar/i.test(voice.lang); }) || null;
    }

    function speakCurrentTask() {
      if (!speechSupported || isMuted) return;
      cancelSpeech();
      var task = tasks[currentIndex];
      var utterance = new SpeechSynthesisUtterance(task.title + '. ' + task.message);
      utterance.lang = 'ar-SA';
      utterance.rate = .9;
      utterance.pitch = 1.08;
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

    function openGuide() {
      launcher.hidden = true;
      guide.setAttribute('aria-hidden', 'false');
      requestAnimationFrame(function () { guide.classList.add('is-visible'); });
    }

    function closeGuide(showLauncher) {
      cancelSpeech();
      guide.classList.remove('is-visible');
      guide.setAttribute('aria-hidden', 'true');
      window.setTimeout(function () { launcher.hidden = !showLauncher; }, 320);
    }

    renderTask(0);
    updateMuteButton();

    if (readStorage(dismissedKey) !== localDayKey()) {
      window.setTimeout(openGuide, 650);
    }

    listen.addEventListener('click', speakCurrentTask);
    mascot.addEventListener('click', speakCurrentTask);
    previous.addEventListener('click', function () { renderTask(currentIndex - 1); });
    next.addEventListener('click', function () { renderTask(currentIndex + 1); });
    close.addEventListener('click', function () { closeGuide(true); });
    launcher.addEventListener('click', openGuide);
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
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && guide.classList.contains('is-visible')) closeGuide(true);
    });
    window.addEventListener('pagehide', cancelSpeech);
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) cancelSpeech();
    });
  });
})();
