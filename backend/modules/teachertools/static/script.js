// Verbinde zum Socket.IO-Server
if (!('teachertools_socket' in window)) {
    var teachertools_url ='/teachertools';
    window.teachertools_socket = io(teachertools_url);
    window.qr_options = {
        width: 1000,
        height: 1000,
        type: 'svg',
        data: '',
        image: '',
        dotsOptions: {
            color: '#001d1d',
            type: 'rounded'
        },
        backgroundOptions: {
            color: '#ffffff',
        },
        imageOptions: {
            crossOrigin: 'anonymous',
            margin: 20
        }
    };
    window.codeQR = '';
};


function addEventListenerButtons() {
    teachertools_qr_button = document.getElementById("teachertools_qr_submit");
    teachertools_qr_url = document.getElementById("teachertools_qr_url");
    if (!teachertools_qr_button.dataset.bound) { // Verhindert doppelte Bindung
        teachertools_qr_button.addEventListener("click", () => {
        genererCodeQR();
        });
        teachertools_qr_button.addEventListener("keydown", (event) => {
            if (event.key === 'Enter') {
                genererCodeQR();
            }

        });
        teachertools_qr_url.addEventListener("keydown", (event) => {
            if (event.key === 'Enter') {
                genererCodeQR();
            }

        });
        teachertools_qr_button.dataset.bound = "true";
    }
}


function genererCodeQR () {
    qr_url = document.getElementById("teachertools_qr_url").value.trim();
    if (qr_url !== '') {
        if (document.querySelector('#teachertools-qr-code').innerHTML !== '') {
            document.querySelector('#teachertools-qr-code').innerHTML = ''
        }
        window.qr_options.data = qr_url;
        window.codeQR = new QRCodeStyling(window.qr_options);
        window.codeQR.append(document.querySelector('#teachertools-qr-code'));
        document.querySelector('#teachertools-qr-code svg').setAttribute('viewBox', '0 0 1000 1000');
        document.querySelector('#teachertools-qr-code svg').setAttribute('preserveAspectRatio', 'xMinYMin meet');

        document.querySelector('#teachertools-qr-modal').classList.add('show');
        document.querySelector('#teachertools-qr-close').focus();
    }
}

document.querySelector('#teachertools-qr-download-submit').addEventListener('click', function () {
    codeQR.download({ name: 'code-qr', extension: 'png' });
});

document.querySelector('#teachertools-qr-download-submit').addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        codeQR.download({ name: 'code-qr', extension: 'png' });
    }
});

document.querySelector('#teachertools-qr-close').addEventListener('click', function () {
    closeQRModal();
});

document.querySelector('#teachertools-qr-close').addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        closeQRModal();
    }
});

document.querySelector('#teachertools-qr-color').addEventListener('change', function (event) {
    window.qr_options.dotsOptions.color = event.target.value;
    QRmodifierOptions(window.qr_options);
});

document.querySelectorAll('.teachertools-qr-color').forEach(function (element) {
    element.addEventListener('click', function (event) {
        const color = event.target.getAttribute('data-color');
        if (color !== '') {
            window.qr_options.dotsOptions.color = color;
            QRmodifierOptions(window.qr_options);
        }
    });
    element.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
            const color = event.target.getAttribute('data-color');
            if (color !== '') {
                window.qr_options.dotsOptions.color = color;
                QRmodifierOptions(window.qr_options);
            }
        }
    });
});

document.querySelector('#teachertools-qr-image').addEventListener('change', function (event) {
    const image_raw = event.target.files[0];
    if (image_raw) {
        const reader = new FileReader();
        reader.readAsDataURL(image_raw);
        reader.onloadend = function (e) {
            const img = new Image();
            img.src = e.target.result;
            img.onload = function () {
                if (img.width > 500) {
                    const canvas = document.createElement('canvas');
                    const ratio = img.width / img.height;
                    const width = 500;
                    const height = 500 / ratio;
                    canvas.width = width;
                    canvas.height = height;
                    canvas.getContext('2d').drawImage(img, 0, 0, width, height);
                    window.qr_options.image = canvas.toDataURL('image/png');
                    QRmodifierOptions(window.qr_options);
                    document.querySelector('#teachertools-qr-image-remove').classList.add('visible');
                    event.target.value = '';
                } else {
                    window.qr_options.image = e.target.result;
                    QRmodifierOptions(window.qr_options);
                    document.querySelector('#teachertools-qr-image-remove').classList.add('visible');
                    event.target.value = '';
                }
            }
        }
    }
});

document.querySelector('#teachertools-qr-image-remove').addEventListener('click', function () {
    QRRemoveImage();
});

document.querySelector('#teachertools-qr-image-remove').addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        QRRemoveImage();
    }
});

function QRRemoveImage () {
    window.qr_options.image = '';
    QRmodifierOptions(window.qr_options);
    document.querySelector('#teachertools-qr-image-remove').classList.remove('visible');
}


function QRmodifierOptions (image, color) {
    window.codeQR.update(window.qr_options);
    document.querySelector('#teachertools-qr-code svg').setAttribute('viewBox', '0 0 1000 1000');
    document.querySelector('#teachertools-qr-code svg').setAttribute('preserveAspectRatio', 'xMinYMin meet');
}


function closeQRModal () {
    document.querySelector('#teachertools-qr-modal').classList.remove('show');
    document.querySelector('#teachertools_qr_url').focus();
}


addEventListenerButtons();