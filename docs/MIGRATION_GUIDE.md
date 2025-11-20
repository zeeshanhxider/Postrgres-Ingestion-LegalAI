# 🚀 Legal AI System Migration Guide

Complete guide for migrating the legal case processing system to a new PC with GPU acceleration.

## 📋 Pre-Migration Checklist

### **System Requirements:**
- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows 10+
- **RAM**: 16GB+ recommended (8GB minimum)
- **Storage**: 50GB+ free space for models and data
- **GPU**: NVIDIA RTX 3060+ or AMD RX 6600+ (optional but recommended)
- **Internet**: Stable connection for model downloads

### **Files to Transfer:**
```
law-helper/
├── app/                    # Core application code
├── scripts/               # Database scripts
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Container configuration
├── init-db.sql           # Database schema
├── migrate_to_new_pc.py   # This migration script
├── batch_process_pdfs.py  # PDF processing script
└── .env                  # Environment configuration
```

---

## 🎯 Quick Migration (Automated)

### **1. Clone Repository**
```bash
git clone https://github.com/yourusername/law-helper.git
cd law-helper
```

### **2. Run Migration Script**
```bash
# Auto-detect GPU and setup everything
python migrate_to_new_pc.py

# Or specify GPU type
python migrate_to_new_pc.py --gpu-type nvidia

# Skip model downloads (if you want to download later)
python migrate_to_new_pc.py --skip-models
```

### **3. Verify Installation**
```bash
python setup_ollama_processing.py
```

---

## 🔧 Manual Migration Steps

If you prefer manual setup or the automated script fails:

### **Step 1: System Prerequisites**

#### **Linux (Ubuntu/Debian):**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y curl wget git build-essential python3-pip python3-venv

# Install Docker
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
newgrp docker

# Install PostgreSQL client
sudo apt install -y postgresql-client
```

#### **macOS:**
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install packages
brew install python3 git docker docker-compose postgresql
```

