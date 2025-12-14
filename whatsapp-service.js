// WhatsApp Web.js Service - Ücretsiz WhatsApp Bildirim Sistemi
// QR kod ile bağlanma desteği

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

// WhatsApp Client
let client = null;
let qrCodeData = null;
let isReady = false;
let isAuthenticated = false;
let qrRefreshCount = 0;
let connectionError = null;

// WhatsApp Client'ı başlat
function initializeWhatsApp() {
    console.log('[WhatsApp] Client başlatılıyor...');
    connectionError = null;
    qrRefreshCount = 0;
    
    // Eğer önceki client varsa temizle
    if (client) {
        try {
            client.destroy();
        } catch (err) {
            console.log('[WhatsApp] Önceki client temizlenirken hata:', err.message);
        }
    }
    
    client = new Client({
        authStrategy: new LocalAuth({
            dataPath: './whatsapp-session',
            clientId: 'deprem-analiz-client'
        }),
        puppeteer: {
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-blink-features=AutomationControlled',
                '--window-size=1920,1080'
            ],
            timeout: 60000, // 60 saniye timeout
            ignoreHTTPSErrors: true
        },
        webVersionCache: {
            type: 'remote',
            remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.2413.51-beta.html',
        }
    });

    // QR Kod oluşturulduğunda
    client.on('qr', async (qr) => {
        qrRefreshCount++;
        console.log(`[WhatsApp] QR kod oluşturuldu (${qrRefreshCount}. kez) - WhatsApp'tan QR kodu okutun!`);
        console.log(`[WhatsApp] ⏰ QR kod 20 saniye içinde okutulmalı!`);
        qrCodeData = qr;
        connectionError = null; // QR kod yenilendi, hata temizlendi
        
        // QR kod'u base64'e çevir
        try {
            const qrImage = await qrcode.toDataURL(qr, {
                errorCorrectionLevel: 'M',
                type: 'image/png',
                quality: 0.92,
                margin: 1,
                color: {
                    dark: '#000000',
                    light: '#FFFFFF'
                }
            });
            qrCodeData = qrImage;
            console.log('[WhatsApp] ✅ QR kod hazır - WhatsApp > Ayarlar > Bağlı Cihazlar > Cihaz Bağla');
        } catch (err) {
            console.error('[WhatsApp] ❌ QR kod oluşturma hatası:', err);
            connectionError = `QR kod oluşturulamadı: ${err.message}`;
        }
    });

    // Bağlantı hazır olduğunda
    client.on('ready', () => {
        console.log('[WhatsApp] ✅ Bağlantı başarılı! WhatsApp hazır.');
        isReady = true;
        isAuthenticated = true;
        qrCodeData = null; // QR kod artık gerekli değil
        connectionError = null;
        qrRefreshCount = 0;
    });

    // Kimlik doğrulama başarılı
    client.on('authenticated', () => {
        console.log('[WhatsApp] ✅ Kimlik doğrulama başarılı');
        isAuthenticated = true;
        connectionError = null;
    });

    // Kimlik doğrulama başarısız
    client.on('auth_failure', (msg) => {
        console.error('[WhatsApp] ❌ Kimlik doğrulama başarısız:', msg);
        isAuthenticated = false;
        isReady = false;
        connectionError = `Kimlik doğrulama başarısız: ${msg}`;
        
        // Session dosyalarını temizle ve yeniden dene
        console.log('[WhatsApp] 🔄 Session temizleniyor ve yeniden başlatılıyor...');
        setTimeout(() => {
            clearSession();
            setTimeout(() => {
                initializeWhatsApp();
            }, 3000);
        }, 2000);
    });

    // Bağlantı kesildiğinde
    client.on('disconnected', (reason) => {
        console.log('[WhatsApp] ⚠️ Bağlantı kesildi:', reason);
        isReady = false;
        isAuthenticated = false;
        connectionError = `Bağlantı kesildi: ${reason}`;
        
        // Yeniden bağlanmayı dene
        if (reason === 'LOGOUT') {
            console.log('[WhatsApp] Oturum kapatıldı, session temizleniyor...');
            clearSession();
            setTimeout(() => {
                initializeWhatsApp();
            }, 5000);
        } else {
            // Diğer nedenler için de yeniden bağlanmayı dene
            console.log('[WhatsApp] Yeniden bağlanma deneniyor...');
            setTimeout(() => {
                initializeWhatsApp();
            }, 10000);
        }
    });

    // Hata durumunda
    client.on('error', (error) => {
        console.error('[WhatsApp] ❌ Hata:', error);
        connectionError = `Bağlantı hatası: ${error.message || error}`;
    });

    // Loading ekranı
    client.on('loading_screen', (percent, message) => {
        console.log(`[WhatsApp] ⏳ Yükleniyor: ${percent}% - ${message}`);
    });

    // Client'ı başlat
    client.initialize().catch(err => {
        console.error('[WhatsApp] ❌ Başlatma hatası:', err);
        connectionError = `Başlatma hatası: ${err.message || err}`;
        
        // Hata durumunda yeniden dene
        setTimeout(() => {
            console.log('[WhatsApp] 🔄 Yeniden başlatma deneniyor...');
            initializeWhatsApp();
        }, 10000);
    });
}

