from triage.gate import evaluate_gate


def test_confidence_and_risk_both_control_autonomy() -> None:
    assert evaluate_gate({"Low": 0.9}).action == "autonomous"
    assert evaluate_gate({"High": 0.9}).action == "autonomous"
    assert evaluate_gate({"High": 0.7}).action == "autonomous"
    assert evaluate_gate({"High": 0.69}).action == "escalate"
    assert evaluate_gate({"Critical": 0.99}).action == "escalate"


def test_gate_accepts_classifier_prediction_payload() -> None:
    prediction = {"Low": 0.1, "Medium": 0.1, "High": 0.7, "Critical": 0.1,
                  "predicted_class": "High", "confidence": 0.7}
    result = evaluate_gate(prediction)
    assert result.predicted_class == "High"
    assert result.autonomous is True
