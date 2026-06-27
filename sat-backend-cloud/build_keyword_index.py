import os
import json
import re
from pypdf import PdfReader

def clean_text(text):
    # Standardize whitespace and remove erratic line breaks from PDFs
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

data_dir = "data"
processed_pages = []

if not os.path.exists(data_dir):
    os.makedirs(data_dir)
    print(f" Created '{data_dir}/' folder. Drop your study guide PDFs inside it and rerun.")
    exit()

print(" Scanning local data directory for PDFs...")
pdf_files = [f for f in os.listdir(data_dir) if f.endswith(".pdf")]

if not pdf_files:
    print("⚠️ No PDFs found in the 'data/' folder!")
    exit()

for file in pdf_files:
    path = os.path.join(data_dir, file)
    print(f" Processing: {file}")
    try:
        reader = PdfReader(path)
        for page_num, page in enumerate(reader.pages):
            raw_text = page.extract_text()
            
            if not raw_text or len(raw_text.strip()) < 15:
                # If your PDFs are raw images/scanned paper, standard extraction returns empty.
                # You would run a local OCR pipeline here.
                continue
                
            clean_page_text = clean_text(raw_text)
            
            # Save the entire page as a single cohesive structural node
            processed_pages.append({
                "text": clean_page_text,
                "source": f"{file} (Page {page_num + 1})"
            })
    except Exception as e:
        print(f" Error reading {file}: {e}")

# Compile into a single lightweight JSON file
with open("cloud_corpus.json", "w", encoding="utf-8") as f:
    json.dump(processed_pages, f, ensure_ascii=False, indent=2)

print(f"\n Done! Transformed your notes into {len(processed_pages)} page-level nodes.")
print("👉 Upload 'cloud_corpus.json' to your Hugging Face Space repository.")