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

// WhatsApp Client'ı başlat
function initializeWhatsApp() {
    console.log('[WhatsApp] Client başlatılıyor...');
    
    client = new Client({
        authStrategy: new LocalAuth({
            dataPath: './whatsapp-session'
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
                '--disable-gpu'
            ]
        }
    });

    // QR Kod oluşturulduğunda
    let qrRefreshCount = 0;
    client.on('qr', async (qr) => {
        qrRefreshCount++;
        console.log(`[WhatsApp] QR kod oluşturuldu (${qrRefreshCount}. kez) - WhatsApp'tan QR kodu okutun!`);
        qrCodeData = qr;
        
        // QR kod'u base64'e çevir
        try {
            const qrImage = await qrcode.toDataURL(qr);
            qrCodeData = qrImage;
            console.log('[WhatsApp] QR kod hazır - 20 saniye içinde okutun!');
        } catch (err) {
            console.error('[WhatsApp] QR kod oluşturma hatası:', err);
        }
    });

    // Bağlantı hazır olduğunda
    client.on('ready', () => {
        console.log('[WhatsApp] ✅ Bağlantı başarılı! WhatsApp hazır.');
        isReady = true;
        isAuthenticated = true;
        qrCodeData = null; // QR kod artık gerekli değil
    });

    // Kimlik doğrulama başarılı
    client.on('authenticated', () => {
        console.log('[WhatsApp] ✅ Kimlik doğrulama başarılı');
        isAuthenticated = true;
    });

    // Kimlik doğrulama başarısız
    client.on('auth_failure', (msg) => {
        console.error('[WhatsApp] ❌ Kimlik doğrulama başarısız:', msg);
        isAuthenticated = false;
        isReady = false;
    });

    // Bağlantı kesildiğinde
    client.on('disconnected', (reason) => {
        console.log('[WhatsApp] ⚠️ Bağlantı kesildi:', reason);
        isReady = false;
        isAuthenticated = false;
        
        // Yeniden bağlanmayı dene
        if (reason === 'LOGOUT') {
            console.log('[WhatsApp] Oturum kapatıldı, yeniden başlatılıyor...');
            setTimeout(() => {
                initializeWhatsApp();
            }, 5000);
        }
    });

    // Hata durumunda
    client.on('error', (error) => {
        console.error('[WhatsApp] ❌ Hata:', error);
    });

    // Client'ı başlat
    client.initialize().catch(err => {
        console.error('[WhatsApp] ❌ Başlatma hatası:', err);
    });
}

// API Endpoints

// Durum kontrolü
app.get('/status', (req, res) => {
    res.json({
        ready: isReady,
        authenticated: isAuthenticated,
        hasQr: !!qrCodeData
    });
});

// QR kod al
app.get('/qr', (req, res) => {
    if (qrCodeData) {
        res.json({
            success: true,
            qr: qrCodeData,
            message: 'QR kod hazır. WhatsApp\'ı açıp QR kod okutun.'
        });
    } else if (isReady) {
        res.json({
            success: false,
            message: 'WhatsApp zaten bağlı. QR kod gerekli değil.'
        });
    } else {
        res.json({
            success: false,
            message: 'QR kod henüz hazır değil. Lütfen bekleyin...'
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
        client.destroy();
    }
    isReady = false;
    isAuthenticated = false;
    qrCodeData = null;
    
    setTimeout(() => {
        initializeWhatsApp();
    }, 2000);
    
    res.json({
        success: true,
        message: 'WhatsApp servisi yeniden başlatılıyor...'
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
