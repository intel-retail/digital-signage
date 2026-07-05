function getBrowserFingerprint() {
    const userAgent = navigator.userAgent;
    const screenResolution = `${screen.width}x${screen.height}`;
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const timestamp = performance.timeOrigin;
    const random = Math.random().toString(36).substring(2);

    let tabId = sessionStorage.getItem('tabId');
    if (!tabId) {
        tabId = `${Date.now()}_${random}`;
        sessionStorage.setItem('tabId', tabId);
    }

    const fingerprint = `${userAgent}_${screenResolution}_${timezone}_${timestamp}_${tabId}`;

    let hash = 0;
    for (let i = 0; i < fingerprint.length; i++) {
        const char = fingerprint.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return Math.abs(hash).toString(36);
}

function updateConnectionStatus(connected) {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');

    if (connected) {
        statusDot.classList.add('connected');
        statusText.textContent = 'Connected';
    } else {
        statusDot.classList.remove('connected');
        statusText.textContent = 'Disconnected';
    }
}

function startPolling() {
    if (window.pollingInterval) clearInterval(window.pollingInterval);
    pollForAdvertisement();
    window.pollingInterval = setInterval(pollForAdvertisement, 2000);
}

function pollForAdvertisement() {
    const container = document.getElementById('ad-image-container');
    const rect = container.getBoundingClientRect();
    const width = Math.floor(rect.width);
    const height = Math.floor(rect.height);

    const clientId = getBrowserFingerprint();
    fetch(`/get_current_advertisement?width=${width}&height=${height}&client_id=${clientId}`)
        .then(res => {
            if (res.status === 200) {
                res.blob().then(imageBlob => {
                    const xgenerationTime = res.headers.get('X-Generation-Time');
                    const imageUrl = URL.createObjectURL(imageBlob);

                    if (xgenerationTime) {
                        const generationTimeElement = document.getElementById('generationTime');
                        generationTimeElement.textContent = `${xgenerationTime}`;
                        generationTimeElement.style.display = 'block';
                    }

                    const productImage = document.getElementById('productImage');
                    const aigServerLoading = document.getElementById('aigServerLoading');

                    productImage.src = imageUrl;
                    productImage.style.display = 'block';
                    aigServerLoading.style.display = 'none';
                });
            }
            return;
        })
        .catch(err => {
            console.error('Error fetching advertisement:', err);
        });
}
