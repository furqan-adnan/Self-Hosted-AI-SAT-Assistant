import os
import json
import easyocr

# Initialize the reader for English text
reader = easyocr.Reader(['en'])

IMAGE_FOLDER = "my_notes_images"
output_corpus = []

print("🚀 Starting Local Image OCR extraction across all folders...")

# os.walk automatically digs down into subfolders like SAT-ENG or SAT-MATH
for root, dirs, files in os.walk(IMAGE_FOLDER):
    # Sort files to keep pages in sequential order
    for filename in sorted(files):
        if filename.lower().endswith(('png', 'jpg', 'jpeg')):
            img_path = os.path.join(root, filename)
            
            # Create a clean display path for logging
            relative_path = os.path.relpath(img_path, IMAGE_FOLDER)
            print(f"📖 Processing: {relative_path}", flush=True)
            
            try:
                # Run OCR on the image file
                result = reader.readtext(img_path, detail=0)
                page_text = " ".join(result)
                
                # Make a pretty source name for your UI (e.g., "SAT-ENG / Page 1")
                source_label = relative_path.replace("\\", " / ").rsplit('.', 1)[0]
                
                output_corpus.append({
                    "source": source_label,
                    "text": page_text
                })
            except Exception as e:
                print(f"❌ Error processing {filename}: {e}", flush=True)

# Save the brand new data array
with open("cloud_corpus.json", "w", encoding="utf-8") as f:
    json.dump(output_corpus, f, indent=4)

print(f"\n✅ Success! Generated cloud_corpus.json with {len(output_corpus)} rich text pages.")