// script.js
// API URL: CORS'suz mimari - aynı domain'de relative path kullan (depremanaliz.onrender.com)
// GitHub Pages'den açılırsa (eski link) Render backend'e cross-origin bağlan
const RENDER_BACKEND_URL = 'https://depremanaliz.onrender.com';
const isSameOrigin = window.location.hostname === 'depremanaliz.onrender.com' ||
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

const API_URL = isSameOrigin ? '' : (window.location.hostname.includes('github.io') ? RENDER_BACKEND_URL : window.location.origin);

let mymap = null;
let cityRiskData = null;
let cityHeatmapLayer = null;
let earthquakeMarkersLayer = null;

if (typeof L !== 'undefined') {
    L.Icon.Default.imagePath = '/static/lib/leaflet/images/';
}

function formatEqDate(eq) {
    const ts = eq.created_at || eq.timestamp || 0;
    if (ts) {
        const d = new Date(ts * 1000);
        return d.toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' });
    }
    return (eq.date || '') + ' ' + (eq.time || '') || 'Bilinmiyor';
}

function initializeMap() {
    if (mymap !== null && mymap._container) {
        mymap.remove();
        mymap = null;
    }
    mymap = L.map('mapid').setView([39.9, 35.8], 6);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap © CARTO'
    }).addTo(mymap);
    [50, 200, 500, 1000].forEach(ms => setTimeout(() => mymap && mymap.invalidateSize(), ms));
}

function getRiskColor(score) {
    if (score >= 7.0) return 'red'; 
    if (score >= 4.0) return 'orange'; 
    return 'green'; 
}

