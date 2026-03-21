const RENDER_BACKEND_URL = "https://depremanaliz.onrender.com";

const API_BASE = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:5000"
    : (window.location.hostname.includes("github.io") ? RENDER_BACKEND_URL : window.location.origin);

const state = {
    map: null,
    cityLayer: null,
    gridLayer: null,
    cities: [],
    grid: [],
    selectedCity: null,
    metrics: null,
    location: null
};

function stripDecorative(value) {
    const text = String(value ?? "");
    try {
        return text.replace(/\p{Extended_Pictographic}/gu, "").replace(/\s{2,}/g, " ").trim();
    } catch (_) {
        return text.trim();
    }
}

function formatPercent(value) {
    return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function formatFixed(value, digits = 2, fallback = "0.00") {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric.toFixed(digits) : fallback;
}

function formatDateTime(value) {
    if (!value) return "Unknown";
    try {
        return new Date(value).toLocaleString("tr-TR");
    } catch (_) {
        return String(value);
    }
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setHtml(id, value) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = value;
}

async function fetchJson(path, options = {}, timeoutMs = 90000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(`${API_BASE}${path}`, {
            mode: "cors",
            headers: { "Content-Type": "application/json", ...(options.headers || {}) },
            ...options,
            signal: controller.signal
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return await response.json();
    } finally {
        clearTimeout(timeoutId);
    }
}

function forecastColor(probability) {
    if (probability >= 0.60) return "#c63d2f";
    if (probability >= 0.40) return "#c88326";
    if (probability >= 0.22) return "#b7a125";
    return "#18794e";
}

function warningClass(level) {
    const normalized = String(level || "").toUpperCase();
    if (normalized.includes("KRITIK") || normalized.includes("KRİTİK")) return "warning-critical";
    if (normalized.includes("YUKSEK") || normalized.includes("YÜKSEK")) return "warning-high";
    if (normalized.includes("ORTA")) return "warning-medium";
    if (normalized.includes("NORMAL")) return "warning-normal";
    return "warning-neutral";
}

function initMap() {
    if (!window.L) return;

    state.map = L.map("forecastMap", {
        zoomControl: true,
        scrollWheelZoom: true
    }).setView([39.1, 35.2], 6);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors &copy; CARTO"
    }).addTo(state.map);

    state.cityLayer = L.layerGroup().addTo(state.map);
    state.gridLayer = L.layerGroup();

    [50, 200, 600].forEach(delay => {
        setTimeout(() => {
            if (state.map) state.map.invalidateSize();
        }, delay);
    });
}

function buildPopup(point) {
    const features = Array.isArray(point.top_features) && point.top_features.length
        ? point.top_features.map(item => `<div>${stripDecorative(item.name || item.feature)}: ${formatFixed(item.value ?? item.impact ?? 0, 3)}</div>`).join("")
        : "<div>No explanation available.</div>";

    const weights = Object.entries(point.ensemble_weights || {})
        .map(([key, value]) => `<div>${String(key).toUpperCase()}: ${formatPercent(value)}</div>`)
        .join("");

    return `
        <strong>${stripDecorative(point.city || "Forecast point")}</strong><br>
        Final probability: ${formatPercent(point.probability)}<br>
        Risk score: ${formatFixed(point.risk_score, 2)}/10<br>
        M&gt;=5 / 72h: ${formatPercent(point.m5_72h_probability)}<br>
        Max mag / 7d: ${formatFixed(point.max_mag_7d_prediction, 2)}<br>
        Locality score: ${formatPercent(point.locality_score)}<br>
        Fault distance: ${formatFixed(point.fault_distance, 1, "999.0")} km<br>
        Signal events: ${Number(point.signal_event_count || 0)}<br>
        <hr>
        <div><strong>Weights</strong></div>
        ${weights || "<div>No weight data.</div>"}
        <hr>
        <div><strong>Top features</strong></div>
        ${features}
    `;
}