// Session dosyalarını temizle
function clearSession() {
    const sessionPath = './whatsapp-session';
    try {
        if (fs.existsSync(sessionPath)) {
            fs.rmSync(sessionPath, { recursive: true, force: true });
            console.log('[WhatsApp] ✅ Session dosyaları temizlendi');
        }
    } catch (err) {
        console.error('[WhatsApp] ❌ Session temizleme hatası:', err);
    }
}

// API Endpoints

// Durum kontrolü
app.get('/status', (req, res) => {
    res.json({
        ready: isReady,
        authenticated: isAuthenticated,
        hasQr: !!qrCodeData,
        qrRefreshCount: qrRefreshCount,
        error: connectionError,
        message: isReady 
            ? 'WhatsApp bağlı ve hazır' 
            : qrCodeData 
                ? `QR kod hazır (${qrRefreshCount}. kez) - 20 saniye içinde okutun!` 
                : connectionError 
                    ? connectionError 
                    : 'Bağlantı kuruluyor...'
    });
});

// QR kod al
app.get('/qr', (req, res) => {
    if (qrCodeData) {
        res.json({
            success: true,
            qr: qrCodeData,
            refreshCount: qrRefreshCount,
            message: `QR kod hazır (${qrRefreshCount}. kez). WhatsApp > Ayarlar > Bağlı Cihazlar > Cihaz Bağla menüsünden QR kodu okutun. 20 saniye içinde okutulmalı!`,
            instructions: [
                '1. WhatsApp uygulamanızı açın',
                '2. Ayarlar > Bağlı Cihazlar > Cihaz Bağla',
                '3. QR kodu okutun',
                '4. 20 saniye içinde okutmanız gerekiyor!'
            ]
        });
    } else if (isReady) {
        res.json({
            success: false,
            message: 'WhatsApp zaten bağlı. QR kod gerekli değil.',
            ready: true
        });
    } else {
        res.json({
            success: false,
            message: connectionError || 'QR kod henüz hazır değil. Lütfen bekleyin...',
            error: connectionError,
            refreshCount: qrRefreshCount
        });
    }
});

// Mesaj gönder
app.post('/send', async (req, res) => {
    if (!isReady || !isAuthenticated) {
        return res.status(503).json({
            success: false,
            error: 'WhatsApp bağlı değil. Lütfen önce QR kod ile bağlanın.'
        });
    }

    const { number, message } = req.body;

    if (!number || !message) {
        return res.status(400).json({
            success: false,
            error: 'Numara ve mesaj gerekli'
        });
    }

    try {
        // Numara formatını düzelt (ülke kodu ile)
        let phoneNumber = number.trim();
        if (!phoneNumber.startsWith('+')) {
            phoneNumber = '+' + phoneNumber.replace(/^0/, '');
        }
        
        // WhatsApp formatına çevir (90XXXXXXXXXX@c.us)
        const cleanNumber = phoneNumber.replace(/[^0-9]/g, '');
        const whatsappNumber = `${cleanNumber}@c.us`;

        // Mesaj gönder
        const result = await client.sendMessage(whatsappNumber, message);
        
        console.log(`[WhatsApp] ✅ Mesaj gönderildi: ${phoneNumber}`);
        
        res.json({
            success: true,
            messageId: result.id._serialized,
            message: 'Mesaj başarıyla gönderildi'
        });
    } catch (error) {
        console.error('[WhatsApp] ❌ Mesaj gönderme hatası:', error);
        res.status(500).json({
            success: false,
            error: error.message || 'Mesaj gönderilemedi'
        });
    }
});

// Yeniden başlat
app.post('/restart', (req, res) => {
    if (client) {
        try {
            client.destroy();
        } catch (err) {
            console.log('[WhatsApp] Client destroy hatası:', err.message);
        }
    }
    isReady = false;
    isAuthenticated = false;
    qrCodeData = null;
    connectionError = null;
    qrRefreshCount = 0;
    
    setTimeout(() => {
        initializeWhatsApp();
    }, 2000);
    
    res.json({
        success: true,
        message: 'WhatsApp servisi yeniden başlatılıyor...'
    });
});

// Session temizle ve yeniden başlat
app.post('/clear-session', (req, res) => {
    console.log('[WhatsApp] Session temizleme isteği alındı');
    
    if (client) {
        try {
            client.destroy();
        } catch (err) {
            console.log('[WhatsApp] Client destroy hatası:', err.message);
        }
    }
    
    clearSession();
    
    isReady = false;
    isAuthenticated = false;
    qrCodeData = null;
    connectionError = null;
    qrRefreshCount = 0;
    
    setTimeout(() => {
        initializeWhatsApp();
    }, 3000);
    
    res.json({
        success: true,
        message: 'Session temizlendi ve servis yeniden başlatılıyor...'
    });
});

// Sunucuyu başlat
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
    console.log(`[Server] WhatsApp servisi ${PORT} portunda çalışıyor`);
    console.log(`[Server] Durum: http://localhost:${PORT}/status`);
    console.log(`[Server] QR Kod: http://localhost:${PORT}/qr`);
    
    // WhatsApp'ı başlat
    initializeWhatsApp();
});
