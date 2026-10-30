# 51-Class Vehicle Classifier Full Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train and select a submission-ready 50-vehicle-plus-unknown classifier using the teacher dataset and validation Macro-F1.

**Architecture:** Keep the existing ImageFolder 51-class mapping and ResNet18 transfer-learning model. Add deterministic class-balanced training, stronger train-only augmentation, staged fine-tuning, per-epoch checkpoints/history, and complete validation metrics; select the final model only by 51-class validation Macro-F1.

**Tech Stack:** Python 3.12, PyTorch/torchvision, scikit-learn, Pillow, NVIDIA CUDA.

**Spec:** `E:/浏览器下载/视觉智能体综合实训：学生任务书.pdf`, sections 4.1-4.3.

## Global Constraints

- Exactly 50 four-digit target IDs from `classes.txt`; `unknown` is output index 50 and is not written to `classes.txt`.
- Train and validation data must not overlap; no teacher test images may be used for tuning.
- The final selection metric is validation Macro-F1 across all 51 classes.
- Save model structure, mapping, preprocessing, training configuration, intermediate checkpoints, final model, history, and confusion matrix.
- Pretrained ImageNet weights are initialization only; the vehicle classifier must be trained on the teacher dataset.

---

### Task 1: Validate dataset and label contract

**Files:**
- Create: `tests/test_training_pipeline.py`
- Modify: `train.py`

**Interfaces:**
- Produces: `validate_dataset_contract(root: str, registered_ids: list[str]) -> dict`

- [ ] Write tests that require 51 ordered classes, `unknown` last, no train/val duplicate files, and exact agreement with `classes.txt`.
- [ ] Run `pytest tests/test_training_pipeline.py -q` and confirm failure because validation helpers do not exist.
- [ ] Implement the validation helpers and run the test again until it passes.

### Task 2: Add task-compliant training and metrics

**Files:**
- Modify: `tests/test_training_pipeline.py`
- Modify: `train.py`

**Interfaces:**
- Produces: class-balanced loss weights, reproducible loaders, Accuracy/Precision/Recall/Macro-F1/unknown metrics, history JSON, per-epoch checkpoints, and best-model checkpoint.

- [ ] Add failing tests for balanced weights, deterministic transforms/config metadata, and complete 51-class metric output.
- [ ] Implement weighted cross-entropy, RandomResizedCrop augmentation, fixed seeds, learning-rate scheduling, and metric serialization.
- [ ] Verify focused tests and the existing backend test suite.

### Task 3: Enable and verify GPU runtime

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Produces: a CUDA-enabled PyTorch runtime recognized by `torch.cuda.is_available()`.

- [ ] Install a CUDA build compatible with Python 3.12 and the RTX 4060/installed driver.
- [ ] Verify CUDA availability, GPU name, one forward/backward pass, and available VRAM.
- [ ] Record exact runtime versions in the experiment metadata.

### Task 4: Run baseline and staged fine-tuning experiments

**Files:**
- Create: `output/experiments/baseline/history.json`
- Create: `output/experiments/finetune/history.json`
- Create: `output/experiments/finetune/best_model.pt`
- Modify: `output/model.pt`

**Interfaces:**
- Consumes: validated 51-class dataset and CUDA runtime.
- Produces: baseline result, improved result, best checkpoint, and final runtime checkpoint.

- [ ] Evaluate the existing checkpoint as the recorded baseline.
- [ ] Fine-tune ResNet18 with the last residual stage unfrozen, balanced loss, train-only augmentation, and validation Macro-F1 selection.
- [ ] If validation improves, unfreeze the full backbone at a lower learning rate and continue with early stopping.
- [ ] Copy only the best verified checkpoint to `output/model.pt` while retaining experiment checkpoints.

### Task 5: Produce evaluation evidence and integration verification

**Files:**
- Create: `output/experiments/finetune/metrics.json`
- Create: `output/experiments/finetune/confusion_matrix.csv`
- Create: `output/experiments/finetune/per_class_metrics.csv`
- Modify: `README.md`
- Modify: `build_manual.py`

**Interfaces:**
- Produces: report-ready metrics and a backend that loads the selected checkpoint.

- [ ] Generate 51-class metrics, unknown recall, known-class rejection rate, confusion matrix, and typical confusion pairs.
- [ ] Run single-image inference and batch prediction smoke tests.
- [ ] Restart the backend, verify the status endpoint reports the selected Macro-F1, and run all automated tests.
- [ ] Update documentation with actual measured values only.
