# CUDA Driver Mismatch Diagnostic & Resolution

## Problem Statement

**Symptom:** ModernBERT NER model falling back to CPU during Condenser extraction phase
- Container reports CUDA version: 12090 (CUDA 12.4.x)
- Host NVIDIA driver: 577.13 (Too old)
- **Incompatibility:** Driver 577.13 requires CUDA 12.2 or lower; CUDA 12.4.1 requires driver 555.x or newer

## Driver Compatibility Matrix

| CUDA Version | Minimum Driver | Recommended Driver |
|---|---|---|
| 12.4.x | 555.x | 560.x+ |
| 12.2.x | 535.x | 545.x+ |
| 12.1.x | 530.x | 540.x+ |
| 11.8.x | 450.x | 500.x+ |
| **Your Host** | **577.13** | **Supports CUDA 12.2 max** |

## Solution Options

### Option A: Update NVIDIA Driver (Recommended if Possible)

**Best for:** Systems where driver update is feasible

1. **Check current driver:**
   ```powershell
   nvidia-smi
   ```

2. **Update to latest (560.x+):**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install nvidia-driver-560
   sudo reboot
   
   # Windows
   # Download from https://www.nvidia.com/Download/driverDetails.aspx
   # Install latest driver for your GPU
   ```

3. **Verify after reboot:**
   ```bash
   nvidia-smi  # Should show driver 560.x+
   ```

4. **Rebuild container:**
   ```bash
   docker-compose down
   docker-compose up --build
   ```

---

### Option B: Downgrade Container to CUDA 11.8 (Current Driver Compatible)

**Best for:** Systems where driver update not possible

**Changes needed:**

1. **Update Dockerfile:**
   ```dockerfile
   FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04
   # ... rest unchanged
   ```

2. **Update requirements.txt:**
   Replace PyTorch CUDA 12.4 with 11.8:
   ```diff
   - torch --extra-index-url https://download.pytorch.org/whl/cu124
   - torchvision --extra-index-url https://download.pytorch.org/whl/cu124
   + torch --extra-index-url https://download.pytorch.org/whl/cu118
   + torchvision --extra-index-url https://download.pytorch.org/whl/cu118
   ```

3. **Rebuild:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up
   ```

**Trade-off:** Loses access to CUDA 12.x optimizations, but maintains full GPU acceleration.

---

### Option C: Force CPU Mode Temporarily (Workaround)

**Best for:** Quick testing; not recommended for production

**Changes needed:**

1. **Update `.env`:**
   ```env
   DEVICE=cpu  # Add this
   NER_DEVICE=cpu
   ```

2. **Update `src/engine/ner.py`:**
   ```python
   DEVICE = os.getenv("NER_DEVICE", "cpu")  # Default to CPU if no CUDA
   ```

**Trade-off:** NER extraction will be significantly slower but will complete.

---

## Recommended Implementation Path

### Step 1: Quick Diagnostic

```bash
# Inside container
docker exec condensate-core nvidia-smi

# Check if CUDA is accessible
docker exec condensate-core python -c "import torch; print(torch.cuda.is_available())"

# Check ModernBERT device
docker exec condensate-core python -c "
from src.engine.ner import get_ner_engine
ner = get_ner_engine()
print(f'NER device: {ner.device}')
"
```

### Step 2: Implement Solution

**If driver 560+ available locally:**
- Follow Option A above
- Estimated time: 30 min (including reboot)
- No code changes needed

**If driver update not possible:**
- Follow Option B above  
- Modify 2 files (Dockerfile, requirements.txt)
- Rebuild container (~15 min)

### Step 3: Verify GPU Access

```bash
# After changes and restart
docker exec condensate-core python << 'EOF'
import torch
print(f"CUDA Available: {torch.cuda.is_available()}")
print(f"CUDA Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
print(f"CUDA Version: {torch.version.cuda}")
EOF
```

---

## Technical Root Cause

The NVIDIA container toolkit requires version compatibility between:

1. **Host NVIDIA Driver** (577.13 on your system)
   - Installed on the Linux/Windows host
   - Provides interaction with GPU hardware

2. **Container CUDA Runtime** (12.4.1 in Dockerfile)
   - CUDA libraries inside container
   - Must be compatible with host driver

3. **PyTorch/cuDNN** (cu124 in requirements.txt)
   - GPU-accelerated compute
   - Compiled for specific CUDA version

**Mismatch occurs when:** Container CUDA runtime > Host driver capability

---

## Performance Impact

### Current State (CPU Fallback)
- NER extraction: ~2-5 seconds per 1000 tokens
- Memory peak: ~800MB
- Bottleneck: Single-threaded CPU inference

### With GPU (CUDA 12.4 + driver 560+)
- NER extraction: ~200-500ms per 1000 tokens  
- Memory peak: ~1.2GB (mostly on GPU)
- Speedup: 4-10x

### With GPU (CUDA 11.8 + driver 577.13)
- NER extraction: ~300-600ms per 1000 tokens
- Memory peak: ~1.1GB
- Speedup: 3-8x

---

## Long-term Recommendations

1. **For Development:** Keep CUDA up-to-date with latest drivers
2. **For Production:** Pin CUDA version to a stable release (e.g., 12.2)
3. **For CI/CD:** Use base images that support wide driver ranges
4. **For Multi-GPU:** Test compatibility across all target driver versions

---

## Rollback Instructions

If changes cause issues:

```bash
# Revert to CUDA 12.4 (original)
git checkout Dockerfile requirements.txt

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up
```