function buildMetricTiles(point) {
    const tiles = [
        ["Final probability", formatPercent(point.probability)],
        ["Risk score", `${formatFixed(point.risk_score, 2)}/10`],
        ["ML", formatPercent(point.ml_probability)],
        ["ETAS", formatPercent(point.etas_probability)],
        ["LSTM", formatPercent(point.lstm_probability)],
        ["GNN", formatPercent(point.gnn_probability)],
        ["M>=5 / 72h", formatPercent(point.m5_72h_probability)],
        ["Max mag / 7d", formatFixed(point.max_mag_7d_prediction, 2)],
        ["Locality score", formatPercent(point.locality_score)],
        ["Fault distance", `${formatFixed(point.fault_distance, 1, "999.0")} km`],
        ["Fault segment", stripDecorative(point.nearest_fault_segment || "unknown")],
        ["Signal events", String(Number(point.signal_event_count || 0))],
        ["Stress transfer", formatPercent(point.stress_transfer)]
    ];

    return tiles.map(([label, value]) => `
        <div class="metric-tile">
            <span class="tile-label">${label}</span>
            <strong class="tile-value">${value}</strong>
        </div>
    `).join("");
}

function updateSelectedCity(point) {
    if (!point) return;
    state.selectedCity = point;

    setText("selectedCityName", stripDecorative(point.city || "Unknown city"));
    setText(
        "selectedCitySubtitle",
        `Final probability ${formatPercent(point.probability)}, M>=5 / 72h ${formatPercent(point.m5_72h_probability)}, signal window ${Number(point.signal_event_count || 0)} event.`
    );
    setHtml("selectedMetricGrid", buildMetricTiles(point));

    const featureHtml = Array.isArray(point.top_features) && point.top_features.length
        ? point.top_features.map(item => `
            <span class="tag-item">${stripDecorative(item.name || item.feature)}: ${formatFixed(item.value ?? item.impact ?? 0, 3)}</span>
        `).join("")
        : `<span class="empty-state">No SHAP-style explanation available for this point.</span>`;
    setHtml("selectedFeatures", featureHtml);

    const weightEntries = Object.entries(point.ensemble_weights || {});
    const weightHtml = weightEntries.length
        ? weightEntries.map(([key, value]) => `
            <div class="weight-row">
                <span>${String(key).toUpperCase()}</span>
                <div class="weight-bar"><div class="weight-fill" style="width:${Math.max(0, Math.min(100, Number(value || 0) * 100))}%"></div></div>
                <span>${formatPercent(value)}</span>
            </div>
        `).join("")
        : `<div class="empty-state">No ensemble weights available.</div>`;
    setHtml("selectedWeights", weightHtml);

    renderCityRanking(state.cities);
}

function renderCityMarkers(points) {
    state.cityLayer.clearLayers();
    const bounds = [];

    points.forEach(point => {
        if (typeof point.lat !== "number" || typeof point.lon !== "number") return;

        const color = forecastColor(Number(point.probability || 0));
        const marker = L.circleMarker([point.lat, point.lon], {
            radius: 8 + Math.min(14, Number(point.risk_score || 0)),
            color,
            fillColor: color,
            fillOpacity: 0.74,
            weight: 2
        }).addTo(state.cityLayer);

        marker.bindPopup(buildPopup(point));
        marker.on("click", () => updateSelectedCity(point));
        bounds.push([point.lat, point.lon]);
    });

    if (bounds.length) {
        state.map.fitBounds(bounds, { padding: [36, 36] });
    }
}

function renderGridMarkers(points) {
    state.gridLayer.clearLayers();

    points.forEach(point => {
        if (typeof point.lat !== "number" || typeof point.lon !== "number") return;
        const color = forecastColor(Number(point.probability || 0));
        L.circleMarker([point.lat, point.lon], {
            radius: 3.6,
            color,
            fillColor: color,
            fillOpacity: 0.16,
            weight: 1
        }).bindPopup(buildPopup(point)).addTo(state.gridLayer);
    });
}

function syncLayerVisibility() {
    if (!state.map) return;

    const showCities = document.getElementById("toggleCityLayer")?.checked !== false;
    const showGrid = !!document.getElementById("toggleGridLayer")?.checked;

    if (showCities && !state.map.hasLayer(state.cityLayer)) {
        state.cityLayer.addTo(state.map);
    } else if (!showCities && state.map.hasLayer(state.cityLayer)) {
        state.map.removeLayer(state.cityLayer);
    }

    if (showGrid && !state.map.hasLayer(state.gridLayer)) {
        state.gridLayer.addTo(state.map);
    } else if (!showGrid && state.map.hasLayer(state.gridLayer)) {
        state.map.removeLayer(state.gridLayer);
    }
}

