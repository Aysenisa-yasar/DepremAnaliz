# DepremAnaliz

Hybrid spatio-temporal earthquake forecasting prototype for Turkey.

This project combines machine learning, ETAS-like scoring, clustering, b-value analysis, sequence heuristics, graph neural networks, explainability, and grid-based forecasting into a single research-oriented pipeline.

## What It Does

- Fuses seismic data from Kandilli, USGS, and optional AFAD sources
- Builds short-horizon earthquake risk forecasts over cities and geographic grid cells
- Uses a hybrid ensemble of XGBoost, ETAS-like scoring, cluster analysis, b-value risk, LSTM-style sequence signal, and optional GNN signal
- Computes SHAP-based local explanations and global feature importance
- Stores rolling evaluation, calibration, and backtest summaries for model inspection

## Current Forecast Stack

- Primary target: `m4_24h`
- Auxiliary targets: `m5_72h`, `max_mag_7d`
- Main model: calibrated XGBoost classifier
- Auxiliary models: calibrated XGBoost classifier + XGBoost regressor
- Spatial model: PyTorch Geometric based GNN
- Explainability: SHAP

## v2 API

- `GET /api/v2/forecast-map`
- `GET /api/v2/forecast-grid`
- `GET /api/v2/forecast-metrics`
- `GET /api/v2/feature-importance`

## Project Structure

```text
forecast/                  core forecasting pipeline
forecast/gnn/              graph dataset, model, trainer, predictor
services/                  application service layer
routes/                    Flask v2 routes
static/                    frontend assets
templates/                 frontend templates
models/                    saved models
data/                      local data assets including fault geometry
app.py                     Flask app with legacy compatibility routes
```

## Installation

```bash
pip install -r requirements.txt
```

Optional GNN dependencies:

```bash
pip install torch torch-geometric
```

## Training

Train the hybrid forecast model:

```bash
python forecast/trainer.py
```

Train the optional GNN model:

```bash
python forecast/gnn/trainer.py
```

Run the application:

```bash
python app.py
```

## Forecast Outputs

The saved forecast model includes:

- Time-series cross-validation metrics
- Calibration curve data
- Rolling backtest summary
- Global feature importance
- Auxiliary target configuration

City and grid forecast responses include:

- Final probability
- ML / ETAS / LSTM / cluster / b-risk / GNN components
- `m5_72h_probability`
- `max_mag_7d_prediction`
- Fault proximity features
- SHAP top features for city-level explainable forecasts

## Research Directions

Planned or partially implemented upgrades:

- Real LSTM / GRU training instead of heuristic sequence scoring
- Stronger spatio-temporal GNN with richer node and edge features
- Calibration plots and benchmarking figures
- Higher-resolution grid forecasting
- Paper-ready evaluation reports

## Important Note

This project is a research and engineering prototype. It does not provide deterministic earthquake prediction. Outputs should be interpreted as short-term probabilistic risk estimates, not official warnings.

## License

MIT