#### **Windows:**
1. Install Python 3.8+ from [python.org](https://python.org)
2. Install Git from [git-scm.com](https://git-scm.com)
3. Install Docker Desktop from [docker.com](https://docker.com)
4. Install PostgreSQL from [postgresql.org](https://postgresql.org)

### **Step 2: GPU Setup**

#### **NVIDIA GPU:**
```bash
# Check GPU
nvidia-smi

# Install CUDA (if not present)
# Download from: https://developer.nvidia.com/cuda-downloads
```

#### **AMD GPU:**
```bash
# Install ROCm (if not present)
# Follow: https://rocm.docs.amd.com/en/latest/deploy/linux/quick_start.html
```

### **Step 3: Ollama Installation**

#### **Linux/macOS:**
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Verify installation
ollama --version
```

#### **Windows:**
1. Download from [ollama.ai](https://ollama.ai)
2. Run installer
3. Verify: `ollama --version`

### **Step 4: Python Environment**

```bash
# Create virtual environment
python3 -m venv venv

# Activate environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### **Step 5: Model Downloads**

```bash
# Download AI extraction model (4.3GB)
ollama pull llama3.3:latest

# Download embedding model (669MB)
ollama pull mxbai-embed-large

# Optional: Alternative model (4.7GB)
ollama pull llama3.1:latest
```

### **Step 6: Database Setup**

```bash
# Start Docker containers
docker compose up -d

# Wait for database to be ready
sleep 10

# Initialize database schema
python database_initializer.py
```

### **Step 7: Environment Configuration**

Create `.env` file:
```bash
# Database Configuration
DATABASE_URL=postgresql://legal_user:legal_pass@localhost:5432/legal_ai

# Ollama Configuration
USE_OLLAMA=true
OLLAMA_MODEL=llama3.3:latest
OLLAMA_EMBED_MODEL=mxbai-embed-large

# GPU Configuration
GPU_TYPE=nvidia  # or amd, cpu

# Optional: Disable OpenAI
# OPENAI_API_KEY=
```

---

## 🧪 Testing & Verification

### **1. System Test**
```bash
python setup_ollama_processing.py
```

### **2. API Test**
```bash
# Start the API
python -m app.main

# Test health endpoint
curl http://localhost:8000/api/v1/health/
```

### **3. PDF Processing Test**
```bash
# Create test folder with a PDF
mkdir test_pdfs
cp your_test_case.pdf test_pdfs/

# Process the PDF
python batch_process_pdfs.py test_pdfs --verbose
```

### **4. Database Verification**
```bash
# Connect to database
docker exec -it legal_ai_postgres psql -U legal_user -d legal_ai

# Check tables
\dt

# Check processed cases
SELECT case_id, title, court FROM cases LIMIT 5;

# Check word indexing
SELECT COUNT(*) FROM word_dictionary;
SELECT COUNT(*) FROM word_occurrence;

# Exit
\q
```

---

## 🎮 GPU Optimization

### **NVIDIA GPU Settings**

#### **Ollama GPU Configuration:**
```bash
# Set CUDA device
export CUDA_VISIBLE_DEVICES=0

# Run Ollama with GPU
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

#### **Performance Tuning:**
```bash
# Monitor GPU usage
watch -n 1 nvidia-smi

# Optimize for your GPU
# RTX 4090: Use llama3.3:latest
# RTX 3080: Use llama3.1:latest  
# RTX 3060: Use llama3:latest
```

### **AMD GPU Settings**

#### **ROCm Configuration:**
```bash
# Set ROCm device
export HIP_VISIBLE_DEVICES=0

# Run Ollama with AMD GPU
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

---

## 📊 Performance Expectations

### **Processing Speed (per PDF):**
- **CPU Only**: 2-5 minutes per PDF
- **NVIDIA RTX 3060**: 30-60 seconds per PDF
- **NVIDIA RTX 3080**: 20-40 seconds per PDF
- **NVIDIA RTX 4090**: 15-30 seconds per PDF
- **AMD RX 6600**: 45-90 seconds per PDF

### **Memory Usage:**
- **Base System**: 2-4GB RAM
- **Ollama Models**: 4-8GB RAM
- **Database**: 1-2GB RAM
- **Processing**: +2-4GB RAM per PDF

### **Storage Requirements:**
- **Models**: ~10GB
- **Database**: ~1GB per 1000 cases
- **Logs**: ~100MB per 100 PDFs

---

## 🔧 Troubleshooting

### **Common Issues:**

#### **Ollama Connection Failed:**
```bash
# Check if Ollama is running
ollama list

# Start Ollama service
ollama serve

# Check logs
journalctl -u ollama  # Linux
```

#### **GPU Not Detected:**
```bash
# NVIDIA
nvidia-smi

# AMD
rocm-smi

# Check drivers
lspci | grep -i vga
```

#### **Database Connection Failed:**
```bash
# Check Docker containers
docker ps

# Restart containers
docker compose down && docker compose up -d

# Check logs
docker compose logs postgres
```

#### **Model Download Failed:**
```bash
# Check internet connection
ping ollama.ai

# Retry download
ollama pull llama3.3:latest

# Check available space
df -h
```

### **Performance Issues:**

#### **Slow Processing:**
1. **Check GPU utilization**: `nvidia-smi` or `rocm-smi`
2. **Reduce batch size**: Process fewer PDFs at once
3. **Use smaller model**: Try `llama3:latest` instead of `llama3.3:latest`
4. **Increase RAM**: Add more system memory

#### **Memory Errors:**
1. **Close other applications**
2. **Use CPU-only mode**: Set `GPU_TYPE=cpu`
3. **Process PDFs individually**
4. **Restart Ollama service**

---

## 📈 Post-Migration Optimization

### **1. Batch Processing Setup**
```bash
# Create processing scripts
mkdir -p scripts/batch_processing

# Setup cron job for automated processing
crontab -e
# Add: 0 2 * * * /path/to/law-helper/scripts/daily_batch.sh
```

### **2. Monitoring Setup**
```bash
# Install monitoring tools
pip install psutil GPUtil

# Create monitoring script
python scripts/system_monitor.py
```

### **3. Backup Strategy**
```bash
# Database backup
docker exec legal_ai_postgres pg_dump -U legal_user legal_ai > backup.sql

# Model backup
tar -czf ollama_models.tar.gz ~/.ollama/models/
```

---

## 🎯 Next Steps

After successful migration:

1. **Test with Real Data**: Process your actual legal PDFs
2. **Performance Tuning**: Optimize for your specific hardware
3. **Automation**: Set up automated batch processing
4. **Monitoring**: Implement system monitoring
5. **Backup**: Establish regular backup procedures

---

## 📞 Support

If you encounter issues:

1. **Check Logs**: Review migration_report.json
2. **Run Diagnostics**: `python setup_ollama_processing.py`
3. **Verify Prerequisites**: Ensure all dependencies are installed
4. **Test Components**: Test each component individually
5. **Check Resources**: Ensure sufficient RAM, storage, and GPU memory

**Happy Processing!** 🦙⚖️🚀
