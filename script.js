// script.js
// API URL'ini dinamik olarak belirle
const RENDER_BACKEND_URL = 'https://depremanaliz.onrender.com';

const API_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5000'
    : (window.location.hostname.includes('github.io') 
        ? RENDER_BACKEND_URL  // GitHub Pages'den Render.com backend'e bağlan
        : window.location.origin); // Diğer durumlarda aynı domain'i kullan

let mymap = null; 

function initializeMap() {
    if (mymap !== null && mymap._container) {
        mymap.remove();
        mymap = null;
    }
    
    mymap = L.map('mapid').setView([39.9, 35.8], 6); 

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(mymap);
}

function getRiskColor(score) {
    if (score >= 7.0) return 'red'; 
    if (score >= 4.0) return 'orange'; 
    return 'green'; 
}

document.addEventListener('DOMContentLoaded', () => {
    // API URL'ini dinamik olarak kullan (localhost veya production)
    const RENDER_API_BASE_URL = API_URL;
    const apiURL = `${RENDER_API_BASE_URL}/api/risk`; 
    
    const listContainer = document.getElementById('earthquake-list');
    const refreshButton = document.getElementById('refreshButton');
    
    const getLocationButton = document.getElementById('getLocationButton');
    const saveSettingsButton = document.getElementById('saveSettingsButton');
    const locationStatus = document.getElementById('locationStatus');
    const numberInput = document.getElementById('numberInput');
    
    const calculateDamageButton = document.getElementById('calculateDamageButton');
    const damageResult = document.getElementById('damageResult');
    const predictRiskButton = document.getElementById('predictRiskButton');
    const riskPredictionResult = document.getElementById('riskPredictionResult');
    const analyzeCityDamageButton = document.getElementById('analyzeCityDamageButton');
    const cityDamageResult = document.getElementById('cityDamageResult');
    const checkIstanbulWarningButton = document.getElementById('checkIstanbulWarningButton');
    const istanbulWarningResult = document.getElementById('istanbulWarningResult');

    let userCoords = null; 

    function fetchData() {
        listContainer.innerHTML = '<p>YZ risk analizi verileri yükleniyor...</p>';
        initializeMap(); 

        fetch(apiURL)
            .then(response => {
                if (!response.ok && response.status !== 404 && response.status !== 503 && response.status !== 500) {
                    throw new Error('YZ API bağlantı hatası: Beklenmeyen Kod ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                listContainer.innerHTML = '';
                
                if (!data || data.status === 'low_activity' || !data.risk_regions || data.risk_regions.length === 0) {
                    listContainer.innerHTML = '<p>Şu anda yeterli kümeleme verisi yok veya risk düşüktür. (Deprem sayısı < 10)</p>';
                    return;
                }

                let bounds = []; 
                
                // Aktif fay hatlarını haritaya ekle
                if (data.fault_lines) {
                    data.fault_lines.forEach(fault => {
                        const faultCoords = fault.coords.map(coord => [coord[0], coord[1]]);
                        const polyline = L.polyline(faultCoords, {
                            color: '#8B0000',
                            weight: 3,
                            opacity: 0.7
                        }).addTo(mymap);
                        polyline.bindPopup(`<b>${fault.name}</b>`);
                        bounds.push(...faultCoords);
                    });
                }
                
                data.risk_regions.forEach(riskRegion => {
                    
                    const { lat, lon, score, density } = riskRegion;
                    bounds.push([lat, lon]);
                    
                    const color = getRiskColor(score);
                    
                    const marker = L.circleMarker([lat, lon], {
                        radius: score * 1.5, 
                        color: color,
                        fillColor: color,
                        fillOpacity: 0.6,
                        weight: 2
                    }).addTo(mymap);
                    
                    const popupContent = `
                        <b>YZ Risk Merkezi #${riskRegion.id + 1}</b><br>
                        Risk Puanı: <b>${score.toFixed(1)} / 10</b><br>
                        Yoğunluk: ${density} deprem
                    `;
                    marker.bindPopup(popupContent).openPopup();

                    const item = document.createElement('div');
                    item.className = 'earthquake-item';
                    let magnitudeClass = (score >= 7.0) ? 'mag-high' : (score >= 4.0 ? 'mag-medium' : 'mag-low');

                    item.innerHTML = `
                        <div class="magnitude-box ${magnitudeClass}">${score.toFixed(1)}</div>
                        <div class="details">
                            <p class="location">Risk Merkezi #${riskRegion.id + 1}: YZ Analizi</p>
                            <p class="info">
                                Risk Puanı: ${score.toFixed(1)} / 10 | 
                                Yoğunluk: ${density} son deprem
                            </p>
                        </div>
                    `;
                    listContainer.appendChild(item);
                });
                
                if (bounds.length > 0) {
                    mymap.fitBounds(bounds, { padding: [50, 50] });
                }
            })
            .catch(error => {
                console.error('Veri çekme hatası:', error);
                listContainer.innerHTML = `<p>Hata: YZ sunucusuna bağlanılamadı. Render sunucunuzun aktif olduğunu kontrol edin. (${error.message})</p>`;
            });
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


    // Hasar Tahmini Hesaplama
    calculateDamageButton.addEventListener('click', () => {
        const magnitude = parseFloat(document.getElementById('damageMagnitude').value);
        const depth = parseFloat(document.getElementById('damageDepth').value);
        const distance = parseFloat(document.getElementById('damageDistance').value);
        const buildingType = document.getElementById('damageBuildingType').value;
        
        if (!magnitude || magnitude <= 0) {
            alert('Lütfen geçerli bir deprem büyüklüğü giriniz.');
            return;
        }
        
        fetch(`${RENDER_API_BASE_URL}/api/damage-estimate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                magnitude: magnitude,
                depth: depth,
                distance: distance,
                building_type: buildingType
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                damageResult.innerHTML = `<p style="color: red;">Hata: ${data.error}</p>`;
                damageResult.style.display = 'block';
                return;
            }
            
            let levelColor = '#2ecc71'; // Yeşil
            if (data.damage_score >= 70) levelColor = '#e74c3c'; // Kırmızı
            else if (data.damage_score >= 50) levelColor = '#e67e22'; // Turuncu
            else if (data.damage_score >= 30) levelColor = '#f39c12'; // Sarı
            
            damageResult.innerHTML = `
                <div style="background-color: ${levelColor}; color: white; padding: 15px; border-radius: 8px;">
                    <h3 style="margin: 0 0 10px 0;">Hasar Seviyesi: ${data.level}</h3>
                    <p style="margin: 5px 0; font-size: 1.2em;"><strong>Hasar Skoru: ${data.damage_score}/100</strong></p>
                    <p style="margin: 10px 0;">${data.description}</p>
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.3);">
                        <p style="margin: 5px 0; font-size: 0.9em;"><strong>Faktörler:</strong></p>
                        <p style="margin: 3px 0; font-size: 0.85em;">Büyüklük Etkisi: ${data.factors.magnitude_impact}</p>
                        <p style="margin: 3px 0; font-size: 0.85em;">Derinlik Faktörü: ${data.factors.depth_factor}</p>
                        <p style="margin: 3px 0; font-size: 0.85em;">Mesafe Faktörü: ${data.factors.distance_factor}</p>
                        <p style="margin: 3px 0; font-size: 0.85em;">Bina Faktörü: ${data.factors.building_factor}x</p>
                    </div>
                </div>
            `;
            damageResult.style.display = 'block';
        })
        .catch(error => {
            console.error('Hasar tahmini hatası:', error);
            damageResult.innerHTML = `<p style="color: red;">Hata: Sunucuya bağlanılamadı.</p>`;
            damageResult.style.display = 'block';
        });
    });
    
    // Risk Tahmini
    predictRiskButton.addEventListener('click', () => {
        if (!userCoords) {
            alert('Lütfen önce "Konumumu Otomatik Belirle" butonuna basarak konumunuzu tespit edin.');
            return;
        }
        
        riskPredictionResult.innerHTML = '<p>Risk tahmini yapılıyor...</p>';
        riskPredictionResult.style.display = 'block';
        
        fetch(`${RENDER_API_BASE_URL}/api/predict-risk`, {
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
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                riskPredictionResult.innerHTML = `<p style="color: red;">Hata: ${data.error}</p>`;
                return;
            }
            
            let riskColor = '#2ecc71'; // Yeşil
            if (data.risk_score >= 7.0) riskColor = '#e74c3c'; // Kırmızı
            else if (data.risk_score >= 5.0) riskColor = '#e67e22'; // Turuncu
            else if (data.risk_score >= 3.0) riskColor = '#f39c12'; // Sarı
            
            let detailsHtml = '';
            if (data.method === 'ml_ensemble') {
                detailsHtml = `
                    <p style="margin: 5px 0; font-size: 0.9em;"><strong>🤖 ML Model Tahminleri:</strong></p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Random Forest: ${data.model_predictions.random_forest}/10</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">XGBoost: ${data.model_predictions.xgboost}/10</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">LightGBM: ${data.model_predictions.lightgbm}/10</p>
                    <p style="margin: 10px 0 5px 0; font-size: 0.9em;"><strong>Özellikler:</strong></p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Toplam Deprem: ${data.features.count || 0}</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Maksimum Büyüklük: M${data.features.max_magnitude?.toFixed(1) || 'N/A'}</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">En Yakın Mesafe: ${data.features.min_distance?.toFixed(1) || 'N/A'} km</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Aktivite Yoğunluğu: ${data.features.activity_density?.toFixed(4) || 'N/A'}</p>
                    ${data.anomaly ? `
                        <p style="margin: 10px 0 5px 0; font-size: 0.9em;"><strong>⚠️ Anomali Tespiti:</strong></p>
                        <p style="margin: 3px 0; font-size: 0.85em;">Anomali Skoru: ${data.anomaly.anomaly_score}/1.0</p>
                        <p style="margin: 3px 0; font-size: 0.85em;">Tespit Edildi: ${data.anomaly.anomaly_detected ? '✅ Evet' : '❌ Hayır'}</p>
                    ` : ''}
                `;
            } else {
                detailsHtml = `
                    <p style="margin: 5px 0; font-size: 0.9em;"><strong>Detaylar:</strong></p>
                    <p style="margin: 3px 0; font-size: 0.85em;">En Büyük Deprem: M${data.factors.max_magnitude}</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Son 24 Saatteki Deprem Sayısı: ${data.factors.recent_count}</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">Ortalama Mesafe: ${data.factors.avg_distance} km</p>
                    <p style="margin: 3px 0; font-size: 0.85em;">En Yakın Fay Hattı: ${data.factors.nearest_fault_km} km</p>
                `;
            }
            
            riskPredictionResult.innerHTML = `
                <div style="background-color: ${riskColor}; color: white; padding: 15px; border-radius: 8px;">
                    <h3 style="margin: 0 0 10px 0;">Risk Seviyesi: ${data.risk_level}</h3>
                    <p style="margin: 5px 0; font-size: 1.2em;"><strong>Risk Skoru: ${data.risk_score}/10</strong></p>
                    <p style="margin: 5px 0; font-size: 0.9em;">Yöntem: ${data.method === 'ml_ensemble' ? '🤖 Gelişmiş ML (Ensemble)' : '📊 Geleneksel'}</p>
                    ${data.reason ? `<p style="margin: 10px 0;">${data.reason}</p>` : ''}
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.3);">
                        ${detailsHtml}
                    </div>
                </div>
            `;
        })
        .catch(error => {
            console.error('Risk tahmini hatası:', error);
            riskPredictionResult.innerHTML = `<p style="color: red;">Hata: Sunucuya bağlanılamadı.</p>`;
        });
    });
    
    // İl Bazında Hasar Analizi
    analyzeCityDamageButton.addEventListener('click', () => {
        cityDamageResult.innerHTML = '<p>İl bazında hasar analizi yapılıyor...</p>';
        cityDamageResult.style.display = 'block';
        
        fetch(`${RENDER_API_BASE_URL}/api/city-damage-analysis`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    cityDamageResult.innerHTML = `<p style="color: red;">Hata: ${data.error}</p>`;
                    return;
                }
                
                if (data.status === 'no_major_earthquakes') {
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
                        <p style="margin: 5px 0;">Toplam 5+ Deprem: <strong>${data.total_major_earthquakes}</strong></p>
                        <p style="margin: 5px 0;">Etkilenen İl Sayısı: <strong>${data.affected_cities}</strong></p>
                    </div>
                    <div style="max-height: 600px; overflow-y: auto;">
                `;
                
                data.city_damages.forEach((city, index) => {
                    let levelColor = '#2ecc71'; // Yeşil
                    if (city.max_damage_score >= 75) levelColor = '#e74c3c'; // Kırmızı
                    else if (city.max_damage_score >= 55) levelColor = '#e67e22'; // Turuncu
                    else if (city.max_damage_score >= 35) levelColor = '#f39c12'; // Sarı
                    else if (city.max_damage_score >= 18) levelColor = '#3498db'; // Mavi
                    
                    html += `
                        <div style="background-color: ${levelColor}; color: white; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                            <h4 style="margin: 0 0 10px 0;">${index + 1}. ${city.city}</h4>
                            <p style="margin: 5px 0; font-size: 1.2em;"><strong>Hasar Skoru: ${city.max_damage_score.toFixed(1)}/100</strong></p>
                            <p style="margin: 5px 0;"><strong>Seviye: ${city.damage_level}</strong></p>
                            <p style="margin: 10px 0; font-size: 0.9em;">${city.description}</p>
                            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.3);">
                                <p style="margin: 5px 0; font-size: 0.85em;"><strong>Etkilenen Binalar (%):</strong></p>
                                <p style="margin: 3px 0; font-size: 0.8em;">Güçlendirilmiş: %${city.affected_buildings.reinforced}</p>
                                <p style="margin: 3px 0; font-size: 0.8em;">Normal: %${city.affected_buildings.normal}</p>
                                <p style="margin: 3px 0; font-size: 0.8em;">Zayıf: %${city.affected_buildings.weak}</p>
                                <p style="margin: 10px 0 5px 0; font-size: 0.85em;"><strong>Etkilendiği Depremler:</strong></p>
                                ${city.earthquakes_affecting.map(eq => `
                                    <p style="margin: 2px 0; font-size: 0.75em;">M${eq.magnitude} - ${eq.location} (${eq.distance} km)</p>
                                `).join('')}
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
                cityDamageResult.innerHTML = html;
            })
            .catch(error => {
                console.error('İl bazında hasar analizi hatası:', error);
                cityDamageResult.innerHTML = `<p style="color: red;">Hata: Sunucuya bağlanılamadı.</p>`;
            });
    });
    
    // İstanbul Erken Uyarı Sistemi
    checkIstanbulWarningButton.addEventListener('click', () => {
        istanbulWarningResult.innerHTML = '<p>İstanbul erken uyarı durumu kontrol ediliyor...</p>';
        istanbulWarningResult.style.display = 'block';
        
        fetch(`${RENDER_API_BASE_URL}/api/istanbul-early-warning`)
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
                istanbulWarningResult.innerHTML = `<p style="color: red;">Hata: Sunucuya bağlanılamadı.</p>`;
            });
    });

    refreshButton.addEventListener('click', fetchData);
    fetchData();
});