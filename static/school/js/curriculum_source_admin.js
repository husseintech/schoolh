(function () {
    'use strict';

    function setStatus(element, message, tone) {
        element.textContent = message || '';
        element.className = 'text-' + (tone || 'primary');
    }

    function csrf(form) {
        var field = form.querySelector('input[name="csrfmiddlewaretoken"]');
        return field ? field.value : '';
    }

    async function jsonResponse(response) {
        var payload;
        try { payload = await response.json(); } catch (ignore) { payload = {}; }
        if (!response.ok || payload.ok === false) {
            var error = new Error(payload.error || 'تعذرت عملية الرفع.');
            error.reconnectUrl = payload.reconnect_url;
            throw error;
        }
        return payload;
    }

    async function sha256(file) {
        if (!window.crypto || !window.crypto.subtle) {
            throw new Error('المتصفح لا يدعم التحقق الآمن من بصمة الملف. استخدم متصفحًا حديثًا.');
        }
        var digest = await window.crypto.subtle.digest('SHA-256', await file.arrayBuffer());
        return Array.from(new Uint8Array(digest)).map(function (value) {
            return value.toString(16).padStart(2, '0');
        }).join('');
    }

    document.querySelectorAll('[data-pdf-upload]').forEach(function (form) {
        var input = form.querySelector('input[type="file"]');
        var button = form.querySelector('button[type="submit"]');
        var status = form.querySelector('[data-upload-status]');
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            var file = input.files && input.files[0];
            if (!file) return setStatus(status, 'اختر ملف PDF أولًا.', 'danger');
            if (!/\.pdf$/i.test(file.name) || (file.type && file.type !== 'application/pdf')) {
                return setStatus(status, 'الملف المختار ليس PDF.', 'danger');
            }
            if (!file.size || file.size > 100 * 1024 * 1024) {
                return setStatus(status, 'يجب ألا يتجاوز حجم الملف 100 ميغابايت.', 'danger');
            }
            button.disabled = true;
            try {
                setStatus(status, 'جارٍ التحقق من مطابقة الكتاب…', 'primary');
                var fileHash = await sha256(file);
                setStatus(status, 'جارٍ بدء الرفع الآمن…', 'primary');
                var startResponse = await fetch(form.dataset.startUrl, {
                    method: 'POST',
                    credentials: 'same-origin',
                    cache: 'no-store',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf(form), 'Accept': 'application/json'},
                    body: JSON.stringify({name: file.name, type: file.type || 'application/pdf', size: file.size, sha256: fileHash})
                });
                var session = await jsonResponse(startResponse);
                var chunkSize = session.chunk_size || 2 * 1024 * 1024;
                var offset = 0;
                while (offset < file.size) {
                    var end = Math.min(offset + chunkSize, file.size);
                    setStatus(status, 'جارٍ الرفع… ' + Math.round(end / file.size * 100) + '%', 'primary');
                    var response = await fetch(session.chunk_url, {
                        method: 'POST',
                        credentials: 'same-origin',
                        cache: 'no-store',
                        headers: {
                            'Content-Type': 'application/octet-stream',
                            'Content-Range': 'bytes ' + offset + '-' + (end - 1) + '/' + file.size,
                            'X-Upload-Token': session.upload_token,
                            'X-CSRFToken': csrf(form),
                            'Accept': 'application/json'
                        },
                        body: file.slice(offset, end)
                    });
                    await jsonResponse(response);
                    offset = end;
                }
                setStatus(status, 'تم حفظ PDF الأصلي في Google Drive.', 'success');
                window.setTimeout(function () { window.location.reload(); }, 700);
            } catch (error) {
                setStatus(status, error.message, 'danger');
                if (error.reconnectUrl) {
                    var link = document.createElement('a');
                    link.href = error.reconnectUrl;
                    link.textContent = ' إعادة ربط Drive';
                    status.appendChild(link);
                }
                button.disabled = false;
            }
        });
    });
})();
