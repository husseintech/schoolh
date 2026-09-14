(function () {
    'use strict';

    var MAX_FILES = 10;
    var MAX_FILE_SIZE = 10 * 1024 * 1024;
    var ALLOWED_EXTENSIONS = /\.(jpe?g|png|webp|heic|heif|pdf)$/i;
    var NOTICE_KEY = 'schoolRadioUploadNotice';

    function setStatus(element, message, tone) {
        if (!element) return;
        element.textContent = message || '';
        element.classList.remove('text-primary', 'text-success', 'text-danger', 'text-warning');
        element.classList.add('text-' + (tone || 'primary'));
    }

    function replaceExtension(name) {
        return name.replace(/\.[^.]+$/, '') + '.jpg';
    }

    async function compressJpeg(file) {
        if (file.type !== 'image/jpeg' || file.size < 1500000 || !window.createImageBitmap) return file;
        var bitmap = await createImageBitmap(file);
        var longest = Math.max(bitmap.width, bitmap.height);
        if (longest <= 1920 && file.size < 2500000) {
            bitmap.close();
            return file;
        }
        var scale = Math.min(1, 1920 / longest);
        var canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(bitmap.width * scale));
        canvas.height = Math.max(1, Math.round(bitmap.height * scale));
        canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        bitmap.close();
        var blob = await new Promise(function (resolve) {
            canvas.toBlob(resolve, 'image/jpeg', 0.84);
        });
        if (!blob || blob.size >= file.size) return file;
        return new File([blob], replaceExtension(file.name), {type: 'image/jpeg', lastModified: file.lastModified});
    }

    function requestError(payload, fallback) {
        var error = new Error((payload && payload.error) || fallback || 'تعذّرت عملية الرفع');
        error.code = payload && payload.code;
        error.reconnectUrl = payload && payload.reconnect_url;
        return error;
    }

    async function responseJson(response, fallback) {
        var payload = null;
        try {
            payload = await response.json();
        } catch (ignore) {
            throw requestError(null, fallback);
        }
        if (!response.ok || !payload.ok) throw requestError(payload, fallback);
        return payload;
    }

    async function prepareFiles(input, status) {
        var originals = Array.from(input.files || []);
        if (originals.length > MAX_FILES) {
            throw new Error('يمكن اختيار ' + MAX_FILES + ' ملفات كحد أقصى في المرة الواحدة.');
        }
        var prepared = [];
        for (var index = 0; index < originals.length; index += 1) {
            var original = originals[index];
            if (!ALLOWED_EXTENSIONS.test(original.name)) {
                throw new Error('الملف «' + original.name + '» غير مدعوم.');
            }
            setStatus(status, 'جارٍ تجهيز الملف ' + (index + 1) + ' من ' + originals.length + '…', 'primary');
            var file = await compressJpeg(original);
            if (file.size > MAX_FILE_SIZE) {
                throw new Error('الملف «' + original.name + '» أكبر من 10 ميغابايت.');
            }
            if (!file.size) throw new Error('الملف «' + original.name + '» فارغ.');
            prepared.push(file);
        }
        return prepared;
    }

    function csrfToken(form) {
        var field = form.querySelector('input[name="csrfmiddlewaretoken"]');
        return field ? field.value : '';
    }

    async function saveEntry(form, csrf) {
        var body = new FormData(form);
        body.delete('files');
        var response = await fetch(form.action || window.location.href, {
            method: 'POST',
            body: body,
            credentials: 'same-origin',
            cache: 'no-store',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrf,
                'Accept': 'application/json'
            }
        });
        return responseJson(response, 'تعذّر حفظ بيانات الإذاعة. راجع الحقول المطلوبة.');
    }

    async function startUpload(file, startUrl, csrf) {
        var response = await fetch(startUrl, {
            method: 'POST',
            body: JSON.stringify({name: file.name, type: file.type, size: file.size}),
            credentials: 'same-origin',
            cache: 'no-store',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrf,
                'Accept': 'application/json'
            }
        });
        return responseJson(response, 'تعذّر بدء رفع الملف إلى Google Drive.');
    }

    async function uploadFile(file, startUrl, csrf, status, number, count) {
        var session = await startUpload(file, startUrl, csrf);
        var chunkSize = session.chunk_size || (2 * 1024 * 1024);
        var offset = 0;
        while (offset < file.size) {
            var endExclusive = Math.min(offset + chunkSize, file.size);
            var chunk = file.slice(offset, endExclusive);
            var percent = Math.round((endExclusive / file.size) * 100);
            setStatus(
                status,
                'رفع الملف ' + number + ' من ' + count + ': «' + file.name + '» — ' + percent + '%',
                'primary'
            );
            var response = await fetch(session.chunk_url, {
                method: 'POST',
                body: chunk,
                credentials: 'same-origin',
                cache: 'no-store',
                headers: {
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes ' + offset + '-' + (endExclusive - 1) + '/' + file.size,
                    'X-Upload-Token': session.upload_token,
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrf,
                    'Accept': 'application/json'
                }
            });
            var result = await responseJson(response, 'توقف رفع الملف «' + file.name + '».');
            offset = endExclusive;
            if (result.complete && offset < file.size) {
                throw new Error('أبلغ Google Drive عن اكتمال الملف قبل وصول جميع أجزائه.');
            }
        }
    }

    function storeNotice(message, tone, reconnectUrl) {
        try {
            sessionStorage.setItem(NOTICE_KEY, JSON.stringify({
                message: message,
                tone: tone || 'success',
                reconnectUrl: reconnectUrl || ''
            }));
        } catch (ignore) {}
    }

    function displayStoredNotice() {
        var raw = null;
        try {
            raw = sessionStorage.getItem(NOTICE_KEY);
            sessionStorage.removeItem(NOTICE_KEY);
        } catch (ignore) {}
        if (!raw) return;
        var notice;
        try {
            notice = JSON.parse(raw);
        } catch (ignore) {
            return;
        }
        var host = document.querySelector('main') || document.querySelector('.container') || document.body;
        var box = document.createElement('div');
        box.className = 'alert alert-' + (notice.tone === 'danger' ? 'danger' : (notice.tone === 'warning' ? 'warning' : 'success'));
        box.setAttribute('role', 'alert');
        box.textContent = notice.message;
        if (notice.reconnectUrl) {
            var link = document.createElement('a');
            link.href = notice.reconnectUrl;
            link.className = 'btn btn-sm btn-outline-danger ms-2';
            link.textContent = 'إعادة ربط Google Drive';
            box.appendChild(link);
        }
        host.insertBefore(box, host.firstChild);
    }

    displayStoredNotice();

    document.querySelectorAll('form[data-radio-upload]').forEach(function (form) {
        var input = form.querySelector('input[type="file"][name="files"]');
        var status = form.querySelector('[data-upload-status]');
        var button = form.querySelector('[data-submit-button]');
        if (!input) return;

        input.addEventListener('change', function () {
            setStatus(status, input.files.length ? 'تم اختيار ' + input.files.length + ' ملف/ملفات.' : '', 'primary');
        });

        form.addEventListener('submit', async function (event) {
            if (!input.files.length) return;
            event.preventDefault();
            if (button) button.disabled = true;

            var redirectUrl = '';
            var entrySaved = false;
            var csrf = csrfToken(form);
            try {
                var files = await prepareFiles(input, status);
                var startUrl = form.dataset.uploadStartUrl || '';
                if (form.dataset.radioUpload === 'staged') {
                    setStatus(status, 'جارٍ حفظ بيانات الإذاعة أولًا…', 'primary');
                    var entry = await saveEntry(form, csrf);
                    entrySaved = true;
                    startUrl = entry.upload_start_url;
                    redirectUrl = entry.redirect_url;
                } else {
                    redirectUrl = window.location.href;
                }

                var saved = 0;
                var failures = [];
                var reconnectUrl = '';
                for (var index = 0; index < files.length; index += 1) {
                    try {
                        await uploadFile(files[index], startUrl, csrf, status, index + 1, files.length);
                        saved += 1;
                    } catch (error) {
                        failures.push('«' + files[index].name + '»: ' + error.message);
                        reconnectUrl = reconnectUrl || error.reconnectUrl || '';
                        if (error.code === 'drive_reconnect') break;
                    }
                }

                if (failures.length) {
                    var failureMessage = 'تم رفع ' + saved + ' من ' + files.length + ' ملف/ملفات. ' + failures.join(' ');
                    setStatus(status, failureMessage, 'danger');
                    storeNotice(failureMessage, 'danger', reconnectUrl);
                } else {
                    var successMessage = 'تم رفع ' + saved + ' ملف/ملفات إلى Google Drive بنجاح.';
                    setStatus(status, successMessage, 'success');
                    storeNotice(successMessage, 'success');
                }
                window.setTimeout(function () {
                    window.location.href = redirectUrl || window.location.href;
                }, failures.length ? 1800 : 500);
            } catch (error) {
                var message = error.message || 'تعذّرت عملية الرفع.';
                setStatus(status, message, 'danger');
                if (entrySaved && redirectUrl) {
                    storeNotice(message, 'danger', error.reconnectUrl || '');
                    window.setTimeout(function () { window.location.href = redirectUrl; }, 1800);
                } else if (button) {
                    button.disabled = false;
                }
            }
        });
    });
}());