function renderCityRanking(points) {
    const container = document.getElementById("cityRanking");
    if (!container) return;

    const sorted = [...points].sort((left, right) => Number(right.probability || 0) - Number(left.probability || 0));
    const spread = sorted.length
        ? Number(sorted[0].probability || 0) - Number(sorted[sorted.length - 1].probability || 0)
        : 0;

    setText(
        "rankingSummary",
        sorted.length
            ? `Tracking ${sorted.length} cities. Forecast spread ${formatPercent(spread)} between highest and lowest city probability.`
            : "No city forecast data."
    );

    container.innerHTML = sorted.map(point => {
        const activeClass = state.selectedCity && point.city === state.selectedCity.city ? " is-active" : "";
        return `
            <button class="ranking-row${activeClass}" type="button" data-city="${stripDecorative(point.city)}">
                <div class="ranking-top">
                    <span class="ranking-title">${stripDecorative(point.city)}</span>
                    <span class="ranking-score">${formatPercent(point.probability)}</span>
                </div>
                <div class="ranking-meta">
                    <span>M>=5 / 72h ${formatPercent(point.m5_72h_probability)}</span>
                    <span>Locality ${formatPercent(point.locality_score)}</span>
                    <span>Fault ${formatFixed(point.fault_distance, 1, "999.0")} km</span>
                    <span>Signals ${Number(point.signal_event_count || 0)}</span>
                </div>
            </button>
        `;
    }).join("");

    container.querySelectorAll(".ranking-row").forEach(button => {
        button.addEventListener("click", () => {
            const point = state.cities.find(item => stripDecorative(item.city) === button.dataset.city);
            if (!point) return;
            updateSelectedCity(point);
            if (state.map) {
                state.map.flyTo([point.lat, point.lon], Math.max(state.map.getZoom(), 6), { duration: 0.6 });
            }
        });
    });
}

function renderCalibration(calibration) {
    const xs = Array.isArray(calibration?.prob_pred) ? calibration.prob_pred : [];
    const ys = Array.isArray(calibration?.prob_true) ? calibration.prob_true : [];
    if (!xs.length || xs.length !== ys.length) {
        setHtml("calibrationChart", `<div class="empty-state">No calibration curve available.</div>`);
        return;
    }

    const width = 420;
    const height = 250;
    const pad = 28;
    const scaleX = value => pad + Math.max(0, Math.min(1, Number(value || 0))) * (width - pad * 2);
    const scaleY = value => height - pad - Math.max(0, Math.min(1, Number(value || 0))) * (height - pad * 2);
    const points = xs.map((x, index) => `${scaleX(x)},${scaleY(ys[index])}`).join(" ");
    const circles = xs.map((x, index) => `<circle cx="${scaleX(x)}" cy="${scaleY(ys[index])}" r="4" fill="#b13a2d"></circle>`).join("");

    setHtml("calibrationChart", `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Calibration chart">
            <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="rgba(31, 41, 55, 0.04)"></rect>
            <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${pad}" stroke="rgba(31, 41, 55, 0.22)" stroke-dasharray="6 6"></line>
            <polyline points="${points}" fill="none" stroke="#0f766e" stroke-width="3"></polyline>
            ${circles}
            <text x="${pad}" y="${height - 8}" font-size="11" fill="#5f6b7a">Predicted probability</text>
            <text x="10" y="${pad - 8}" font-size="11" fill="#5f6b7a">Observed frequency</text>
        </svg>
    `);
}

function renderImportance(items) {
    if (!Array.isArray(items) || !items.length) {
        setHtml("importanceList", `<div class="empty-state">No feature importance data.</div>`);
        return;
    }

    const top = items.slice(0, 10);
    const maxValue = Math.max(...top.map(item => Number(item.value ?? item.importance ?? 0)), 1);
    setHtml("importanceList", top.map(item => {
        const name = stripDecorative(item.name || item.feature);
        const value = Number(item.value ?? item.importance ?? 0);
        const width = Math.max(2, (value / maxValue) * 100);
        return `
            <div class="importance-row">
                <span>${name}</span>
                <div class="importance-track"><div class="importance-fill" style="width:${width}%"></div></div>
                <span>${formatFixed(value, 2)}</span>
            </div>
        `;
    }).join(""));
}

