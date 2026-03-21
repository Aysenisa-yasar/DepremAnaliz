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
        pairs = [
            {
                "feature": name,
                "impact": float(v),
                "name": name,
                "value": float(v),
            }
            for name, v in zip(feature_names, vals)
        ]
        pairs.sort(key=lambda x: abs(x["impact"]), reverse=True)
        return pairs[:5]
    except Exception:
        return []


def global_feature_importance(model, feature_names):
    base_model = _unwrap_model(model)

    score_map = None
    if hasattr(base_model, "get_booster"):
        try:
            booster = base_model.get_booster()
            score_map = booster.get_score(importance_type="gain")
        except Exception:
            score_map = None

    if score_map:
        pairs = []
        for idx, name in enumerate(feature_names):
            value = float(score_map.get(f"f{idx}", 0.0))
            pairs.append({"feature": name, "importance": value, "name": name, "value": value})
        pairs.sort(key=lambda item: item["importance"], reverse=True)
        return pairs

    if hasattr(base_model, "feature_importances_"):
        try:
            importances = list(base_model.feature_importances_)
            pairs = []
            for name, value in zip(feature_names, importances):
                value = float(value)
                pairs.append({"feature": name, "importance": value, "name": name, "value": value})
            pairs.sort(key=lambda item: item["importance"], reverse=True)
            return pairs
        except Exception:
            return []

    return []
