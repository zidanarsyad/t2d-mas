# RCA graph module

The package is a course-sized root-cause-ranking prototype. It keeps the service-call graph directed (`edge_index`, caller to callee) and also adds a bidirectional message-passing view so incident evidence can reach callers and callees. Repeated calls are coalesced and their request volume is stored as `edge_weight`; the weighted GraphSAGE layers use that volume in their neighbor mean.

## Install

```powershell
python -m pip install -r rca/requirements.txt
```

PyTorch Geometric's installation instructions may vary with the installed PyTorch build. Use the official PyG install guide if pip needs a matching wheel index.

## Graph input contract

`compute_7d_baselines(history, as_of=...)` accepts timestamped rows with `service_instance_id` and the fields `latency`, `error_rate`, `cpu`, `mem`, and `saturation`. It computes population mean and standard deviation over the preceding seven days. `build_service_graph(current_metrics, calls, baseline)` returns PyG `Data` with five z-score features per service instance, directed call edges, request-volume weights, and an auxiliary bidirectional edge view for message passing.

For a constant baseline metric, the z-score is set to zero because no scale can be estimated. This is a simple course-project convention.

## Train, explain, and evaluate

Each training example is `(graph, incident_node_indices)`. `train_ranker` uses pairwise margin ranking loss so labeled incident nodes score above the other nodes in that graph. `explain_top3_nodes` applies GNNExplainer to a target node score and returns the three most important nodes plus explanatory edges. `evaluation.py` reports Top-1 accuracy, Top-3 accuracy, and MRR. `synthetic.generate_synthetic_incidents(seed=42)` creates reproducible examples by injecting metric deviations at a known service.

The hand-configured numeric fixture uses mean aggregation over the adjacent services of the A->B->C chain with `W=0.5I` and readout `[0.6, 0.4]`. That reference calculation gives 1.850, 2.225, and 2.600. The trained two-layer model learns its own parameters; the fixture is not a claim that training always produces those scores.

Run the assignment checks with:

```powershell
python -m pytest rca/tests -q
```
