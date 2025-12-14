// script.js
// API URL'ini dinamik olarak belirle
const RENDER_BACKEND_URL = 'https://depremanaliz.onrender.com';

const API_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5000'
    : (window.location.hostname.includes('github.io') 
        ? RENDER_BACKEND_URL  // GitHub Pages'den Render.com backend'e bağlan
        : window.location.origin); // Diğer durumlarda aynı domain'i kullan

let mymap = null; 
let mymap2 = null; 

function initializeMap() {
    if (mymap !== null && mymap._container) {
        mymap.remove();
        mymap = null;
    }
    
    mymap = L.map('mapid').setView([39.9, 35.8], 6); 

    // Koyu tema harita
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors © CARTO'
    }).addTo(mymap);
}

function initializeMap2() {
    if (mymap2 !== null && mymap2._container) {
        mymap2.remove();
        mymap2 = null;
    }
    
    mymap2 = L.map('mapid2').setView([39.9, 35.8], 6); 

    // Koyu tema harita
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors © CARTO'
    }).addTo(mymap2);
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
    
    const listContainer = document.getElementById('earthquake-list');
    const refreshButton = document.getElementById('refreshButton');
    
    const getLocationButton = document.getElementById('getLocationButton');
    const saveSettingsButton = document.getElementById('saveSettingsButton');
    const locationStatus = document.getElementById('locationStatus');
    const numberInput = document.getElementById('numberInput');
    
    // Manuel hasar tahmini kaldırıldı
    // Manuel hasar tahmini kaldırıldı
    const predictRiskButton = document.getElementById('predictRiskButton');
    const riskPredictionResult = document.getElementById('riskPredictionResult');
    const analyzeCityDamageButton = document.getElementById('analyzeCityDamageButton');
    const cityDamageResult = document.getElementById('cityDamageResult');
    const checkIstanbulWarningButton = document.getElementById('checkIstanbulWarningButton');
    const istanbulWarningResult = document.getElementById('istanbulWarningResult');

    let userCoords = null; 

    // İlk harita: Risk Analizi
    function fetchRiskData() {
        listContainer.innerHTML = '<p>YZ risk analizi verileri yükleniyor...</p>';
        initializeMap(); 

        fetch(apiURL, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            mode: 'cors'
        })
            .then(response => {
                if (!response.ok) {
                    if (response.status === 503 || response.status === 502) {
                        listContainer.innerHTML = `<p style="color: #FFA726;">⚠️ Sunucu uyku modunda. Lütfen 10-15 saniye bekleyip sayfayı yenileyin (F5).</p>`;
                        return null;
                    }
                    throw new Error(`Sunucu hatası: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (!data) return; // Uyku modu durumunda çık
                
                listContainer.innerHTML = '';
                let bounds = [];
                
                // Hata kontrolü
                if (data.error) {
                    listContainer.innerHTML = `<p style="color: #FF1744;">Hata: ${data.error}</p>`;
                    return;
                }
                
                // YZ Risk bölgelerini ekle (SADECE RİSK ANALİZİ)
                if (data.risk_regions && data.risk_regions.length > 0) {
                    data.risk_regions.forEach(riskRegion => {
                        const { lat, lon, score, density } = riskRegion;
                        bounds.push([lat, lon]);
                        
                        const color = getRiskColor(score);
                        
                        const marker = L.circleMarker([lat, lon], {
                            radius: score * 1.5, 
                            color: color,
                            fillColor: color,
                            fillOpacity: 0.6,
                            weight: 3
                        }).addTo(mymap);
                        
                        const popupContent = `
                            <b style="color: ${color};">🤖 YZ Risk Merkezi #${riskRegion.id + 1}</b><br>
                            Risk Puanı: <b>${score.toFixed(1)} / 10</b><br>
                            Yoğunluk: ${density} deprem
                        `;
                        marker.bindPopup(popupContent);
                    });
                }
                
                // Veri yoksa mesaj göster
                if (!data.risk_regions || data.risk_regions.length === 0) {
                    listContainer.innerHTML = '<p style="color: #FF1744;">Şu anda yeterli risk analizi verisi yok.</p>';
                }
                
                // Haritayı tüm işaretlere göre ayarla
                if (bounds.length > 0) {
                    mymap.fitBounds(bounds, { padding: [50, 50] });
                } else {
                    mymap.setView([39.9, 35.8], 6);
                }
            })
            .catch(error => {
                console.error('Veri çekme hatası:', error);
                listContainer.innerHTML = `<p style="color: #FF1744;">Hata: YZ sunucusuna bağlanılamadı. (${error.message})</p>`;
            });
    }

    // İkinci harita: Son 1 Gün Depremler + Aktif Fay Hatları
    function fetchEarthquakeData() {
        initializeMap2(); 

        fetch(apiURL, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            mode: 'cors'
        })
            .then(response => {
                if (!response.ok) {
                    if (response.status === 503 || response.status === 502) {
                        console.warn('Sunucu uyku modunda, cache verisi kullanılıyor');
                        return null; // Hata fırlatma, sadece null döndür
                    }
                    throw new Error(`Sunucu hatası: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (!data) {
                    console.warn('Veri alınamadı, harita boş kalabilir');
                    return;
                }
                let bounds = [];
                
                // Hata kontrolü
                if (data.error) {
                    return;
                }
                
                // 1. Aktif fay hatlarını haritaya ekle
                if (data.fault_lines && data.fault_lines.length > 0) {
                    data.fault_lines.forEach(fault => {
                        const faultCoords = fault.coords.map(coord => [coord[0], coord[1]]);
                        const polyline = L.polyline(faultCoords, {
                            color: '#FF1744',  // Kırmızı
                            weight: 4,
                            opacity: 0.8,
                            dashArray: '10, 5'  // Kesikli çizgi
                        }).addTo(mymap2);
                        polyline.bindPopup(`<b style="color: #FF1744;">${fault.name}</b><br>⚠️ Aktif Fay Hattı`);
                        bounds.push(...faultCoords);
                    });
                }
                
                // 2. Son 1 günde olan depremleri haritaya ekle
                if (data.recent_earthquakes && data.recent_earthquakes.length > 0) {
                    data.recent_earthquakes.forEach((eq, index) => {
                        if (eq.geojson && eq.geojson.coordinates) {
                            const [lon, lat] = eq.geojson.coordinates;
                            const mag = eq.mag || 0;
                            const location = eq.location || 'Bilinmiyor';
                            const date = eq.date || '';
                            const time = eq.time || '';
                            
                            bounds.push([lat, lon]);
                            
                            // Büyüklüğe göre renk ve boyut
                            let eqColor = '#2ecc71'; // Yeşil (düşük)
                            let radius = 5;
                            if (mag >= 5.0) {
                                eqColor = '#FF1744'; // Kırmızı (yüksek)
                                radius = 12;
                            } else if (mag >= 4.0) {
                                eqColor = '#f39c12'; // Turuncu (orta)
                                radius = 8;
                            } else if (mag >= 3.0) {
                                eqColor = '#3498db'; // Mavi (düşük-orta)
                                radius = 6;
                            }
                            
                            // Deprem marker'ı
                            const eqMarker = L.circleMarker([lat, lon], {
                                radius: radius,
                                color: '#000',
                                fillColor: eqColor,
                                fillOpacity: 0.8,
                                weight: 2
                            }).addTo(mymap2);
                            
                            const popupContent = `
                                <b>📍 Deprem #${index + 1}</b><br>
                                <b>Büyüklük: M${mag.toFixed(1)}</b><br>
                                Konum: ${location}<br>
                                Tarih: ${date} ${time}<br>
                                Derinlik: ${eq.depth || 'N/A'} km
                            `;
                            eqMarker.bindPopup(popupContent);
                        }
                    });
                }
                
                // Haritayı tüm işaretlere göre ayarla
                if (bounds.length > 0) {
                    mymap2.fitBounds(bounds, { padding: [50, 50] });
                } else {
                    mymap2.setView([39.9, 35.8], 6);
                }
            })
            .catch(error => {
                console.error('Veri çekme hatası:', error);
                listContainer.innerHTML = `<p style="color: #FF1744;">⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip sayfayı yenileyin (F5).</p>`;
            });
    }

    function fetchData() {
        fetchRiskData();
        fetchEarthquakeData();
    } 

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


    // Manuel hasar tahmini kaldırıldı - otomatik il bazında analiz kullanılıyor
    
    // Risk Tahmini
    predictRiskButton.addEventListener('click', () => {
        if (!userCoords) {
            openModal('🔮 AI Risk Tahmini', '<div style="text-align: center; padding: 20px; color: #FF1744;"><p>⚠️ Lütfen önce "Konumumu Otomatik Belirle" butonuna basarak konumunuzu tespit edin.</p></div>');
            return;
        }
        
        openModal('🔮 AI Risk Tahmini', '<div style="text-align: center; padding: 40px;"><div class="loading"></div><p style="margin-top: 20px;">Risk tahmini yapılıyor...</p></div>');
        
        fetch(`${RENDER_API_BASE_URL}/api/predict-risk`, {
            mode: 'cors',
            method: 'POST',
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
            console.error('Risk tahmini hatası:', error);
            openModal('🔮 AI Risk Tahmini', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.</p></div>`);
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
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    openModal('🏛️ İstanbul Erken Uyarı Sistemi', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>Hata: ${data.error}</p></div>`);
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
                openModal('🏛️ İstanbul Erken Uyarı Sistemi', `<div style="color: #FF1744; padding: 20px; text-align: center;"><p>⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.</p></div>`);
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

    chatbotToggle.addEventListener('click', () => {
        chatbotWindow.classList.toggle('active');
    });

    closeChatbot.addEventListener('click', () => {
        chatbotWindow.classList.remove('active');
    });

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
});