function renderMetricBlocks(metrics, backtest, calibration) {
    const blocks = [
        ["ROC-AUC", `${formatFixed(metrics.roc_auc_mean ?? metrics.roc_auc ?? 0, 3)}`],
        ["PR-AUC", `${formatFixed(metrics.pr_auc_mean ?? metrics.pr_auc ?? 0, 3)}`],
        ["Brier", `${formatFixed(metrics.brier_mean ?? metrics.brier ?? 0, 4)}`],
        ["Backtest hit", `${formatPercent(backtest.hit_rate || 0)}`],
        ["Positive rate", `${formatFixed(metrics.positive_rate ?? 0, 3)}`],
        ["Samples", `${Number(metrics.samples ?? metrics.samples_test ?? 0)}`],
        ["Mean forecast", `${formatPercent(backtest.mean_prob || 0)}`],
        ["Calibration bins", `${Array.isArray(calibration?.prob_true) ? calibration.prob_true.length : 0}`]
    ];

    setHtml("metricsGrid", blocks.map(([label, value]) => `
        <div class="metric-block">
            <span>${label}</span>
            <strong>${value}</strong>
        </div>
    `).join(""));
}

function renderNarrative(metrics, backtest, targets) {
    const roc = Number(metrics.roc_auc_mean ?? metrics.roc_auc ?? 0);
    const pr = Number(metrics.pr_auc_mean ?? metrics.pr_auc ?? 0);
    const brier = Number(metrics.brier_mean ?? metrics.brier ?? 1);
    const hit = Number(backtest.hit_rate || 0);
    const primaryTarget = stripDecorative(targets?.primary || "m4_24h");
    const auxiliary = Array.isArray(targets?.auxiliary) ? targets.auxiliary.join(", ") : "none";
    const citySpread = state.cities.length
        ? Number(Math.max(...state.cities.map(point => Number(point.probability || 0))) - Math.min(...state.cities.map(point => Number(point.probability || 0))))
        : 0;
    const gnnInactive = state.cities.length && state.cities.every(point => Number(point.gnn_probability || 0) === 0);

    const sentences = [
        `The primary live score on screen is ${primaryTarget}. Auxiliary targets are ${stripDecorative(auxiliary)}.`,
        `Current discrimination is moderate with ROC-AUC ${roc.toFixed(3)} and PR-AUC ${pr.toFixed(3)}.`,
        `Probability calibration is ${brier <= 0.08 ? "good" : brier <= 0.15 ? "usable" : "weak"} based on Brier ${brier.toFixed(4)}.`,
        `Rolling backtest hit rate is ${(hit * 100).toFixed(1)} percent.`,
        `City forecast spread is ${formatPercent(citySpread)} across the tracked city set.`
    ];

    if (gnnInactive) {
        sentences.push("GNN contribution is currently zero in the live outputs; if that remains after restart, verify the runtime environment that serves the app.");
    }

    setHtml("qualityNarrative", sentences.map(sentence => `<p>${sentence}</p>`).join(""));
}

function updateSummary(metricsPayload, turkeyWarnings) {
    const metrics = metricsPayload.metrics || {};
    const backtest = metricsPayload.backtest || {};
    const targets = metricsPayload.targets || {};

    setText("summaryModel", stripDecorative(metricsPayload.model_type || "forecast_hybrid_v3_timeseriescv"));
    setText("summaryTarget", `Primary target ${stripDecorative(targets.primary || "m4_24h")}`);
    setText("summaryTrainedAt", formatDateTime(metricsPayload.trained_at));
    setText("summarySamples", `${Number(metrics.samples ?? metrics.samples_test ?? 0)} samples`);
    setText("summaryBacktest", formatPercent(backtest.hit_rate || 0));
    setText("summaryRoc", `ROC ${formatFixed(metrics.roc_auc_mean ?? metrics.roc_auc ?? 0, 3)}`);

    const activeCount = Number(turkeyWarnings?.cities_with_warnings || 0);
    setText("summaryWarningState", activeCount > 0 ? `${activeCount} active city` : "No active city");
    setText(
        "summaryWarningNote",
        activeCount > 0
            ? "Before-event warning remains enabled."
            : "Before-event warning remains available."
    );
}

