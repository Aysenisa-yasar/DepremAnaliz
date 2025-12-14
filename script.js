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

document.addEventListener('DOMContentLoaded', () => {
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
        .then(result => {
            if (result.status === 'success') {
                alert('✅ Bildirim ayarlarınız başarıyla kaydedildi! WhatsApp üzerinden uyarı alacaksınız.');
                locationStatus.innerHTML += `<br>🔔 Bildirimler **${number}** numarasına aktif edildi.`;
            } else {
                alert('Hata: Ayarlar kaydedilirken sunucuda bir sorun oluştu. ' + result.message);
            }
        })
        .catch(error => {
            console.error('Ağ/Sunucu Hatası:', error);
            alert('Bağlantı Hatası: Render sunucunuzun API uç noktasını kontrol edin. (' + error.message + ')');
        });
    });


    // Manuel hasar tahmini kaldırıldı - otomatik il bazında analiz kullanılıyor
    
    // Risk Tahmini
    predictRiskButton.addEventListener('click', () => {
        if (!userCoords) {
            alert('Lütfen önce "Konumumu Otomatik Belirle" butonuna basarak konumunuzu tespit edin.');
            return;
        }
        
        riskPredictionResult.innerHTML = '<p>Risk tahmini yapılıyor...</p>';
        riskPredictionResult.style.display = 'block';
        
        fetch(`${RENDER_API_BASE_URL}/api/predict-risk`, {
            mode: 'cors',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                lat: userCoords.lat,
                lon: userCoords.lon,
                use_ml: true  // Gelişmiş ML modeli kullan
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
                riskPredictionResult.innerHTML = `<p style="color: #FF1744;">Hata: ${data.error}</p>`;
                return;
            }
            
            // Risk skoru kontrolü
            if (data.risk_score === undefined) {
                riskPredictionResult.innerHTML = `<p style="color: #FF1744;">Hata: Geçersiz veri formatı. Sunucu yanıtı beklenmedik formatta.</p>`;
                return;
            }
            
            let riskColor = '#2ecc71'; // Yeşil
            if (data.risk_score >= 7.0) riskColor = '#e74c3c'; // Kırmızı
            else if (data.risk_score >= 5.0) riskColor = '#e67e22'; // Turuncu
            else if (data.risk_score >= 3.0) riskColor = '#f39c12'; // Sarı
            
            let detailsHtml = '';
            if (data.method === 'ml_ensemble' && data.features) {
                detailsHtml = `
                    <p style="margin: 5px 0; font-size: 0.9em;"><strong>🤖 ML Model Tahminleri:</strong></p>
                    ${data.model_predictions ? `
                        <p style="margin: 3px 0; font-size: 0.85em;">Random Forest: ${data.model_predictions.random_forest || 'N/A'}/10</p>
                        <p style="margin: 3px 0; font-size: 0.85em;">XGBoost: ${data.model_predictions.xgboost || 'N/A'}/10</p>
                        <p style="margin: 3px 0; font-size: 0.85em;">LightGBM: ${data.model_predictions.lightgbm || 'N/A'}/10</p>
                    ` : ''}
                    <p style="margin: 10px 0 5px 0; font-size: 0.9em;"><strong>Özellikler:</strong></p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Toplam Deprem: ${data.features.count || 0}</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Maksimum Büyüklük: M${data.features.max_magnitude?.toFixed(1) || 'N/A'}</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">En Yakın Mesafe: ${data.features.min_distance?.toFixed(1) || 'N/A'} km</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Aktivite Yoğunluğu: ${data.features.activity_density?.toFixed(4) || 'N/A'}</p>
                    ${data.anomaly ? `
                        <p style="margin: 10px 0 5px 0; font-size: 0.9em;"><strong>⚠️ Anomali Tespiti:</strong></p>
                        <p style="margin: 3px 0; font-size: 0.85em;">Anomali Skoru: ${data.anomaly.anomaly_score || 0}/1.0</p>
                        <p style="margin: 3px 0; font-size: 0.85em;">Tespit Edildi: ${data.anomaly.anomaly_detected ? '✅ Evet' : '❌ Hayır'}</p>
                    ` : ''}
                `;
            } else if (data.factors) {
                // Geleneksel yöntem (fallback)
                detailsHtml = `
                    <p style="margin: 5px 0; font-size: 0.9em;"><strong>Detaylar:</strong></p>
                    <p style="margin: 3px 0; font-size: 0.85em;">En Büyük Deprem: M${data.factors.max_magnitude || 'N/A'}</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Son 24 Saatteki Deprem Sayısı: ${data.factors.recent_count || 0}</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Ortalama Mesafe: ${data.factors.avg_distance || 'N/A'} km</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">En Yakın Fay Hattı: ${data.factors.nearest_fault_km || 'N/A'} km</p>
                `;
            } else {
                // Veri yoksa minimal bilgi göster
                detailsHtml = `
                    <p style="margin: 5px 0; font-size: 0.9em;"><strong>Bilgi:</strong></p>
                    <p style="margin: 3px 0; font-size: 0.85em;">${data.reason || 'Risk analizi tamamlandı.'}</p>
                `;
            }
            
            riskPredictionResult.innerHTML = `
                <div style="background-color: ${riskColor}; color: white; padding: 15px; border-radius: 8px;">
                    <h3 style="margin: 0 0 10px 0;">Risk Seviyesi: ${data.risk_level || 'Bilinmiyor'}</h3>
                    <p style="margin: 5px 0; font-size: 1.2em;"><strong>Risk Skoru: ${data.risk_score || 0}/10</strong></p>
                    <p style="margin: 5px 0; font-size: 0.9em;">Yöntem: ${data.method === 'ml_ensemble' ? '🤖 Gelişmiş ML (Ensemble)' : (data.method === 'traditional' ? '📊 Geleneksel' : '📊 Standart')}</p>
                    ${data.reason ? `<p style="margin: 10px 0;">${data.reason}</p>` : ''}
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.3);">
                        ${detailsHtml}
                    </div>
                </div>
            `;
        })
        .catch(error => {
            console.error('Risk tahmini hatası:', error);
            riskPredictionResult.innerHTML = `<p style="color: #FF1744;">⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.<br><small>Hata: ${error.message}</small></p>`;
        });
    });
    
    // İl Bazında Hasar Analizi
    analyzeCityDamageButton.addEventListener('click', () => {
        cityDamageResult.innerHTML = '<p>İl bazında hasar analizi yapılıyor...</p>';
        cityDamageResult.style.display = 'block';
        
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
                    cityDamageResult.innerHTML = `<p style="color: red;">Hata: ${data.error}</p>`;
                    return;
                }
                
                if (data.status === 'error' || !data.city_risks || data.city_risks.length === 0) {
                    cityDamageResult.innerHTML = `
                        <div style="background-color: #2ecc71; color: white; padding: 15px; border-radius: 8px;">
                            <h3 style="margin: 0 0 10px 0;">✅ İyi Haber!</h3>
                            <p style="margin: 5px 0;">${data.message}</p>
                        </div>
                    `;
                    return;
                }
                
                let html = `
                    <div style="background-color: #34495e; color: white; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                        <h3 style="margin: 0 0 10px 0;">📊 Analiz Sonuçları</h3>
                        <p style="margin: 5px 0;">Toplam Deprem: <strong>${data.total_earthquakes}</strong></p>
                        <p style="margin: 5px 0;">Analiz Edilen İl Sayısı: <strong>${data.analyzed_cities}</strong></p>
                        <p style="margin: 5px 0; font-size: 0.9em; opacity: 0.9;">📌 Analiz: Son depremler ve aktif fay hatlarına göre risk hesaplandı</p>
                    </div>
                    <div style="max-height: 600px; overflow-y: auto;">
                `;
                
                data.city_risks.forEach((city, index) => {
                    let levelColor = '#95a5a6'; // Gri (minimal)
                    if (city.risk_score >= 70) levelColor = '#e74c3c'; // Kırmızı
                    else if (city.risk_score >= 50) levelColor = '#e67e22'; // Turuncu
                    else if (city.risk_score >= 30) levelColor = '#f39c12'; // Sarı
                    else if (city.risk_score >= 15) levelColor = '#3498db'; // Mavi
                    
                    html += `
                        <div style="background-color: ${levelColor}; color: white; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                            <h4 style="margin: 0 0 10px 0;">${index + 1}. ${city.city}</h4>
                            <p style="margin: 5px 0; font-size: 1.2em;"><strong>Risk Skoru: ${city.risk_score.toFixed(1)}/100</strong></p>
                            <p style="margin: 5px 0;"><strong>Seviye: ${city.risk_level}</strong></p>
                            <p style="margin: 10px 0; font-size: 0.9em;">${city.description}</p>
                            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.3);">
                                <p style="margin: 5px 0; font-size: 0.85em;"><strong>📊 Risk Faktörleri:</strong></p>
                                <p style="margin: 3px 0; font-size: 0.8em;">• Deprem Riski: ${city.factors.earthquake_risk.toFixed(1)} puan</p>
                                <p style="margin: 3px 0; font-size: 0.8em;">• Fay Hattı Riski: ${city.factors.fault_risk.toFixed(1)} puan</p>
                                <p style="margin: 3px 0; font-size: 0.8em;">• Aktivite Skoru: ${city.factors.activity_score.toFixed(1)} puan (${city.factors.earthquake_count} deprem)</p>
                                <p style="margin: 3px 0; font-size: 0.8em;">• En Yakın Fay: ${city.factors.nearest_fault_name || 'Bilinmiyor'} (${city.factors.nearest_fault_distance.toFixed(1)} km)</p>
                                ${city.factors.nearest_earthquake_distance ? `<p style="margin: 3px 0; font-size: 0.8em;">• En Yakın Deprem: ${city.factors.nearest_earthquake_distance.toFixed(1)} km (M${city.factors.max_nearby_magnitude.toFixed(1)})</p>` : '<p style="margin: 3px 0; font-size: 0.8em;">• En Yakın Deprem: 200 km+ (Etki yok)</p>'}
                                ${city.affecting_earthquakes && city.affecting_earthquakes.length > 0 ? `
                                    <p style="margin: 10px 0 5px 0; font-size: 0.85em;"><strong>📍 Etkileyen Depremler:</strong></p>
                                    ${city.affecting_earthquakes.map(eq => `
                                        <p style="margin: 2px 0; font-size: 0.75em;">M${eq.magnitude} - ${eq.location} (${eq.distance} km uzaklıkta)</p>
                                    `).join('')}
                                ` : ''}
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
                cityDamageResult.innerHTML = html;
            })
            .catch(error => {
                console.error('İl bazında risk analizi hatası:', error);
                cityDamageResult.innerHTML = `<p style="color: #FF1744;">⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.</p>`;
            });
    });
    
    // İstanbul Erken Uyarı Sistemi
    checkIstanbulWarningButton.addEventListener('click', () => {
        istanbulWarningResult.innerHTML = '<p>İstanbul erken uyarı durumu kontrol ediliyor...</p>';
        istanbulWarningResult.style.display = 'block';
        
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
                    istanbulWarningResult.innerHTML = `<p style="color: red;">Hata: ${data.error}</p>`;
                    return;
                }
                
                let alertColor = '#2ecc71'; // Yeşil
                if (data.alert_level === 'KRİTİK') alertColor = '#e74c3c'; // Kırmızı
                else if (data.alert_level === 'YÜKSEK') alertColor = '#e67e22'; // Turuncu
                else if (data.alert_level === 'ORTA') alertColor = '#f39c12'; // Sarı
                
                istanbulWarningResult.innerHTML = `
                    <div style="background-color: ${alertColor}; color: white; padding: 20px; border-radius: 8px;">
                        <h3 style="margin: 0 0 15px 0; font-size: 1.5em;">${data.alert_level} UYARI</h3>
                        <p style="margin: 10px 0; font-size: 1.2em;"><strong>Uyarı Skoru: ${data.alert_score}/1.0</strong></p>
                        <p style="margin: 10px 0; font-size: 1.1em;">${data.message}</p>
                        ${data.time_to_event ? `<p style="margin: 10px 0; font-size: 1.0em;"><strong>Tahmini Süre: ${data.time_to_event}</strong></p>` : ''}
                        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.3);">
                            <p style="margin: 5px 0; font-size: 0.9em;"><strong>Detaylar:</strong></p>
                            <p style="margin: 3px 0; font-size: 0.85em;">Son 48 Saatteki Deprem: ${data.recent_earthquakes}</p>
                            <p style="margin: 3px 0; font-size: 0.85em;">Anomali Tespiti: ${data.anomaly_detected ? '✅ Tespit Edildi' : '❌ Yok'}</p>
                            ${data.features ? `
                                <p style="margin: 5px 0; font-size: 0.9em;"><strong>Özellikler:</strong></p>
                                <p style="margin: 3px 0; font-size: 0.8em;">Maksimum Büyüklük: ${data.features.max_magnitude?.toFixed(1) || 'N/A'}</p>
                                <p style="margin: 3px 0; font-size: 0.8em;">Toplam Deprem: ${data.features.count || 0}</p>
                                <p style="margin: 3px 0; font-size: 0.8em;">En Yakın Mesafe: ${data.features.min_distance?.toFixed(1) || 'N/A'} km</p>
                            ` : ''}
                        </div>
                    </div>
                `;
            })
            .catch(error => {
                console.error('İstanbul erken uyarı hatası:', error);
                istanbulWarningResult.innerHTML = `<p style="color: #FF1744;">⚠️ Sunucuya bağlanılamadı. Render.com backend'i uyku modunda olabilir. Lütfen 10-15 saniye bekleyip tekrar deneyin.</p>`;
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
                        istanbulAlertResult.innerHTML = `
                            <div style="background-color: rgba(46, 204, 113, 0.2); border: 2px solid #2ecc71; color: #2ecc71; padding: 15px; border-radius: 8px;">
                                <p style="margin: 0; font-weight: 600;">✅ ${data.message}</p>
                                <p style="margin: 10px 0 0 0; font-size: 0.9em;">Deprem öncesi sinyaller tespit edildiğinde size WhatsApp ile bildirim gönderilecektir.</p>
                            </div>
                        `;
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