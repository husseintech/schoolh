(function () {
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

    document.querySelectorAll('form[data-radio-upload]').forEach(function (form) {
        var input = form.querySelector('input[type="file"][name="files"]');
        var status = form.querySelector('[data-upload-status]');
        var button = form.querySelector('[data-submit-button]');
        if (!input) return;

        input.addEventListener('change', function () {
            if (status) status.textContent = input.files.length ? 'تم اختيار ' + input.files.length + ' ملف/ملفات.' : '';
        });

        form.addEventListener('submit', async function (event) {
            if (form.dataset.radioUpload === 'sequential' && input.files.length) {
                event.preventDefault();
                if (button) button.disabled = true;
                var files = Array.from(input.files).slice(0, 10);
                var csrf = form.querySelector('input[name="csrfmiddlewaretoken"]');
                var saved = 0;
                try {
                    for (var index = 0; index < files.length; index += 1) {
                        if (status) status.textContent = 'جارٍ تجهيز ورفع الملف ' + (index + 1) + ' من ' + files.length + '…';
                        var prepared = await compressJpeg(files[index]);
                        var body = new FormData();
                        if (csrf) body.append('csrfmiddlewaretoken', csrf.value);
                        body.append('files', prepared, prepared.name);
                        var response = await fetch(form.action, {
                            method: 'POST',
                            body: body,
                            headers: {'X-Requested-With': 'XMLHttpRequest'},
                            credentials: 'same-origin'
                        });
                        var result = await response.json();
                        if (!response.ok || !result.saved) throw new Error('upload');
                        saved += result.saved;
                    }
                    if (status) status.textContent = 'تم رفع ' + saved + ' ملف/ملفات بنجاح.';
                    window.setTimeout(function () { window.location.reload(); }, 500);
                } catch (error) {
                    if (status) status.textContent = 'توقف الرفع بعد ' + saved + ' ملف/ملفات. أعد اختيار الملفات التي لم تُرفع.';
                    if (button) button.disabled = false;
                }
                return;
            }
            if (form.dataset.filesPrepared === '1' || !input.files.length || typeof DataTransfer === 'undefined') return;
            event.preventDefault();
            if (button) button.disabled = true;
            if (status) status.textContent = 'جارٍ تجهيز الصور للرفع…';
            try {
                var transfer = new DataTransfer();
                for (var i = 0; i < input.files.length; i += 1) {
                    transfer.items.add(await compressJpeg(input.files[i]));
                }
                input.files = transfer.files;
                form.dataset.filesPrepared = '1';
                if (status) status.textContent = 'تم تجهيز الصور، جارٍ الرفع إلى Google Drive…';
            } catch (error) {
                form.dataset.filesPrepared = '1';
                if (status) status.textContent = 'جارٍ رفع الملفات الأصلية…';
            }
            if (button) button.disabled = false;
            form.requestSubmit(event.submitter || button);
        });
    });
}());