async function loadMetrics() {
    const data = await fetchJson("/api/v2/forecast-metrics");
    state.metrics = data;

    const metrics = data.metrics || {};
    const backtest = data.backtest || {};
    renderMetricBlocks(metrics, backtest, data.calibration || {});
    renderCalibration(data.calibration || {});
    renderImportance(data.feature_importance || []);
    return data;
}

async function loadForecastCities() {
    setText("forecastMapStatus", "Loading city forecast.");
    const data = await fetchJson("/api/v2/forecast-map");
    const points = Array.isArray(data.points) ? data.points : [];
    state.cities = points;
    renderCityMarkers(points);
    renderCityRanking(points);
    syncLayerVisibility();

    if (points.length) {
        const top = [...points].sort((left, right) => Number(right.probability || 0) - Number(left.probability || 0))[0];
        updateSelectedCity(top);
        setText("forecastMapStatus", `Loaded ${points.length} city forecasts. Grid is optional.`);
    } else {
        setText("forecastMapStatus", "No city forecast data returned.");
    }

    return data;
}

async function loadForecastGrid(forceReload = false) {
    if (!document.getElementById("toggleGridLayer")?.checked) {
        state.gridLayer.clearLayers();
        syncLayerVisibility();
        return;
    }

    if (state.grid.length && !forceReload) {
        renderGridMarkers(state.grid);
        syncLayerVisibility();
        setText("forecastMapStatus", `Grid layer loaded with ${state.grid.length} points.`);
        return;
    }

    setText("forecastMapStatus", "Loading grid forecast. This can take longer than city forecast.");
    const data = await fetchJson("/api/v2/forecast-grid", {}, 180000);
    state.grid = Array.isArray(data.points) ? data.points : [];
    renderGridMarkers(state.grid);
    syncLayerVisibility();
    setText("forecastMapStatus", `Grid layer loaded with ${state.grid.length} points.`);
}

function renderIstanbulWarning(data) {
    const level = stripDecorative(data.alert_level || "Unknown");
    const message = stripDecorative(data.message || "No warning message.");
    const timeToEvent = stripDecorative(data.time_to_event || "No estimate");
    const score = formatFixed(data.alert_score || 0, 2);
    const predictedMagnitude = data.predicted_magnitude != null ? `Predicted magnitude ${formatFixed(data.predicted_magnitude, 1)}.` : "Predicted magnitude unavailable.";
    const recent = Number(data.recent_earthquakes || 0);
    const anomaly = data.anomaly_detected ? "Anomaly detected." : "No anomaly flag.";

    const body = [
        `<p>${message}</p>`,
        `<p>Warning score ${score}. ${predictedMagnitude}</p>`,
        `<p>Time window ${timeToEvent}. Recent events ${recent}. ${anomaly}</p>`
    ].join("");

    const levelEl = document.getElementById("istanbulWarningLevel");
    if (levelEl) {
        levelEl.className = `warning-level ${warningClass(level)}`;
        levelEl.textContent = level;
    }

    setHtml("istanbulWarningBody", body);
}

function renderTurkeyWarnings(data) {
    if (data && data.status === "error") {
        const summaryEl = document.getElementById("turkeyWarningSummary");
        if (summaryEl) {
            summaryEl.className = "warning-level warning-neutral";
            summaryEl.textContent = "Turkey warning endpoint error";
        }
        setHtml("turkeyWarningList", `<div class="status-error">${stripDecorative(data.message || "Turkey early warning could not be loaded.")}</div>`);
        return;
    }

    const count = Number(data.cities_with_warnings || 0);
    const summary = count > 0
        ? `${count} city has active pre-event warning output.`
        : "No active city warning at the current run.";

    const summaryEl = document.getElementById("turkeyWarningSummary");
    if (summaryEl) {
        summaryEl.className = `warning-level ${count > 0 ? "warning-high" : "warning-normal"}`;
        summaryEl.textContent = summary;
    }

    const activeWarnings = data.active_warnings || {};
    const entries = Object.entries(activeWarnings);
    if (!entries.length) {
        setHtml("turkeyWarningList", `<div class="empty-state">The pre-event Turkey warning module is active, but no city is currently in ORTA or above.</div>`);
        return;
    }

    setHtml("turkeyWarningList", entries.map(([city, warning]) => `
        <div class="warning-item">
            <strong>${stripDecorative(city)}</strong><br>
            Level ${stripDecorative(warning.alert_level || "Unknown")}<br>
            Score ${formatFixed(warning.alert_score || 0, 2)}<br>
            ${warning.predicted_magnitude != null ? `Predicted magnitude ${formatFixed(warning.predicted_magnitude, 1)}<br>` : ""}
            ${stripDecorative(warning.message || "")}
        </div>
    `).join(""));
}