// Modern Modal System - Global functions
function openModal(title, content) {
    const modalOverlay = document.getElementById('modalOverlay');
    const modalTitle = document.getElementById('modalTitle');
    const modalContent = document.getElementById('modalContent');
    
    if (!modalOverlay || !modalTitle || !modalContent) return;
    
    modalTitle.textContent = title;
    modalContent.innerHTML = content;
    modalOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    const modalOverlay = document.getElementById('modalOverlay');
    if (modalOverlay) {
        modalOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Modal System Setup
    const modalOverlay = document.getElementById('modalOverlay');
    const modalClose = document.getElementById('modalClose');
    
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                closeModal();
            }
        });
    }
    
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    
    // ESC tuşu ile kapat
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalOverlay && modalOverlay.classList.contains('active')) {
            closeModal();
        }
    });
    
    window.addEventListener('resize', () => { if (mymap) mymap.invalidateSize(); });
    window.addEventListener('load', () => { setTimeout(() => mymap && mymap.invalidateSize(), 100); });
    
    // API URL'ini dinamik olarak kullan (localhost veya production)
    const RENDER_API_BASE_URL = API_URL;
    
    // Render.com'u uyanık tutmak için düzenli ping (her 10 dakikada bir)
    // Free plan'da 15 dakika inaktiflikten sonra uyku moduna geçer
    if (RENDER_API_BASE_URL.includes('render.com') || RENDER_API_BASE_URL.includes('onrender.com')) {
        function pingServer() {
            // Health check endpoint'i kullan (en hafif endpoint)
            fetch(`${RENDER_API_BASE_URL}/api/health`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                mode: 'cors'
            })
            .then(response => {
                if (response.ok) {
                    console.log('[PING] ✅ Render.com uyanık tutuldu');
                } else {
                    console.log('[PING] ⚠️ Sunucu yanıt vermedi');
                }
            })
            .catch(error => {
                // İlk ping başarısız olabilir (sunucu uyku modunda)
                // Bu normal, sonraki ping'ler başarılı olacak
                console.log('[PING] ⏳ Sunucu uyanıyor...');
            });
        }
        
        // İlk ping'i hemen gönder
        setTimeout(pingServer, 2000); // 2 saniye sonra
        
        // Sonra her 10 dakikada bir ping gönder (600000 ms = 10 dakika)
        // 15 dakika uyku moduna geçmeden önce 10 dakikada bir ping yeterli
        setInterval(pingServer, 600000); // 10 dakika = 600000 ms
        
        console.log('[PING] Render.com uyanık tutma sistemi aktif (her 10 dakikada bir ping)');
    }
    const apiURL = `${RENDER_API_BASE_URL}/api/risk`;
    const eqListEl = document.getElementById('earthquakeList');
    const m5ListEl = document.getElementById('m5RiskList');
    const cityListEl = document.getElementById('cityRiskList');
    const anomalyEl = document.getElementById('anomalyContent');
    const metricsEl = document.getElementById('metricsDetail');
    const refreshButton = document.getElementById('refreshButton');
    
    const getLocationButton = document.getElementById('getLocationButton');
    const saveSettingsButton = document.getElementById('saveSettingsButton');
    const getOptInLinkButton = document.getElementById('getOptInLinkButton');
    const optInLinkDisplay = document.getElementById('optInLinkDisplay');
    const optInLink = document.getElementById('optInLink');
    const locationStatus = document.getElementById('locationStatus');
    const numberInput = document.getElementById('numberInput');
    
    // Manuel hasar tahmini kaldırıldı
    // Manuel hasar tahmini kaldırıldı
    const predictRiskButton = document.getElementById('predictRiskButton');
    const analyzeCityDamageButton = document.getElementById('analyzeCityDamageButton');
    const checkIstanbulWarningButton = document.getElementById('checkIstanbulWarningButton');

    let userCoords = null; 

    // Tek harita: Risk + Depremler + Fay + M5 + İl overlay
    function fetchRiskData() {
        if (eqListEl) eqListEl.innerHTML = '<p class="loading">Yükleniyor...</p>';
        initializeMap();

        fetch(apiURL, { method: 'GET', headers: { 'Content-Type': 'application/json' }, mode: 'cors' })
            .then(r => (!r.ok && (r.status === 503 || r.status === 502)) ? null : (r.ok ? r.json() : Promise.reject(new Error(r.status))))
            .then(data => {
                if (!data) {
                    if (eqListEl) eqListEl.innerHTML = '<p class="loading">Sunucu uyanıyor, lütfen bekleyin...</p>';
                    return;
                }
                let bounds = [];

                // 1. Fay hatları
                if (data.fault_lines && data.fault_lines.length > 0) {
                    data.fault_lines.forEach(fault => {
                        const coords = fault.coords.map(c => [c[0], c[1]]);
                        L.polyline(coords, { color: '#FF1744', weight: 4, opacity: 0.8, dashArray: '10, 5' })
                            .bindPopup(`<b>${fault.name}</b><br>⚠️ Aktif Fay Hattı`).addTo(mymap);
                        bounds.push(...coords);
                    });
                }

                // 2. Depremler - Konum, Tarih, Derinlik, Şiddet popup
                const eqs = data.recent_earthquakes || [];
                if (earthquakeMarkersLayer) mymap.removeLayer(earthquakeMarkersLayer);
                earthquakeMarkersLayer = L.layerGroup();
                eqs.forEach((eq, i) => {
                    if (!eq.geojson || !eq.geojson.coordinates) return;
                    const [lon, lat] = eq.geojson.coordinates;
                    const mag = eq.mag || 0;
                    const loc = eq.location || 'Bilinmiyor';
                    const tarih = formatEqDate(eq);
                    const derinlik = (eq.depth != null ? eq.depth : 'N/A') + (typeof eq.depth === 'number' ? ' km' : '');
                    bounds.push([lat, lon]);
                    let eqColor = '#2ecc71', radius = 5;
                    if (mag >= 5.0) { eqColor = '#FF1744'; radius = 12; }
                    else if (mag >= 4.0) { eqColor = '#f39c12'; radius = 8; }
                    else if (mag >= 3.0) { eqColor = '#3498db'; radius = 6; }
                    const m = L.circleMarker([lat, lon], { radius, color: '#000', fillColor: eqColor, fillOpacity: 0.8, weight: 2 });
                    m.bindPopup(`<b>📍 Konum:</b> ${loc}<br><b>📅 Tarih:</b> ${tarih}<br><b>📏 Derinlik:</b> ${derinlik}<br><b>💥 Şiddet:</b> M${mag.toFixed(1)}`);
                    m.addTo(earthquakeMarkersLayer);
                });
                earthquakeMarkersLayer.addTo(mymap);

                // 3. YZ Risk bölgeleri
                (data.risk_regions || []).forEach(rr => {
                    const c = getRiskColor(rr.score);
                    L.circleMarker([rr.lat, rr.lon], { radius: rr.score * 1.5, color: c, fillColor: c, fillOpacity: 0.6, weight: 3 })
                        .bindPopup(`<b>🤖 YZ Risk</b><br>Puan: ${rr.score.toFixed(1)}/10<br>Yoğunluk: ${rr.density}`).addTo(mymap);
                    bounds.push([rr.lat, rr.lon]);
                });

                if (bounds.length > 0) mymap.fitBounds(bounds, { padding: [50, 50] });
                else mymap.setView([39.9, 35.8], 6);
                if (cityRiskData) addCityHeatmapOverlay(cityRiskData);
                mymap.invalidateSize();

                // Son depremler listesi
                if (eqListEl) {
                    if (eqs.length === 0) eqListEl.innerHTML = '<p class="loading">Deprem verisi yok.</p>';
                    else eqListEl.innerHTML = eqs.slice(0, 15).map(eq => {
                        const loc = eq.location || 'Bilinmiyor';
                        const mag = eq.mag || 0;
                        const cls = mag >= 5 ? 'mag-high' : mag >= 4 ? 'mag-mid' : '';
                        return `<div class="eq-item ${cls}"><strong>${loc}</strong> · M${mag.toFixed(1)} · ${formatEqDate(eq)} · ${eq.depth != null ? eq.depth + ' km' : '-'}</div>`;
                    }).join('');
                }
            })
            .catch(e => {
                if (eqListEl) eqListEl.innerHTML = `<p style="color:#FF1744;">Bağlantı hatası. Yenileyin.</p>`;
            });
    }

    function getRiskLevelClass(score) {
        if (score >= 70) return 'risk-high';
        if (score >= 30) return 'risk-mid';
        return 'risk-low';
    }

    function getRiskLabel(score) {
        if (score >= 70) return 'YÜKSEK';
        if (score >= 50) return 'ORTA-YÜKSEK';
        if (score >= 30) return 'ORTA';
        if (score >= 15) return 'DÜŞÜK';
        return 'MİNİMAL';
    }

    function cityRisksToMap(cityRisks) {
        const map = {};
        (cityRisks || []).forEach(c => { map[c.city] = c; });
        return map;
    }

    function updateRiskMeter(cityRisks) {
        const grid = document.getElementById('riskMeterGrid');
        if (!grid || !cityRisks) return;
        const cities = ['İstanbul', 'Ankara', 'İzmir', 'Bursa', 'Kocaeli'];
        const byCity = Array.isArray(cityRisks) ? cityRisksToMap(cityRisks) : cityRisks;
        cities.forEach((cityName, i) => {
            const item = grid.children[i];
            if (!item) return;
            const city = byCity[cityName];
            if (city) {
                const score = city.risk_score ?? city.total_risk_score ?? 0;
                item.classList.remove('loading', 'risk-low', 'risk-mid', 'risk-high');
                item.classList.add(getRiskLevelClass(score));
                const valEl = item.querySelector('.risk-value');
                if (valEl) valEl.textContent = getRiskLabel(score);
            }
        });
    }

    function addCityHeatmapOverlay(cityRisks) {
        if (!mymap || !cityRisks) return;
        if (cityHeatmapLayer) {
            mymap.removeLayer(cityHeatmapLayer);
            cityHeatmapLayer = null;
        }
        const layer = L.layerGroup();
        const list = Array.isArray(cityRisks) ? cityRisks : Object.values(cityRisks || {});
        for (const data of list) {
            const cityName = data.city || data.name;
            const lat = data.lat, lon = data.lon;
            if (lat == null || lon == null) continue;
            const score = data.risk_score ?? data.total_risk_score ?? 0;
            let color = '#2ecc71';
            if (score >= 70) color = '#e74c3c';
            else if (score >= 30) color = '#f39c12';
            const radius = 15000 + Math.min(score * 800, 50000);
            L.circle([lat, lon], {
                radius,
                color,
                fillColor: color,
                fillOpacity: 0.25,
                weight: 2
            }).bindPopup(`<b>${cityName}</b><br>Risk: ${getRiskLabel(score)} (${score.toFixed(0)}/100)`).addTo(layer);
        }
        layer.addTo(mymap);
        cityHeatmapLayer = layer;
    }

    let m5MarkerLayer = null;
    function addM5MarkersToMap(m5Cities) {
        if (!mymap || !cityRiskData || !m5Cities || m5Cities.length === 0) return;
        if (m5MarkerLayer) { mymap.removeLayer(m5MarkerLayer); m5MarkerLayer = null; }
        const byCity = {};
        cityRiskData.forEach(c => { byCity[c.city] = c; });
        m5MarkerLayer = L.layerGroup();
        m5Cities.forEach(cityName => {
            const c = byCity[cityName];
            if (c && c.lat != null && c.lon != null) {
                L.circleMarker([c.lat, c.lon], { radius: 14, color: '#e74c3c', fillColor: '#e74c3c', fillOpacity: 0.8, weight: 3 })
                    .bindPopup(`<b>🚨 M≥5 Risk</b><br>${cityName}`).addTo(m5MarkerLayer);
            }
        });
        m5MarkerLayer.addTo(mymap);
    }

    function fetchCityRiskAndHeatmap() {
        fetch(`${RENDER_API_BASE_URL}/api/city-damage-analysis`, { method: 'GET', headers: { 'Content-Type': 'application/json' }, mode: 'cors' })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (data && data.city_risks) {
                cityRiskData = data.city_risks;
                updateRiskMeter(cityRiskData);
                addCityHeatmapOverlay(cityRiskData);
                renderCityList(document.getElementById('citySearch')?.value || '');
                fetch(`${RENDER_API_BASE_URL}/api/turkey-early-warning`, { method: 'GET', mode: 'cors' })
                    .then(r2 => r2.ok ? r2.json() : null)
                    .then(m5 => {
                        if (m5 && m5.active_warnings) addM5MarkersToMap(Object.keys(m5.active_warnings));
                    }).catch(() => {});
            }
        })
        .catch(() => {});
    }

    function renderCityList(filter = '') {
        if (!cityListEl || !cityRiskData) return;
        const q = (filter || '').toLowerCase().trim();
        let list = cityRiskData;
        if (q) list = list.filter(c => (c.city || '').toLowerCase().includes(q));
        if (list.length === 0) {
            cityListEl.innerHTML = '<p class="loading">Aranan kriterde il bulunamadı.</p>';
            return;
        }
        cityListEl.innerHTML = list.map(c => {
            const s = c.risk_score ?? c.total_risk_score ?? 0;
            const cls = s >= 50 ? 'risk-high' : s >= 30 ? 'risk-mid' : 'risk-low';
            return `<div class="city-item ${cls}"><span>${c.city}</span><span>${(c.risk_level || getRiskLabel(s))} (${s.toFixed(0)})</span></div>`;
        }).join('');
    }

    function fetchData() {
        fetchRiskData();
        fetchCityRiskAndHeatmap();
        fetchM5AndAnomaly();
        fetchMetrics();
    }

    function fetchM5AndAnomaly() {
        fetch(`${RENDER_API_BASE_URL}/api/turkey-early-warning`, { method: 'GET', mode: 'cors' })
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (m5ListEl) {
                    if (!data || data.status === 'error') m5ListEl.innerHTML = '<p class="loading">Yüklenemedi.</p>';
                    else {
                        const active = data.active_warnings || {};
                        const arr = Object.entries(active);
                        if (arr.length === 0) m5ListEl.innerHTML = '<p style="color:#2ecc71;">✅ M≥5 risk tespit edilmedi.</p>';
                        else m5ListEl.innerHTML = arr.map(([city, w]) =>
                            `<div class="m5-item"><strong>${city}</strong> - ${w.alert_level} (M${w.predicted_magnitude || '?'}) - ${w.message}</div>`
                        ).join('');
                    }
                }
            })
            .catch(() => { if (m5ListEl) m5ListEl.innerHTML = '<p class="loading">Bağlantı hatası.</p>'; });

        fetch(`${RENDER_API_BASE_URL}/api/istanbul-early-warning`, { method: 'GET', mode: 'cors' })
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (anomalyEl) {
                    if (!data) anomalyEl.innerHTML = '<p class="loading">Analiz yapılamadı.</p>';
                    else anomalyEl.innerHTML = `<p>Anomali: <strong>${data.anomaly_detected ? '✅ Tespit edildi' : '❌ Yok'}</strong></p><p>Skor: ${data.alert_score || 0}/1.0 · ${data.message || ''}</p>`;
                }
            })
            .catch(() => { if (anomalyEl) anomalyEl.innerHTML = '<p class="loading">Bağlantı hatası.</p>'; });
    }

    function fetchMetrics() {
        if (!metricsEl) return;
        metricsEl.innerHTML = `
            <div class="metric-row"><span>Deprem sayısı (24h)</span><span>Risk artışı</span></div>
            <div class="metric-row"><span>Maksimum büyüklük</span><span>Yüksek M = yüksek risk</span></div>
            <div class="metric-row"><span>En yakın deprem mesafesi</span><span>Yakın = risk artar</span></div>
            <div class="metric-row"><span>Fay hattı mesafesi</span><span>Yakın fay = risk artar</span></div>
            <div class="metric-row"><span>Aktivite yoğunluğu</span><span>Yoğunluk = risk artar</span></div>
        `;
    }

    document.getElementById('citySearch')?.addEventListener('input', (e) => renderCityList(e.target.value));

    // Konum Alma Fonksiyonu
    getLocationButton.addEventListener('click', () => {
        if (!navigator.geolocation) {
            locationStatus.textContent = 'Hata: Tarayıcınız konum servisini desteklemiyor.';
            return;
        }

        locationStatus.textContent = 'Konumunuz tespit ediliyor...';

        navigator.geolocation.getCurrentPosition(position => {
            userCoords = {
                lat: position.coords.latitude,
                lon: position.coords.longitude
            };
            locationStatus.innerHTML = `✅ Konum Tespit Edildi!<br>Enlem: ${userCoords.lat.toFixed(4)}, Boylam: ${userCoords.lon.toFixed(4)}`;
        }, error => {
            locationStatus.textContent = `Hata: Konum izni verilmedi veya hata oluştu. (${error.message})`;
            userCoords = null;
        });
    });

    // Ayarları Kaydetme (Backend'e POST) Fonksiyonu
    saveSettingsButton.addEventListener('click', () => {
        const number = numberInput.value; 
        
        if (!userCoords) {
            alert('Lütfen önce "Konumumu Otomatik Belirle" butonuna basarak konumunuzu tespit edin.');
            return;
        }
        if (!number || !number.startsWith('+')) { 
            alert('Lütfen geçerli bir telefon numarası (ülke kodu ile, Örn: +905xxxxxxxx) girin.');
            return;
        }
        
        // Mutlak URL ile POST isteği gönderiliyor.
        fetch(`${RENDER_API_BASE_URL}/api/set-alert`, {
            mode: 'cors',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                lat: userCoords.lat,
                lon: userCoords.lon,
                number: number 
            }),
        })
        .then(response => {
            // 404/Ağ hatalarını yakalar
            if (!response.ok) { 
                 throw new Error(`Sunucu Hatası: ${response.status}. Render loglarını kontrol edin.`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                // Başarı mesajı + Sandbox rehberi
                locationStatus.innerHTML = `
                    <div style="background-color: rgba(46, 204, 113, 0.2); border: 2px solid #2ecc71; color: #2ecc71; padding: 15px; border-radius: 8px; margin-top: 10px;">
                        <p style="margin: 0; font-weight: 600;">✅ ${data.message}</p>
                        <div style="margin-top: 15px; padding: 10px; background-color: rgba(255, 193, 7, 0.2); border-radius: 5px;">
                            <p style="margin: 5px 0; font-size: 0.9em; color: #FFC107;">
                                ⚠️ <strong>ÖNEMLİ - WhatsApp Sandbox'a Katılın (ÜCRETSİZ):</strong>
                            </p>
                            <p style="margin: 5px 0; font-size: 0.85em;">
                                Bildirim alabilmek için numaranızı Twilio WhatsApp Sandbox'a eklemeniz gerekiyor. Bu işlem <strong>ücretsizdir</strong> ve sadece bir kez yapılır.
                            </p>
                            <ol style="margin: 10px 0; padding-left: 20px; font-size: 0.85em;">
                                <li><a href="https://console.twilio.com" target="_blank" style="color: #FFC107;">Twilio Console</a>'a gidin</li>
                                <li><strong>Messaging</strong> > <strong>Try it out</strong> > <strong>Send a WhatsApp message</strong></li>
                                <li><strong>"Join code"</strong> kısmındaki kodu kopyalayın (örn: <code>join abc-xyz</code>)</li>
                                <li>WhatsApp'tan <strong>+1 415 523 8886</strong> numarasına bu kodu gönderin</li>
                                <li>Onay mesajı gelecek: <strong>"You're all set!"</strong></li>
                            </ol>
                            <p style="margin: 10px 0 0 0; font-size: 0.8em; color: var(--color-light-text);">
                                💡 Bu işlem sadece bir kez yapılır. Sandbox'a katıldıktan sonra tüm bildirimleri alabilirsiniz!
                            </p>
                        </div>
                    </div>
                `;
                numberInput.value = '';
            } else {
                locationStatus.innerHTML = `<p style="color: #FF1744;">❌ Hata: ${data.message || 'Bildirim ayarları kaydedilemedi'}</p>`;
            }
        })
        .catch(error => {
            console.error('Ayarlar kaydedilirken hata:', error);
            locationStatus.innerHTML = `<p style="color: #FF1744;">⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.</p>`;
        });
    });

    // Meta WhatsApp Opt-In Link
    if (getOptInLinkButton) {
        getOptInLinkButton.addEventListener('click', () => {
            getOptInLinkButton.disabled = true;
            getOptInLinkButton.textContent = '⏳ Link Yükleniyor...';
            
            fetch(`${RENDER_API_BASE_URL}/api/get-opt-in-link`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
                mode: 'cors'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                getOptInLinkButton.disabled = false;
                getOptInLinkButton.textContent = '🔗 Session Açma Linkini Al';
                
                if (data.success && data.opt_in_link) {
                    if (optInLink) { optInLink.href = data.opt_in_link; optInLink.textContent = data.opt_in_link; }
                    if (optInLinkDisplay) optInLinkDisplay.style.display = 'block';
                    
                    // Modal ile detaylı talimatlar göster
                    const instructions = data.instructions ? data.instructions.map(step => `<li style="margin: 8px 0; text-align: left;">${step}</li>`).join('') : '';
                    openModal('📱 WhatsApp Session Açma (Opt-In)', `
                        <div style="text-align: center; padding: 20px;">
                            <h3 style="margin-bottom: 20px; color: #ffffff;">Session Açın ve Bildirimleri Alın</h3>
                            <div style="background: rgba(46, 204, 113, 0.2); border: 2px solid #2ecc71; border-radius: 15px; padding: 20px; margin: 20px 0;">
                                <p style="margin: 0 0 15px 0; color: #2ecc71; font-weight: 600; font-size: 1.1em;">
                                    ✅ Bu işlem sadece bir kez yapılır!
                                </p>
                                <a href="${data.opt_in_link}" target="_blank" style="display: inline-block; background: #2ecc71; color: white; padding: 15px 30px; border-radius: 10px; text-decoration: none; font-weight: 600; margin: 10px 0;">
                                    🔗 WhatsApp'ta Aç ve "basla" Yaz
                                </a>
                            </div>
                            ${instructions ? `
                                <div style="background: rgba(52, 73, 94, 0.3); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin: 20px 0; text-align: left;">
                                    <h4 style="margin: 0 0 15px 0; color: #ffffff; font-size: 1.1em;">📋 Adım Adım:</h4>
                                    <ol style="margin: 0; padding-left: 20px; color: rgba(255, 255, 255, 0.9); line-height: 1.8;">
                                        ${instructions}
                                    </ol>
                                </div>
                            ` : ''}
                            <div style="background: rgba(243, 156, 18, 0.2); border: 1px solid #f39c12; border-radius: 10px; padding: 15px; margin: 20px 0;">
                                <p style="margin: 0; color: #f39c12; font-size: 0.95em;">
                                    ⚠️ ÖNEMLİ: Session açtıktan sonra 24 saat boyunca serbest metin bildirimleri alabilirsiniz!
                                </p>
                                <p style="margin: 10px 0 0 0; color: rgba(243, 156, 18, 0.9); font-size: 0.85em;">
                                    💡 24 saat sonra tekrar session açmanız gerekebilir (Meta WhatsApp kuralları).
                                </p>
                            </div>
                        </div>
                    `);
                } else {
                    openModal('📱 Opt-In Link Hatası', `
                        <div style="text-align: center; padding: 20px;">
                            <p style="color: #FF1744;">${data.message || 'Opt-in linki alınamadı.'}</p>
                            <p style="color: rgba(255, 255, 255, 0.7); font-size: 0.9em; margin-top: 10px;">
                                Meta WhatsApp API ayarları yapılmamış olabilir.
                            </p>
                        </div>
                    `);
                }
            })
            .catch(error => {
                console.error('Opt-in link hatası:', error);
                getOptInLinkButton.disabled = false;
                getOptInLinkButton.textContent = '🔗 Session Açma Linkini Al';
                openModal('📱 Opt-In Link Hatası', `
                    <div style="text-align: center; padding: 20px;">
                        <p style="color: #FF1744;">Opt-in linki alınamadı.</p>
                        <p style="color: rgba(255, 255, 255, 0.7); font-size: 0.9em; margin-top: 10px;">
                            Hata: ${error.message}
                        </p>
                    </div>
                `);
            });
        });
    }

    // Manuel hasar tahmini kaldırıldı - otomatik il bazında analiz kullanılıyor
    
    // Risk Tahmini
    predictRiskButton.addEventListener('click', () => {
        if (!userCoords) {
            openModal('🔮 AI Risk Tahmini', '<div style="text-align: center; padding: 20px; color: #FF1744;"><p>⚠️ Lütfen önce "Konumumu Otomatik Belirle" butonuna basarak konumunuzu tespit edin.</p></div>');
            return;
        }
        
        openModal('🔮 AI Risk Tahmini', '<div style="text-align: center; padding: 40px;"><div class="loading"></div><p style="margin-top: 20px;">Risk tahmini yapılıyor...</p><p style="font-size: 0.85em; opacity: 0.7; margin-top: 10px;">İlk istek 50-60 saniye sürebilir (sunucu uyandırılıyor).</p></div>');
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 90000); // 90 saniye timeout
        
        fetch(`${RENDER_API_BASE_URL}/api/predict-risk`, {
            mode: 'cors',
            method: 'POST',
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                lat: userCoords.lat,
                lon: userCoords.lon,
                use_ml: true
            }),
        })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`Sunucu hatası: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                openModal('🔮 AI Risk Tahmini', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>Hata: ${data.error}</p></div>`);
                return;
            }
            
            if (data.risk_score === undefined) {
                openModal('🔮 AI Risk Tahmini', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>Hata: Geçersiz veri formatı.</p></div>`);
                return;
            }
            
            let riskColor = '#2ecc71';
            if (data.risk_score >= 7.0) riskColor = '#e74c3c';
            else if (data.risk_score >= 5.0) riskColor = '#e67e22';
            else if (data.risk_score >= 3.0) riskColor = '#f39c12';
            
            let detailsHtml = '';
            if (data.method === 'ml_ensemble' && data.features) {
                detailsHtml = `
                    <div style="background: rgba(0, 0, 0, 0.2); border-radius: 15px; padding: 20px; margin-top: 20px;">
                        <p style="margin: 0 0 15px 0; font-size: 1.1em; font-weight: 600;">🤖 ML Model Tahminleri:</p>
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
                            ${data.model_predictions ? `
                                <div style="text-align: center; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 10px;">
                                    <p style="margin: 0; font-size: 0.85em; opacity: 0.8;">Random Forest</p>
                                    <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: 700;">${data.model_predictions.random_forest || 'N/A'}/10</p>
                                </div>
                                <div style="text-align: center; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 10px;">
                                    <p style="margin: 0; font-size: 0.85em; opacity: 0.8;">XGBoost</p>
                                    <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: 700;">${data.model_predictions.xgboost || 'N/A'}/10</p>
                                </div>
                                <div style="text-align: center; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 10px;">
                                    <p style="margin: 0; font-size: 0.85em; opacity: 0.8;">LightGBM</p>
                                    <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: 700;">${data.model_predictions.lightgbm || 'N/A'}/10</p>
                                </div>
                            ` : ''}
                        </div>
                        <p style="margin: 15px 0 10px 0; font-size: 1em; font-weight: 600;">📊 Özellikler:</p>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.9em;">
                            <p style="margin: 5px 0;">• Toplam Deprem: <strong>${data.features.count || 0}</strong></p>
                            <p style="margin: 5px 0;">• Maksimum Büyüklük: <strong>M${data.features.max_magnitude?.toFixed(1) || 'N/A'}</strong></p>
                            <p style="margin: 5px 0;">• En Yakın Mesafe: <strong>${data.features.min_distance?.toFixed(1) || 'N/A'} km</strong></p>
                            <p style="margin: 5px 0;">• Aktivite Yoğunluğu: <strong>${data.features.activity_density?.toFixed(4) || 'N/A'}</strong></p>
                        </div>
                        ${data.anomaly ? `
                            <div style="margin-top: 20px; padding: 15px; background: rgba(243, 156, 18, 0.2); border-left: 4px solid #f39c12; border-radius: 10px;">
                                <p style="margin: 0 0 10px 0; font-size: 1em; font-weight: 600;">⚠️ Anomali Tespiti:</p>
                                <p style="margin: 5px 0; font-size: 0.9em;">Anomali Skoru: <strong>${data.anomaly.anomaly_score || 0}/1.0</strong></p>
                                <p style="margin: 5px 0; font-size: 0.9em;">Tespit Edildi: <strong>${data.anomaly.anomaly_detected ? '✅ Evet' : '❌ Hayır'}</strong></p>
                            </div>
                        ` : ''}
                    </div>
                `;
            } else if (data.factors) {
                detailsHtml = `
                    <div style="background: rgba(0, 0, 0, 0.2); border-radius: 15px; padding: 20px; margin-top: 20px;">
                        <p style="margin: 0 0 15px 0; font-size: 1em; font-weight: 600;">📊 Detaylar:</p>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.9em;">
                            <p style="margin: 5px 0;">• En Büyük Deprem: <strong>M${data.factors.max_magnitude || 'N/A'}</strong></p>
                            <p style="margin: 5px 0;">• Son 24 Saatteki: <strong>${data.factors.recent_count || 0}</strong></p>
                            <p style="margin: 5px 0;">• Ortalama Mesafe: <strong>${data.factors.avg_distance || 'N/A'} km</strong></p>
                            <p style="margin: 5px 0;">• En Yakın Fay: <strong>${data.factors.nearest_fault_km || 'N/A'} km</strong></p>
                        </div>
                    </div>
                `;
            }
            
            openModal('🔮 AI Risk Tahmini', `
                <div style="background: linear-gradient(135deg, ${riskColor} 0%, ${riskColor}dd 100%); border-radius: 20px; padding: 30px; text-align: center; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 15px 0; font-size: 2rem; font-weight: 800;">Risk Seviyesi: ${data.risk_level || 'Bilinmiyor'}</h3>
                    <div style="font-size: 3rem; font-weight: 900; margin: 20px 0;">${data.risk_score || 0}/10</div>
                    <p style="margin: 10px 0; font-size: 1.1em; opacity: 0.95;">${data.method === 'ml_ensemble' ? '🤖 Gelişmiş ML (Ensemble)' : (data.method === 'traditional' ? '📊 Geleneksel' : '📊 Standart')}</p>
                    ${data.reason ? `<p style="margin: 15px 0 0 0; font-size: 1em; opacity: 0.9;">${data.reason}</p>` : ''}
                </div>
                ${detailsHtml}
            `);
        })
        .catch(error => {
            clearTimeout(timeoutId);
            console.error('Risk tahmini hatası:', error);
            const isTimeout = error.name === 'AbortError';
            const msg = isTimeout
                ? '⏱️ İstek zaman aşımına uğradı. Önce haritanın yüklenmesini bekleyin, sonra tekrar deneyin.'
                : '⚠️ Sunucuya bağlanılamadı. Önce haritanın yüklenmesini bekleyin, sonra tekrar deneyin. Sunucu uyku modundaysa 15-20 saniye sürebilir.';
            openModal('🔮 AI Risk Tahmini', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>${msg}</p></div>`);
        });
    });
    
    // İl Bazında Hasar Analizi
    analyzeCityDamageButton.addEventListener('click', () => {
        openModal('🏙️ İl Bazında Risk Analizi', '<div style="text-align: center; padding: 40px;"><div class="loading"></div><p style="margin-top: 20px;">İl bazında hasar analizi yapılıyor...</p></div>');
        
        fetch(`${RENDER_API_BASE_URL}/api/city-damage-analysis`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            mode: 'cors'
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    openModal('🏙️ İl Bazında Risk Analizi', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>Hata: ${data.error}</p></div>`);
                    return;
                }
                
                if (data.status === 'error' || !data.city_risks || data.city_risks.length === 0) {
                    openModal('🏙️ İl Bazında Risk Analizi', `
                        <div style="background: linear-gradient(135deg, rgba(46, 204, 113, 0.2) 0%, rgba(39, 174, 96, 0.2) 100%); border: 2px solid #2ecc71; border-radius: 15px; padding: 25px; text-align: center;">
                            <h3 style="margin: 0 0 15px 0; color: #2ecc71; font-size: 1.5rem;">✅ İyi Haber!</h3>
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.9); font-size: 1.1em;">${data.message}</p>
                        </div>
                    `);
                    return;
                }
                
                let html = `
                    <div style="background: linear-gradient(135deg, rgba(52, 73, 94, 0.3) 0%, rgba(44, 62, 80, 0.3) 100%); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 15px 0; color: #ffffff; font-size: 1.3rem;">📊 Analiz Sonuçları</h3>
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                            <div style="text-align: center;">
                                <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">Toplam Deprem</p>
                                <p style="margin: 5px 0 0 0; font-size: 1.5em; font-weight: 700; color: #FF1744;">${data.total_earthquakes}</p>
                            </div>
                            <div style="text-align: center;">
                                <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">Analiz Edilen İl</p>
                                <p style="margin: 5px 0 0 0; font-size: 1.5em; font-weight: 700; color: #9D4EDD;">${data.analyzed_cities}</p>
                            </div>
                            <div style="text-align: center;">
                                <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">Risk Durumu</p>
                                <p style="margin: 5px 0 0 0; font-size: 1.5em; font-weight: 700; color: #00E5FF;">Aktif</p>
                            </div>
                        </div>
                    </div>
                    <div style="max-height: 60vh; overflow-y: auto; padding-right: 10px;">
                `;
                
                data.city_risks.forEach((city, index) => {
                    let levelColor = '#95a5a6';
                    if (city.risk_score >= 70) levelColor = '#e74c3c';
                    else if (city.risk_score >= 50) levelColor = '#e67e22';
                    else if (city.risk_score >= 30) levelColor = '#f39c12';
                    else if (city.risk_score >= 15) levelColor = '#3498db';
                    
                    html += `
                        <div style="background: linear-gradient(135deg, ${levelColor} 0%, ${levelColor}dd 100%); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 15px; padding: 20px; margin-bottom: 15px; backdrop-filter: blur(10px);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                                <h4 style="margin: 0; font-size: 1.3em; font-weight: 700;">${index + 1}. ${city.city}</h4>
                                <div style="background: rgba(0, 0, 0, 0.3); padding: 8px 15px; border-radius: 20px; font-weight: 700; font-size: 1.1em;">${city.risk_score.toFixed(1)}/100</div>
                            </div>
                            <p style="margin: 0 0 15px 0; font-size: 1.1em; font-weight: 600;">Seviye: ${city.risk_level}</p>
                            <p style="margin: 0 0 15px 0; font-size: 0.95em; opacity: 0.95;">${city.description}</p>
                            <div style="background: rgba(0, 0, 0, 0.2); border-radius: 10px; padding: 15px; margin-top: 15px;">
                                <p style="margin: 0 0 10px 0; font-size: 0.95em; font-weight: 600;">📊 Risk Faktörleri:</p>
                                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.85em;">
                                    <p style="margin: 5px 0;">• Deprem Riski: <strong>${city.factors.earthquake_risk.toFixed(1)}</strong></p>
                                    <p style="margin: 5px 0;">• Fay Hattı Riski: <strong>${city.factors.fault_risk.toFixed(1)}</strong></p>
                                    <p style="margin: 5px 0;">• Aktivite Skoru: <strong>${city.factors.activity_score.toFixed(1)}</strong></p>
                                    <p style="margin: 5px 0;">• En Yakın Fay: <strong>${city.factors.nearest_fault_distance.toFixed(1)} km</strong></p>
                                </div>
                                ${city.building_risk_analysis ? `
                                    <div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid rgba(255,255,255,0.3);">
                                        <p style="margin: 0 0 10px 0; font-size: 0.95em; font-weight: 600;">🏗️ Bina Risk Analizi:</p>
                                        <p style="margin: 5px 0; font-size: 0.9em;">Hasar Skoru: <strong>${city.building_risk_analysis.damage_score}/100</strong> - ${city.building_risk_analysis.damage_level}</p>
                                        <p style="margin: 5px 0; font-size: 0.85em; opacity: 0.9;">${city.building_risk_analysis.damage_description}</p>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
                openModal('🏙️ İl Bazında Risk Analizi', html);
            })
            .catch(error => {
                console.error('İl bazında risk analizi hatası:', error);
                openModal('🏙️ İl Bazında Risk Analizi', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.</p></div>`);
            });
    });
    
    // Tüm Türkiye Erken Uyarı Sistemi
    const checkTurkeyWarningButton = document.getElementById('checkTurkeyWarningButton');
    const turkeyWarningResult = document.getElementById('turkeyWarningResult');
    
    if (checkTurkeyWarningButton) {
        checkTurkeyWarningButton.addEventListener('click', () => {
            openModal('🇹🇷 Tüm Türkiye Erken Uyarı Sistemi', '<div style="text-align: center; padding: 40px;"><div class="loading"></div><p style="margin-top: 20px;">Tüm Türkiye erken uyarı durumu kontrol ediliyor...</p></div>');
            
            fetch(`${RENDER_API_BASE_URL}/api/turkey-early-warning`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                mode: 'cors'
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'error') {
                        openModal('🇹🇷 Tüm Türkiye Erken Uyarı Sistemi', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>Hata: ${data.message || 'Bilinmeyen hata'}</p></div>`);
                        return;
                    }
                    
                    let html = `
                        <div style="background: linear-gradient(135deg, rgba(52, 73, 94, 0.3) 0%, rgba(44, 62, 80, 0.3) 100%); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px;">
                            <h3 style="margin: 0 0 15px 0; color: #ffffff; font-size: 1.3rem;">📊 Analiz Sonuçları</h3>
                            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                                <div style="text-align: center; padding: 15px; background: rgba(255, 255, 255, 0.05); border-radius: 10px;">
                                    <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">Analiz Edilen İl</p>
                                    <p style="margin: 5px 0 0 0; font-size: 1.8em; font-weight: 700; color: #9D4EDD;">${data.total_cities_analyzed}</p>
                                </div>
                                <div style="text-align: center; padding: 15px; background: rgba(255, 255, 255, 0.05); border-radius: 10px;">
                                    <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">Uyarı Veren İl</p>
                                    <p style="margin: 5px 0 0 0; font-size: 1.8em; font-weight: 700; color: #FF1744;">${data.cities_with_warnings}</p>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    if (data.cities_with_warnings === 0) {
                        html += `
                            <div style="background: linear-gradient(135deg, rgba(46, 204, 113, 0.3) 0%, rgba(39, 174, 96, 0.3) 100%); border: 2px solid #2ecc71; border-radius: 20px; padding: 30px; text-align: center;">
                                <h3 style="margin: 0 0 15px 0; color: #2ecc71; font-size: 1.8rem;">✅ İyi Haber!</h3>
                                <p style="margin: 0; color: rgba(255, 255, 255, 0.95); font-size: 1.1em;">Şu anda tüm Türkiye'de M ≥ 5.0 deprem riski tespit edilmedi.</p>
                            </div>
                        `;
                    } else {
                        html += '<div style="max-height: 60vh; overflow-y: auto; padding-right: 10px;">';
                        
                        Object.entries(data.active_warnings || {}).forEach(([city, warning]) => {
                            let alertColor = '#2ecc71';
                            if (warning.alert_level === 'KRİTİK') alertColor = '#e74c3c';
                            else if (warning.alert_level === 'YÜKSEK') alertColor = '#e67e22';
                            else if (warning.alert_level === 'ORTA') alertColor = '#f39c12';
                            
                            html += `
                                <div style="background: linear-gradient(135deg, ${alertColor} 0%, ${alertColor}dd 100%); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 15px; padding: 20px; margin-bottom: 15px; backdrop-filter: blur(10px);">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                                        <h4 style="margin: 0; font-size: 1.4em; font-weight: 700;">🚨 ${city.toUpperCase()}</h4>
                                        <div style="background: rgba(0, 0, 0, 0.3); padding: 8px 15px; border-radius: 20px; font-weight: 700;">${warning.alert_level}</div>
                                    </div>
                                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 15px;">
                                        <div>
                                            <p style="margin: 0; font-size: 0.9em; opacity: 0.9;">Tahmini Büyüklük</p>
                                            <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: 700;">M${warning.predicted_magnitude || 'N/A'}</p>
                                        </div>
                                        <div>
                                            <p style="margin: 0; font-size: 0.9em; opacity: 0.9;">Uyarı Skoru</p>
                                            <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: 700;">${warning.alert_score}/1.0</p>
                                        </div>
                                    </div>
                                    <p style="margin: 0 0 15px 0; font-size: 1.1em; font-weight: 600;">Tahmini Süre: ${warning.time_to_event || 'Bilinmiyor'}</p>
                                    <p style="margin: 0 0 15px 0; font-size: 0.95em; opacity: 0.95;">${warning.message}</p>
                                    <div style="background: rgba(0, 0, 0, 0.2); border-radius: 10px; padding: 15px;">
                                        <p style="margin: 0 0 10px 0; font-size: 0.9em; font-weight: 600;">📊 Detaylar:</p>
                                        <p style="margin: 5px 0; font-size: 0.85em;">• Son deprem sayısı: <strong>${warning.recent_earthquakes}</strong></p>
                                        <p style="margin: 5px 0; font-size: 0.85em;">• Anomali tespit edildi: <strong>${warning.anomaly_detected ? '✅ Evet' : '❌ Hayır'}</strong></p>
                                    </div>
                                </div>
                            `;
                        });
                        
                        html += '</div>';
                    }
                    
                    openModal('🇹🇷 Tüm Türkiye Erken Uyarı Sistemi', html);
                })
                .catch(error => {
                    console.error('Türkiye erken uyarı hatası:', error);
                    openModal('🇹🇷 Tüm Türkiye Erken Uyarı Sistemi', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.</p></div>`);
                });
        });
    }

    // İstanbul Erken Uyarı Sistemi
    checkIstanbulWarningButton.addEventListener('click', () => {
        openModal('🏛️ İstanbul Erken Uyarı Sistemi', '<div style="text-align: center; padding: 40px;"><div class="loading"></div><p style="margin-top: 20px;">İstanbul erken uyarı durumu kontrol ediliyor...</p></div>');
        
        fetch(`${RENDER_API_BASE_URL}/api/istanbul-early-warning`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            mode: 'cors'
        })
            .then(response => {
                if (!response.ok) throw new Error(`Sunucu: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.error || data.alert_level === 'HATA') {
                    openModal('🏛️ İstanbul Erken Uyarı Sistemi', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>Hata: ${data.message || data.error || 'Bilinmeyen hata'}</p></div>`);
                    return;
                }
                
                let alertColor = '#2ecc71';
                if (data.alert_level === 'KRİTİK') alertColor = '#e74c3c';
                else if (data.alert_level === 'YÜKSEK') alertColor = '#e67e22';
                else if (data.alert_level === 'ORTA') alertColor = '#f39c12';
                
                openModal('🏛️ İstanbul Erken Uyarı Sistemi', `
                    <div style="background: linear-gradient(135deg, ${alertColor} 0%, ${alertColor}dd 100%); border-radius: 20px; padding: 30px; text-align: center; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 20px 0; font-size: 2.2rem; font-weight: 900;">${data.alert_level} UYARI</h3>
                        <div style="font-size: 3rem; font-weight: 900; margin: 20px 0;">${data.alert_score}/1.0</div>
                        <p style="margin: 15px 0; font-size: 1.2em; font-weight: 600; opacity: 0.95;">${data.message}</p>
                        ${data.time_to_event ? `<p style="margin: 15px 0 0 0; font-size: 1.1em; font-weight: 700;">⏰ Tahmini Süre: ${data.time_to_event}</p>` : ''}
                    </div>
                    <div style="background: rgba(0, 0, 0, 0.2); border-radius: 15px; padding: 20px;">
                        <p style="margin: 0 0 15px 0; font-size: 1.1em; font-weight: 600;">📊 Detaylar:</p>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 15px;">
                            <div style="text-align: center; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 10px;">
                                <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">Son 48 Saatteki Deprem</p>
                                <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: 700;">${data.recent_earthquakes}</p>
                            </div>
                            <div style="text-align: center; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 10px;">
                                <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">Anomali Tespiti</p>
                                <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: 700;">${data.anomaly_detected ? '✅ Evet' : '❌ Hayır'}</p>
                            </div>
                        </div>
                        ${data.features ? `
                            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid rgba(255, 255, 255, 0.2);">
                                <p style="margin: 0 0 15px 0; font-size: 1em; font-weight: 600;">🔍 Özellikler:</p>
                                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; font-size: 0.9em;">
                                    <div style="text-align: center; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 10px;">
                                        <p style="margin: 0; opacity: 0.8;">Maksimum Büyüklük</p>
                                        <p style="margin: 5px 0 0 0; font-weight: 700;">M${data.features.max_magnitude?.toFixed(1) || 'N/A'}</p>
                                    </div>
                                    <div style="text-align: center; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 10px;">
                                        <p style="margin: 0; opacity: 0.8;">Toplam Deprem</p>
                                        <p style="margin: 5px 0 0 0; font-weight: 700;">${data.features.count || 0}</p>
                                    </div>
                                    <div style="text-align: center; padding: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 10px;">
                                        <p style="margin: 0; opacity: 0.8;">En Yakın Mesafe</p>
                                        <p style="margin: 5px 0 0 0; font-weight: 700;">${data.features.min_distance?.toFixed(1) || 'N/A'} km</p>
                                    </div>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                `);
            })
            .catch(error => {
                console.error('İstanbul erken uyarı hatası:', error);
                openModal('🏛️ İstanbul Erken Uyarı Sistemi', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>⚠️ Sunucuya bağlanılamadı.</p><p style="font-size: 0.9em; margin-top: 10px; opacity: 0.9;">Önce haritanın yüklenmesini bekleyin, sonra tekrar deneyin. Sunucu uyku modundaysa 15-20 saniye sürebilir.</p></div>`);
            });
    });

    // İstanbul WhatsApp Bildirim Formu
    const istanbulNumberInput = document.getElementById('istanbulNumberInput');
    const saveIstanbulAlertButton = document.getElementById('saveIstanbulAlertButton');
    const istanbulAlertResult = document.getElementById('istanbulAlertResult');

    if (saveIstanbulAlertButton && istanbulNumberInput && istanbulAlertResult) {
        saveIstanbulAlertButton.addEventListener('click', () => {
            const number = istanbulNumberInput.value.trim();
            
            if (!number) {
                istanbulAlertResult.innerHTML = '<p style="color: #FF1744;">⚠️ Lütfen WhatsApp numaranızı girin.</p>';
                istanbulAlertResult.style.display = 'block';
                return;
            }
            
            if (!number.startsWith('+')) {
                istanbulAlertResult.innerHTML = '<p style="color: #FF1744;">⚠️ Telefon numarası ülke kodu ile başlamalıdır. Örnek: +90532xxxxxxx</p>';
                istanbulAlertResult.style.display = 'block';
                return;
            }
            
            istanbulAlertResult.innerHTML = '<p>İstanbul erken uyarı bildirimleri kaydediliyor...</p>';
            istanbulAlertResult.style.display = 'block';
            saveIstanbulAlertButton.disabled = true;
            saveIstanbulAlertButton.textContent = '⏳ Kaydediliyor...';
            
            fetch(`${RENDER_API_BASE_URL}/api/istanbul-alert`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                mode: 'cors',
                body: JSON.stringify({
                    number: number
                })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        let resultHtml = `
                            <div style="background-color: rgba(46, 204, 113, 0.2); border: 2px solid #2ecc71; color: #2ecc71; padding: 15px; border-radius: 8px;">
                                <p style="margin: 0; font-weight: 600;">✅ ${data.message}</p>
                                <p style="margin: 10px 0 0 0; font-size: 0.9em;">Deprem öncesi sinyaller tespit edildiğinde size WhatsApp ile bildirim gönderilecektir.</p>
                            </div>
                        `;
                        
                        // Eğer uyarı mesajı varsa (örn: HTTP 429 rate limit)
                        if (data.warning) {
                            resultHtml += `
                                <div style="background-color: rgba(255, 193, 7, 0.2); border: 2px solid #FFC107; color: #FFC107; padding: 15px; border-radius: 8px; margin-top: 15px;">
                                    <p style="margin: 0; font-weight: 600;">⚠️ ${data.warning}</p>
                                    ${data.warning.includes('429') || data.warning.includes('limit') ? `
                                        <p style="margin: 10px 0 0 0; font-size: 0.85em; opacity: 0.9;">
                                            💡 <strong>Çözüm:</strong> Twilio ücretsiz planında günlük 50 mesaj limiti vardır. 
                                            Limit yarın sıfırlanacak. Bildirimler kaydedildi, ancak onay mesajı gönderilemedi. 
                                            Sistem normal çalışmaya devam edecek.
                                        </p>
                                    ` : ''}
                                </div>
                            `;
                        }
                        
                        istanbulAlertResult.innerHTML = resultHtml;
                        istanbulNumberInput.value = '';
                    } else {
                        istanbulAlertResult.innerHTML = `<p style="color: #FF1744;">❌ Hata: ${data.message || 'Bildirim kaydedilemedi'}</p>`;
                    }
                    saveIstanbulAlertButton.disabled = false;
                    saveIstanbulAlertButton.textContent = '🔔 İstanbul Erken Uyarı Bildirimlerini Aktifleştir';
                })
                .catch(error => {
                    console.error('İstanbul bildirim hatası:', error);
                    istanbulAlertResult.innerHTML = `<p style="color: #FF1744;">⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.</p>`;
                    saveIstanbulAlertButton.disabled = false;
                    saveIstanbulAlertButton.textContent = '🔔 İstanbul Erken Uyarı Bildirimlerini Aktifleştir';
                });
        });
    }

    refreshButton.addEventListener('click', fetchData);
    
    // İlk yüklemede her iki haritayı da başlat
    fetchData();

    // Chatbot
    const chatbotToggle = document.getElementById('chatbotToggle');
    const chatbotWindow = document.getElementById('chatbotWindow');
    const closeChatbot = document.getElementById('closeChatbot');
    const chatbotMessages = document.getElementById('chatbotMessages');
    const chatbotInput = document.getElementById('chatbotInput');
    const chatbotSend = document.getElementById('chatbotSend');

    if (chatbotToggle && chatbotWindow) chatbotToggle.addEventListener('click', () => chatbotWindow.classList.toggle('active'));
    if (closeChatbot && chatbotWindow) closeChatbot.addEventListener('click', () => chatbotWindow.classList.remove('active'));

    function addMessage(text, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
        messageDiv.innerHTML = `<div class="message-bubble">${text}</div>`;
        chatbotMessages.appendChild(messageDiv);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    function sendChatbotMessage() {
        const message = chatbotInput.value.trim();
        if (!message) return;

        addMessage(message, true);
        chatbotInput.value = '';

        // Loading indicator
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message bot';
        loadingDiv.innerHTML = '<div class="message-bubble"><span class="loading"></span> Düşünüyorum...</div>';
        chatbotMessages.appendChild(loadingDiv);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;

        // Send to backend
        fetch(`${API_URL}/api/chatbot`, {
            mode: 'cors',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            loadingDiv.remove();
            addMessage(data.response || 'Üzgünüm, bir hata oluştu.');
        })
        .catch(error => {
            loadingDiv.remove();
            addMessage('Bağlantı hatası. Lütfen tekrar deneyin.');
            console.error('Chatbot hatası:', error);
        });
    }

    chatbotSend.addEventListener('click', sendChatbotMessage);
    chatbotInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendChatbotMessage();
        }
    });

    // WhatsApp QR kod sistemi kaldırıldı - sadece Twilio kullanılıyor
});