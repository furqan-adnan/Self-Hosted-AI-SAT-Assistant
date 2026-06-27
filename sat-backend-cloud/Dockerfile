# Use the official Python 3.10 runtime
FROM python:3.10-slim

# FIX: Install system dependencies required by llama-cpp shared libraries (OpenMP and OpenBLAS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up a secure non-root user as required by Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

WORKDIR /home/user/app

# OPTIMIZATION: Install the corrected prebuilt wheel FIRST to satisfy requirements instantly
RUN pip install --no-cache-dir https://huggingface.co/Luigi/llama-cpp-python-wheels-hf-spaces-free-cpu/resolve/main/llama_cpp_python-0.3.22-cp310-cp310-linux_x86_64.whl

# Install remaining standard Python dependencies
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Create a storage directory for the AI weights
RUN mkdir -p models

# BAKE THE 9B MODEL: Downloads Gemma-2-9B directly into the cloud container during build
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Bartowski/gemma-2-9b-it-GGUF', filename='gemma-2-9b-it-Q4_K_M.gguf', local_dir='models')"

# Copy the application code last to protect cache layers
COPY --chown=user main.py .
# CRITICAL FIX: Explicitly copy your local keyword index data into the container image
COPY --chown=user cloud_corpus.json .

# Expose the internal port Hugging Face looks for
EXPOSE 7860

# Fire up the application server binding to port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]