async function loadWarnings() {
    const [istanbulResult, turkeyResult] = await Promise.allSettled([
        fetchJson("/api/istanbul-early-warning"),
        fetchJson("/api/turkey-early-warning")
    ]);

    const istanbul = istanbulResult.status === "fulfilled"
        ? istanbulResult.value
        : {
            alert_level: "ERROR",
            alert_score: 0,
            message: `Istanbul warning endpoint failed: ${stripDecorative(istanbulResult.reason?.message || "unknown error")}`,
            recent_earthquakes: 0,
            anomaly_detected: false
        };

    const turkey = turkeyResult.status === "fulfilled"
        ? turkeyResult.value
        : {
            cities_with_warnings: 0,
            active_warnings: {},
            status: "error",
            message: `Turkey warning endpoint failed: ${stripDecorative(turkeyResult.reason?.message || "unknown error")}`
        };

    renderIstanbulWarning(istanbul || {});
    renderTurkeyWarnings(turkey || {});
    return { istanbul, turkey };
}

async function requestOptInLink() {
    const result = document.getElementById("optInResult");
    result.textContent = "Requesting opt-in link.";

    try {
        const data = await fetchJson("/api/get-opt-in-link");
        if (!data.success) {
            result.innerHTML = `<span class="status-error">${stripDecorative(data.message || "Opt-in link could not be created.")}</span>`;
            return;
        }

        result.innerHTML = `
            <div><strong>WhatsApp number:</strong> ${stripDecorative(data.test_number || "")}</div>
            <div><a href="${data.opt_in_link}" target="_blank" rel="noopener">Open opt-in link</a></div>
            <p>${stripDecorative(data.message || "")}</p>
        `;
    } catch (error) {
        result.innerHTML = `<span class="status-error">Opt-in request failed: ${stripDecorative(error.message)}</span>`;
    }
}

function extractAlertCoordinates() {
    const lat = Number(document.getElementById("alertLat")?.value || 0);
    const lon = Number(document.getElementById("alertLon")?.value || 0);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    if (!lat && !lon) return null;
    return { lat, lon };
}

async function saveGeneralAlert() {
    const status = document.getElementById("alertFormStatus");
    const number = (document.getElementById("alertNumber")?.value || "").trim();
    const coords = extractAlertCoordinates() || state.location;

    if (!number) {
        status.innerHTML = `<span class="status-error">Phone number is required.</span>`;
        return;
    }
    if (!coords) {
        status.innerHTML = `<span class="status-error">Latitude and longitude are required for the general alert.</span>`;
        return;
    }

    status.textContent = "Saving general alert registration.";
    try {
        const data = await fetchJson("/api/set-alert", {
            method: "POST",
            body: JSON.stringify({
                number,
                lat: coords.lat,
                lon: coords.lon
            })
        });
        status.innerHTML = `<span class="status-ok">${stripDecorative(data.message || "General alert registration saved.")}</span>`;
    } catch (error) {
        status.innerHTML = `<span class="status-error">General alert registration failed: ${stripDecorative(error.message)}</span>`;
    }
}

