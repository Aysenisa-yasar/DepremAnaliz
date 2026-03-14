# forecast/explain.py - SHAP ile tahmin açıklaması (CalibratedClassifierCV unwrap)
def _unwrap_model(model):
    if hasattr(model, "calibrated_classifiers_") and model.calibrated_classifiers_:
        calibrated = model.calibrated_classifiers_[0]
        if hasattr(calibrated, "estimator"):
            return calibrated.estimator
        if hasattr(calibrated, "base_estimator"):
            return calibrated.base_estimator
    if hasattr(model, "estimator"):
        return model.estimator
    if hasattr(model, "base_estimator"):
        return model.base_estimator
    return model


def explain_prediction(model, X, feature_names):
    try:
        import shap
    except ImportError:
        return []
    base_model = _unwrap_model(model)
    try:
        explainer = shap.TreeExplainer(base_model)
        shap_values = explainer.shap_values(X)
        if isinstance(shap_values, list):
            vals = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
        else:
            vals = shap_values[0]
        pairs = [{"feature": name, "impact": float(v)} for name, v in zip(feature_names, vals)]
        pairs.sort(key=lambda x: abs(x["impact"]), reverse=True)
        return pairs[:5]
    except Exception:
        return []
