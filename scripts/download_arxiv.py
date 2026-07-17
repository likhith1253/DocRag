import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
import os
import ssl

# Bypass SSL verification if there are environment issues
ssl._create_default_https_context = ssl._create_unverified_context

BASE_URL = 'http://export.arxiv.org/api/query?'

CATEGORIES = {
    'AI': 'cat:cs.AI',
    'RAG': 'all:"retrieval augmented generation"',
    'LLM': 'all:"large language model"',
    'ComputerVision': 'cat:cs.CV',
    'MedicalAI': 'all:"medical" AND (cat:cs.AI OR cat:cs.LG)',
    'GraphML': 'all:"graph neural network"',
    'Robotics': 'cat:cs.RO'
}

MAX_PAPERS_PER_CAT = 10  # starting with 10 for speed; can increase later if stress testing

def download_papers(base_dir="d:/DocRag/papers"):
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    for cat_name, query in CATEGORIES.items():
        cat_dir = os.path.join(base_dir, cat_name)
        if not os.path.exists(cat_dir):
            os.makedirs(cat_dir)

        print(f"\\nFetching metadata for {cat_name} (query: {query})...")
        encoded_query = urllib.parse.quote(query)
        url = f"{BASE_URL}search_query={encoded_query}&start=0&max_results={MAX_PAPERS_PER_CAT}&sortBy=relevance&sortOrder=descending"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                xml_data = response.read()
        except Exception as e:
            print(f"Failed to fetch metadata for {cat_name}: {e}")
            continue

        root = ET.fromstring(xml_data)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}

        entries = root.findall('atom:entry', namespace)
        if not entries:
            print(f"No papers found for {cat_name}.")
            continue

        count = 0
        for entry in entries:
            title = entry.find('atom:title', namespace).text.replace('\n', ' ').strip()
            pdf_link = None
            for link in entry.findall('atom:link', namespace):
                if link.attrib.get('title') == 'pdf':
                    pdf_link = link.attrib.get('href')
                    break
            
            if pdf_link:
                # Add .pdf if missing
                if not pdf_link.endswith('.pdf'):
                    pdf_link += '.pdf'
                
                # Sanitize filename
                safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                safe_title = safe_title[:50].replace(' ', '_')
                filename = f"{safe_title}.pdf"
                filepath = os.path.join(cat_dir, filename)

                if os.path.exists(filepath):
                    print(f"  Already exists: {filename}")
                    count += 1
                    continue

                print(f"  Downloading: {filename} from {pdf_link}")
                try:
                    # polite delay
                    time.sleep(3)
                    pdf_req = urllib.request.Request(pdf_link, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(pdf_req, timeout=15) as pdf_res:
                        with open(filepath, 'wb') as f:
                            f.write(pdf_res.read())
                    count += 1
                except Exception as e:
                    print(f"  Failed to download {filename}: {e}")

        print(f"Completed {cat_name}: downloaded {count}/{len(entries)} papers.")

if __name__ == "__main__":
    download_papers()