async function saveIstanbulAlert() {
    const status = document.getElementById("alertFormStatus");
    const number = (document.getElementById("alertNumber")?.value || "").trim();
    const coords = extractAlertCoordinates() || state.location || {};

    if (!number) {
        status.innerHTML = `<span class="status-error">Phone number is required.</span>`;
        return;
    }

    status.textContent = "Saving Istanbul alert registration.";
    try {
        const data = await fetchJson("/api/istanbul-alert", {
            method: "POST",
            body: JSON.stringify({
                number,
                lat: coords.lat,
                lon: coords.lon
            })
        });
        const warning = data.warning ? `<div>${stripDecorative(data.warning)}</div>` : "";
        status.innerHTML = `<span class="status-ok">${stripDecorative(data.message || "Istanbul alert registration saved.")}</span>${warning}`;
    } catch (error) {
        status.innerHTML = `<span class="status-error">Istanbul alert registration failed: ${stripDecorative(error.message)}</span>`;
    }
}

function useBrowserLocation() {
    const status = document.getElementById("alertFormStatus");
    if (!navigator.geolocation) {
        status.innerHTML = `<span class="status-error">Geolocation is not supported in this browser.</span>`;
        return;
    }

    status.textContent = "Reading browser location.";
    navigator.geolocation.getCurrentPosition(
        position => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            state.location = { lat, lon };
            document.getElementById("alertLat").value = lat.toFixed(6);
            document.getElementById("alertLon").value = lon.toFixed(6);
            status.innerHTML = `<span class="status-ok">Location captured as ${lat.toFixed(4)}, ${lon.toFixed(4)}.</span>`;
        },
        error => {
            status.innerHTML = `<span class="status-error">Location could not be read: ${stripDecorative(error.message)}</span>`;
        }
    );
}

async function refreshDashboard({ reloadGrid = false } = {}) {
    let metricsPayload = null;
    let warningsPayload = { turkey: { cities_with_warnings: 0 } };

    try {
        metricsPayload = await loadMetrics();
    } catch (error) {
        setHtml("qualityNarrative", `<p class="status-error">Metrics could not be loaded: ${stripDecorative(error.message)}</p>`);
    }

    warningsPayload = await loadWarnings();

    try {
        await loadForecastCities();
    } catch (error) {
        setText("forecastMapStatus", `Forecast refresh failed: ${stripDecorative(error.message)}`);
        return;
    }

    if (metricsPayload) {
        updateSummary(metricsPayload, warningsPayload.turkey);
        renderNarrative(metricsPayload.metrics || {}, metricsPayload.backtest || {}, metricsPayload.targets || {});
    } else {
        setText("summaryWarningState", Number(warningsPayload.turkey?.cities_with_warnings || 0) > 0 ? "Warning active" : "Warning ready");
        setText("summaryWarningNote", "Forecast map is available even if metrics failed.");
    }

    if (document.getElementById("toggleGridLayer")?.checked) {
        try {
            await loadForecastGrid(reloadGrid);
        } catch (error) {
            setText("forecastMapStatus", `Grid load failed: ${stripDecorative(error.message)}`);
        }
    } else {
        state.gridLayer.clearLayers();
        syncLayerVisibility();
    }
}

function bindEvents() {
    document.getElementById("refreshForecastButton")?.addEventListener("click", () => refreshDashboard({ reloadGrid: true }));
    document.getElementById("toggleCityLayer")?.addEventListener("change", syncLayerVisibility);
    document.getElementById("toggleGridLayer")?.addEventListener("change", async event => {
        syncLayerVisibility();
        if (event.target.checked) {
            await loadForecastGrid(false);
        } else {
            setText("forecastMapStatus", "Grid layer hidden. City forecast remains visible.");
        }
    });

    document.getElementById("refreshIstanbulWarning")?.addEventListener("click", async () => {
        const data = await fetchJson("/api/istanbul-early-warning");
        renderIstanbulWarning(data || {});
    });

    document.getElementById("refreshTurkeyWarning")?.addEventListener("click", async () => {
        const data = await fetchJson("/api/turkey-early-warning");
        renderTurkeyWarnings(data || {});
    });

    document.getElementById("getOptInLinkButton")?.addEventListener("click", requestOptInLink);
    document.getElementById("saveGeneralAlertButton")?.addEventListener("click", saveGeneralAlert);
    document.getElementById("saveIstanbulAlertButton")?.addEventListener("click", saveIstanbulAlert);
    document.getElementById("useLocationButton")?.addEventListener("click", useBrowserLocation);

    window.addEventListener("resize", () => {
        if (state.map) state.map.invalidateSize();
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    bindEvents();
    refreshDashboard();
});
